# -*- coding: utf-8 -*-
from typing import Dict, Union, Optional, TYPE_CHECKING

import pytz
from django.utils.timezone import utc

from calendar_invite.parser import InviteMessageParser, fix_subject
from calendar_invite.types import CalendarInviteParseDict
from provider.models.utils import date_format

if TYPE_CHECKING:
    from calendar_invite.models import Calendar


class MSGraphParser(InviteMessageParser):

    def __init__(self, item: Dict, calendar: Optional['Calendar'] = None):
        self.item = item
        self.calendar = calendar or None
        super().__init__()

    def get_timezone(self, zone):
        try:
            return pytz.timezone(zone or 'UTC')
        except pytz.UnknownTimeZoneError:
            return None  # TODO raise error? probably only relevant for recurring rules

    def parse_datetime(self, s: Union[Dict, str], timezone=None):
        from django.utils.dateparse import parse_datetime

        if isinstance(s, dict):
            timezone = self.get_timezone(s.get('timeZone'))
            s = s['dateTime']

        result = parse_datetime(s)
        return result.replace(tzinfo=timezone or utc)  # utc is always correct fallback?

    def parse(self) -> CalendarInviteParseDict:
        participants = [a['emailAddress'] for a in self.item['attendees']]

        is_recurring = bool(self.item['seriesMasterId'])
        if self.item['seriesMasterId']:
            recurrence_id = date_format(self.parse_datetime(self.item.get('originalStart') or self.item['start']))
        else:
            recurrence_id = ''

        ts_start = self.parse_datetime(self.item['start'])

        result = CalendarInviteParseDict(
            creator_name=self.item['organizer']['emailAddress']['name'] if self.item['organizer'] else '',
            creator=self.item['organizer']['emailAddress']['address'] if self.item['organizer'] else '',
            subject=fix_subject(self.item['subject'] or '')[:100],
            participants=participants,
            envelope=self.item['id'],
            skype_conference='',
            ts_start=ts_start,
            ts_stop=self.parse_datetime(self.item['end']),
            timezone=self.get_timezone(self.item['originalStartTimeZone']) or ts_start.tzinfo,
            uid=self.item['iCalUId'],
            recurrence_id=recurrence_id,
            dialstring='',
            is_private=self.item['sensitivity'] in ('private', 'confidential'),
            is_recurring=is_recurring,
            recurring='',
            recurring_exceptions='',
            error=None,
            changekey=self.item.get('changeKey'),
            calendar=self.calendar,
            endpoints=[self.calendar.endpoint] if self.calendar and self.calendar.endpoint else None,
            has_body=False,
            cancelled=self.item['isCancelled'],
        )

        # Reuse EmailParser.parse_text() and EmailParser.parse_calendar()
        if self.item.get('body'):
            result['has_body'] = True
            result.update(self.parse_text(self.item['body']['content']))

        if self.item.get('location') and 0:  # TODO
            result.update(self.parse_text(self.item.get('location')))

        self.maybe_use_fallback_dialstring(result)

        return result

