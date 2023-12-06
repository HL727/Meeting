import json
import logging
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Sequence, TYPE_CHECKING, Union

from django.utils.timezone import now

from customer.models import Customer
from calendar_invite.types import InviteMessageParseDict, SyncResult, ChangedItemTuple, SyncChangesTuple, \
    CalendarInviteParseDict

from calendar_invite.models import Calendar, CalendarItem, Credentials
from shared.utils import maybe_update, get_multidict

if TYPE_CHECKING:
    from meeting.models import Meeting


logger = logging.getLogger(__name__)


class InviteHandler:

    @classmethod
    def populate_meeting_dial_settings(cls, data, endpoints, dialout=False):

        if not data.get('dialstring') and data.get('dialstring_fallback'):
            data['dialstring'] = data.pop('dialstring_fallback')

        if not data.get('dialstring') and data.get('dialstring_fallback_h323'):
            data['dialstring'] = data.pop('dialstring_fallback_h323')

        require_webrtc = False
        if not data['dialstring'] and data.get('dialstring_webrtc'):
            if any(e.supports_teams for e in endpoints):
                data['dialstring'] = data.get('dialstring_webrtc')
                require_webrtc = True

        room_info = []
        if data['dialstring']:
            room_info.append({
                'dialstring': data['dialstring'],
                'dialout': dialout and 'https://' not in data['dialstring'],
            })

            data['settings'] = json.dumps({
                **(data.get('settings') or {}),
                'external_uri': data['dialstring'],
            })

        for endpoint in sorted(endpoints, key=lambda x: x.email_key):
            if require_webrtc and not endpoint.supports_teams:
                continue

            room_info.append({
                'endpoint': endpoint.email_key,
            })

        data['room_info'] = json.dumps(room_info)
        return data

    @staticmethod
    def merge_room_infos(room_infos: Sequence[Union[str, Sequence]]) -> str:

        room_infos = [json.loads(room_info or '[]') if isinstance(room_info, str) else room_info
                      for room_info in room_infos]

        all_rooms = [room for lst in room_infos for room in lst]
        result = sorted(all_rooms, key=lambda r: json.dumps(r))

        return json.dumps(result)


class CalendarInviteHandler(InviteHandler):

    calendars: Sequence[Calendar]

    def __init__(self, cred_obj: Credentials):
        self.credentials = cred_obj
        self.video_meetings_only = cred_obj.video_meetings_only

        self.calendars = self.get_active_calendars()

    def get_active_calendars(self):
        return self.credentials.calendar_set.exclude(username='', folder_id='').exclude(endpoint__isnull=True).select_related('endpoint')

    def get_local_items(self, ts_start: datetime = None, ts_stop: datetime = None):

        return CalendarItem.objects.filter(
            credentials=self.credentials,
            meeting__ts_stop__gt=ts_start,
            meeting__ts_start__lt=ts_stop,
            meeting__backend_active=True,
        ).select_related('meeting')

    @abstractmethod
    def get_remote_items(self, ts_start: datetime = None, ts_stop: datetime = None, incremental_since=None) -> Sequence[InviteMessageParseDict]:
        raise NotImplementedError()

    @staticmethod
    def serialize_remote(item: InviteMessageParseDict):
        return (item['uid'], item['recurrence_id'], item['subject'], item['ts_start'].isoformat(), item['ts_stop'].isoformat(), item['room_info'])

    @staticmethod
    def serialize_local(item: CalendarItem):
        assert item.meeting
        return (item.ical_uid, item.meeting.recurrence_id, item.meeting.title, item.meeting.ts_start.isoformat(), item.meeting.ts_stop.isoformat(), item.meeting.room_info)

    @classmethod
    def merge_serialized_remotes(cls, remotes: Sequence[InviteMessageParseDict]):
        """merge remotes based on all serialized values except room_info"""
        grouped_without_rooms = get_multidict(remotes, key=lambda r: cls.serialize_remote(r)[:-1])
        serialized = []
        merged_remotes = []

        for serialized_key, lst in grouped_without_rooms.items():
            merged_room_info = cls.merge_room_infos(r['room_info'] for r in lst)

            serialized.append((*serialized_key, merged_room_info))

            new_remote = lst[0].copy()
            new_remote['room_info'] = merged_room_info
            merged_remotes.append(new_remote)
        return serialized, merged_remotes

    @classmethod
    def get_changes(cls, remote_items: Sequence[InviteMessageParseDict],
                    local_items: Sequence[CalendarItem]) -> SyncChangesTuple:

        local_items_map = get_multidict(local_items, key=lambda x: (x.ical_uid, x.meeting.recurrence_id))
        remote_items_map = get_multidict(remote_items, key=lambda x: (x['uid'], x['recurrence_id']))

        new = []
        removed = []
        changed = []

        for item_key in set(local_items_map) | set(remote_items_map):

            if item_key not in remote_items_map:  # only local. should be removed
                logger.debug('%s (%s) only in local database. Delete', item_key[0], item_key[1])
                removed.extend(local_items_map[item_key])
                continue

            serialized_remote, merged_remote_items = cls.merge_serialized_remotes(remote_items_map[item_key])

            if item_key not in local_items_map:  # only remote. should be created
                logger.debug('%s (%s) only exists in remote items. Add to local database', item_key[0], item_key[1])
                new.extend(merged_remote_items)
                continue

            serialized_local = [cls.serialize_local(local) for local in local_items_map[item_key]]

            serialized_multi = get_multidict(zip(serialized_local, local_items_map[item_key]), key=lambda x: x[0])
            for cur_local in serialized_multi.values():
                for sl, local in cur_local[1:]:  # remove duplicates
                    if sl in serialized_remote:
                        removed.append(local)
                        logger.debug('%s (%s) is a duplicate. Delete from local database', item_key[0], item_key[1])

            # determinate changed values
            missing_local = [local for sl, local in zip(serialized_local, local_items_map[item_key])
                             if sl not in serialized_remote]
            missing_remote = [remote for sr, remote in zip(serialized_remote, merged_remote_items)
                              if sr not in serialized_local]

            if not missing_local and not missing_remote:
                logger.debug('%s (%s) is unchanged. Skip', item_key[0], item_key[1])
                continue

            for i in range(max(len(missing_local), len(missing_remote))):
                if i >= len(missing_local):
                    logger.debug('%s (%s) has changed in serie. Create separate event', item_key[0], item_key[1])
                    new.append(missing_remote[i])
                elif i >= len(missing_remote):
                    logger.debug('%s (%s) has been removed from serie. Delete from local database', item_key[0], item_key[1])
                    removed.append(missing_local[i])
                else:
                    logger.debug('%s (%s) has been changed. Update local database', item_key[0], item_key[1])
                    changed.append(ChangedItemTuple(missing_local[i], missing_remote[i]))

        return SyncChangesTuple(new, changed, removed)

    def filter_cancelled(self, result: Sequence[InviteMessageParseDict], ts_start: datetime, ts_stop: datetime):
        new_result = [r for r in result if not r.get('cancelled')]
        if len(result) != len(new_result):
            logger.info('Removed %s cancelled items', len(result) - len(new_result))
        return new_result

    def filter_result_timeframe(self, result: Sequence[InviteMessageParseDict], ts_start: datetime, ts_stop: datetime):
        new_result = [r for r in result if r['ts_stop'] >= ts_start and r['ts_start'] < ts_stop]
        if len(result) != len(new_result):
            logger.info('Removed %s items outside of time frame', len(result) - len(new_result))
        return new_result

    def get_sync_state(
        self,
        ts_start: datetime = None,
        ts_stop: datetime = None,
        incremental_since=None,
    ) -> SyncChangesTuple:
        """fetch remote data and compare it to local database. return pending sync actions"""

        remote_items = self.get_remote_items(ts_start, ts_stop, incremental_since=incremental_since)
        remote_items = self.filter_result_timeframe(remote_items, ts_start, ts_stop)
        remote_items = self.filter_cancelled(remote_items, ts_start, ts_stop)

        local_items = self.get_local_items(ts_start, ts_stop)

        return self.get_changes(remote_items, local_items)

    def get_sync_state_today(
        self,
        incremental_since=None,
    ) -> SyncChangesTuple:
        """helper function for debugging"""
        return self.get_sync_state(ts_start=now(),
                                   ts_stop=now().replace(hour=23, minute=59),
                                   incremental_since=incremental_since,
                                   )

    def sync(
        self,
        ts_start: datetime = None,
        ts_stop: datetime = None,
        incremental_since=None,
    ) -> SyncResult:
        """full sync of remote data for items between timestamps"""

        new_data, changed, removed = self.get_sync_state(ts_start=ts_start, ts_stop=ts_stop,
                                                         incremental_since=incremental_since)
        if incremental_since:
            removed = []

        return self.perform_sync(new_data, changed, removed)

    def perform_sync(self,
                     new_data: Sequence[CalendarInviteParseDict],
                     changed: Sequence[ChangedItemTuple],
                     removed: Sequence[CalendarItem]) -> SyncResult:
        """write changes to local database"""

        from meeting.models import RecurringMeeting

        recurring_meetings = {r.uid: r for r in RecurringMeeting.objects.filter(
            pk__in=CalendarItem.objects.filter(
                credentials=self.credentials,
                recurring_meeting__uid__in=[e['uid'] for e in new_data + [c[1] for c in changed]],
            ).values_list('recurring_meeting_id', flat=True)
        )}

        result = SyncResult([], [], [])

        for data in new_data:
            meeting = self.create_meeting(data, self.credentials.customer, recurring_meeting=recurring_meetings.get(data['uid']))
            calendar_item, _created = self.update_calendar_item(meeting, data)
            result.new.append(calendar_item)

        for calendar_item, data in changed:
            maybe_update(calendar_item.meeting, self.get_meeting_kwargs(data, recurring_meeting=recurring_meetings.get(data['uid'])))
            maybe_update(calendar_item, self.get_calendar_item_kwargs(calendar_item.meeting, data))
            calendar_item.meeting.activate()
            result.changed.append(calendar_item)

        for existing in removed:
            existing.meeting.api.unbook(existing.meeting)  # TODO check if really removed.
            existing.delete()  # Also deactivate/deletes meeting
            result.removed.append(existing)

        return result

    def get_meeting_kwargs(self, remote_data: CalendarInviteParseDict, **extra):
        result = {
            'creator': remote_data['creator'],
            'ts_start': remote_data['ts_start'],
            'ts_stop': remote_data['ts_stop'],
            'timezone': remote_data.get('timezone'),
            'title': remote_data['subject'],
            'ical_uid': remote_data.get('uid'),
            'room_info': remote_data.get('room_info') or '',
            'settings': remote_data.get('settings') or '',
            'recurrence_id': remote_data.get('recurrence_id') or '',
            **extra,
        }
        return result

    def create_meeting(self,
                       data: CalendarInviteParseDict,
                       customer: Customer,
                       recurring_meeting=None,
                       **extra_kwargs,
                       ):

        from provider.models.provider import Provider
        if data.get('dialstring'):
            provider = Provider.objects.get_active('external')
        else:
            provider = Provider.objects.get_active('offline')

        from meeting.models import Meeting

        if data['is_recurring'] and not recurring_meeting:
            from meeting.models import RecurringMeeting
            recurring_meeting = RecurringMeeting.objects.create(
                provider=provider,
                customer=customer,
                uid=data['uid'],
                external_occasion_handling=True,
            )

        meeting = Meeting.objects.create(
                provider=provider,
                customer=customer,
                recurring_master=recurring_meeting,
                source='{}:{}'.format({0: 'ews', 10: 'msgraph'}.get(self.credentials.type, 'calendar'), self.credentials.pk),
                **self.get_meeting_kwargs(data, **extra_kwargs),
            )

        meeting.activate()
        return meeting

    def get_calendar_item_kwargs(self, meeting: 'Meeting', data: CalendarInviteParseDict):
        return {
            'meeting': meeting,
            'recurring_meeting': meeting.recurring_master,
            'changekey': data.get('changekey') or '',
            'ical_uid': data.get('uid') or '',
        }

    def update_calendar_item(self, meeting: 'Meeting', data: CalendarInviteParseDict):
        return CalendarItem.objects.update_or_create(
            credentials=self.credentials,
            item_id=data['envelope'],
            calendar=data['calendar'],
            defaults=self.get_calendar_item_kwargs(meeting, data)
        )


