# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Sequence

from django.conf import settings
from django.utils.timezone import now

from calendar_invite.handler import CalendarInviteHandler
from provider.exceptions import NotFound
from shared.utils import partial_update
from .models import MSGraphCredentials
from .parser import MSGraphParser
from calendar_invite.types import InviteMessageParseDict


logger = logging.getLogger(__name__)


class MSGraphHandler(CalendarInviteHandler):

    credentials: MSGraphCredentials

    def __init__(self, cred_obj):
        super().__init__(cred_obj)
        self.api = cred_obj.get_api()

    def fetch_msgraph_items_incremental(self, ts_start: datetime = None,
                             ts_stop: datetime = None,
                             incremental_since: datetime = None) -> Sequence[InviteMessageParseDict]:

        if not incremental_since:
            raise ValueError('Incremental value is required')

        # TODO watch
        result = []
        for calendar in self.calendars:
            if '@' not in calendar.username:  # old invalid data may still be present
                continue

            try:
                cur = self.api.calendar_view(calendar.username, ts_start, ts_stop)
                partial_update(calendar, {
                    'is_working': True,
                    'ts_last_sync': now(),
                })
                logger.info('Fetched %s items from calendar %s', len(cur), calendar.username)
            except NotFound as e:
                logger.warning('Could not fetch incremental items for calendar %s: %s', calendar.username, e)
                partial_update(calendar, {
                    'is_working': False,
                })
                calendar.save(update_fields=['is_working'])
                continue
            result.extend(self.parse_msgraph_items(cur, calendar))

        return result

    def fetch_msgraph_items(self, ts_start: datetime = None,
                             ts_stop: datetime = None) -> Sequence[InviteMessageParseDict]:

        result = []
        for calendar in self.calendars:
            try:
                cur = self.api.calendar_view(calendar.username, ts_start, ts_stop)
                partial_update(calendar, {
                    'is_working': True,
                    'ts_last_sync': now(),
                })
                logger.info('Fetched %s items from calendar %s', len(cur), calendar.username)
            except NotFound as e:
                logger.warning('Could not fetch incremental items for calendar %s: %s', calendar.username, e)
                partial_update(calendar, {
                    'is_working': False,
                })
                continue
            result.extend(self.parse_msgraph_items(cur, calendar))

        return result

    def parse_msgraph_items(self, items, calendar):
        parsed_items = []
        for item in items:

            if isinstance(item, Exception):
                if settings.DEBUG:
                    print('Item error:', item)
                continue

            if not calendar or not calendar.endpoint_id:
                continue

            if item['type'] == 'recurringMaster':
                continue  # TODO only for incremental mode without view() unpacking

            item_dict = MSGraphParser(item, calendar).parse()
            self.populate_meeting_dial_settings(item_dict, item_dict['endpoints'])

            parsed_items.append(item_dict)

        if items and not any(item['subject'] or item['has_body'] for item in parsed_items):
            logger.warning('No items matched with either subject or body in calendar %s. '
                           'Set-CalendarProcessing needed?', calendar.username)

        if self.video_meetings_only:
            all_items, parsed_items = parsed_items, [item for item in parsed_items if item.get('dialstring')]
            if len(all_items) != len(parsed_items):
                logger.info('Removed %s meetings without any matched dial strings', len(all_items) - len(parsed_items))

        return parsed_items

    def get_remote_items(self, ts_start=None, ts_stop=None, incremental_since=None):

        if incremental_since:
            return self.fetch_msgraph_items_incremental(ts_start=ts_start, ts_stop=ts_stop, incremental_since=incremental_since)

        return self.fetch_msgraph_items(ts_start=ts_start, ts_stop=ts_stop)
