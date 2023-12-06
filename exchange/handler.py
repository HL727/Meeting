# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from datetime import datetime
from typing import Sequence, Union, TYPE_CHECKING

from django.conf import settings
from django.utils.timezone import now
from exchangelib import EWSDateTime, Account
from exchangelib.errors import ErrorItemNotFound

from calendar_invite.handler import CalendarInviteHandler
from calendar_invite.models import Calendar
from calendar_invite.types import InviteMessageParseDict
from shared.utils import partial_update
from .parser import EWSParser
import exchangelib
from exchangelib.folders import FolderId
from exchangelib.services import GetFolder
from exchangelib.items import ID_ONLY

if TYPE_CHECKING:
    from .models import EWSCredentials


logger = logging.getLogger(__name__)


class ExchangeHandler(CalendarInviteHandler):

    ITEM_FIELDS = (
        'organizer', 'subject', 'required_attendees', 'optional_attendees', 'start',
        'end', 'uid', 'body', 'location', 'parent_folder_id', 'is_cancelled',
        'is_recurring', 'original_start', 'type'
    )

    def __init__(self, cred_obj: 'EWSCredentials', account: 'Account' = None):
        super().__init__(cred_obj)
        self.account = account or cred_obj.get_ews_account(validate_login=None)
        self.calendar_map = {c.folder_id: c for c in self.calendars}

    def get_active_calendars(self):
        return (
            self.credentials.calendar_set.exclude(folder_id='')
            .exclude(endpoint__isnull=True)
            .exclude(is_working=False)
            .select_related('endpoint')
        )

    def get_account_folders(self):
        folder_ids = [
            FolderId(id=c.folder_id) for c in self.calendar_map.values() if c.folder_id
        ]
        if not folder_ids:
            logger.info('No active folders to sync, exiting')
            return []

        logger.info('Start syncing %s folders for account %s', len(folder_ids), self.account)

        folder_objects = GetFolder(account=self.account).call(folder_ids, [], ID_ONLY)
        folders = exchangelib.FolderCollection(account=self.account, folders=folder_objects)

        if len(self.calendars) != len(folder_ids):
            logger.warning('Could not fetch all calendars from exchange, probably permission error. Got %s but should be %s',
                           len(folders), len(self.calendars))

        return folders

    def fetch_exchange_items_incremental(self, ts_start: datetime = None,
                             ts_stop: datetime = None,
                             incremental_since: datetime = None) -> Sequence[InviteMessageParseDict]:

        if not incremental_since:
            raise ValueError('Incremental value is required')

        folders = self.get_account_folders()

        if not folders:
            return []

        for folder in folders:
            calendar = self.calendar_map[folder.id]
            if calendar:
                partial_update(calendar, {
                    'is_working': True,
                    'ts_last_sync': now(),
                })

        items = folders.filter(last_modified_time__gte=EWSDateTime.from_datetime(incremental_since))

        if ts_start:
            items = items.filter(end__gt=EWSDateTime.from_datetime(ts_start))
        if ts_stop:
            items = items.filter(end__lt=EWSDateTime.from_datetime(ts_start))

        items = items.only(*self.ITEM_FIELDS)

        return self.parse_exchange_items(items)

    def fetch_exchange_items(self, ts_start: datetime = None,
                             ts_stop: datetime = None) -> Sequence[InviteMessageParseDict]:

        folders = self.get_account_folders()
        if not folders:
            return []

        try:
            items = folders.view(
                start=EWSDateTime.from_datetime(ts_start), end=EWSDateTime.from_datetime(ts_stop)
            ).only(*self.ITEM_FIELDS)
        except AttributeError:
            valid_ids = [f.id for f in folders if not isinstance(f, ErrorItemNotFound)]
            invalid_ids = set(self.calendar_map) - set(valid_ids)
            Calendar.objects.filter(folder_id__in=invalid_ids, credentials=self.credentials).update(
                folder_id='', is_working=False
            )

            logger.info(
                'Got %s invalid calendars, disabling %s', len(invalid_ids), str(invalid_ids)
            )
        else:
            logger.info(
                'Got %s items from exchange from %s until %s', items.count(), ts_start, ts_stop
            )

        return self.parse_exchange_items(items)

    def parse_exchange_items(self, items: Sequence[Union[exchangelib.CalendarItem, Exception]]):
        parsed_items = []

        has_body = defaultdict(lambda: False)

        for item in items:

            if isinstance(item, Exception):
                logger.info('Parse exception for EWS item', exc_info=1)
                if settings.DEBUG:
                    print('Item error:', item)
                continue

            calendar = self.calendar_map.get(item.parent_folder_id.id)
            if not calendar or not calendar.endpoint_id:
                continue

            if item.type == 'RecurringMaster':
                continue  # TODO only for incremental mode without view() unpacking

            item_dict = EWSParser(item, calendar).parse()
            self.populate_meeting_dial_settings(item_dict, item_dict['endpoints'])

            has_body[calendar.username] = item_dict.get('subject') or item_dict.get('has_body')
            parsed_items.append(item_dict)

        for username in [u for u, value in has_body.items() if not value]:
            logger.warning('No items matched with either subject or body in calendar %s. '
                           'Set-CalendarProcessing needed?', username)

        if self.video_meetings_only:
            all_items, parsed_items = parsed_items, [item for item in parsed_items if item.get('dialstring')]
            if len(all_items) != len(parsed_items):
                logger.info('Removed %s meetings without any matched dial strings', len(all_items) - len(parsed_items))
        return parsed_items

    def get_remote_items(self, ts_start=None, ts_stop=None, incremental_since=None) -> Sequence[InviteMessageParseDict]:

        if incremental_since:
            return self.fetch_exchange_items_incremental(ts_start=ts_start, ts_stop=ts_stop, incremental_since=incremental_since)

        return self.fetch_exchange_items(ts_start=ts_start, ts_stop=ts_stop)


