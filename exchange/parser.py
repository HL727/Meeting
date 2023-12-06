# -*- coding: utf-8 -*-
from exchangelib import CalendarItem

from calendar_invite.parser import InviteMessageParser, fix_subject
from calendar_invite.types import CalendarInviteParseDict
from provider.models.utils import date_format


class EWSParser(InviteMessageParser):

    def __init__(self, item: CalendarItem, calendar=None):
        self.item = item
        self.calendar = calendar or None
        super().__init__()

    def parse(self) -> CalendarInviteParseDict:
        participants = [a.mailbox.email_address for a in self.item.required_attendees] if self.item.required_attendees else []
        if self.item.optional_attendees:
            participants += [a.mailbox.email_address for a in self.item.optional_attendees]

        if self.item.is_recurring:
            recurrence_id = date_format(self.item.original_start or self.item.start)
        else:
            recurrence_id = ''

        result = CalendarInviteParseDict(
             creator_name=self.item.organizer.name if self.item.organizer else '',
             creator=self.item.organizer.email_address if self.item.organizer else '',
             subject=fix_subject(self.item.subject or '')[:100],
             participants=participants,
             envelope=self.item.id,
             changekey=self.item.changekey,
             skype_conference='',
             ts_start=self.item.start,
             ts_stop=self.item.end,
             timezone=self.item.start.tzinfo,
             uid=self.item.uid,
             recurrence_id=recurrence_id,
             dialstring='',
             is_recurring=self.item.is_recurring,
             recurring=None,
             is_private=self.item.sensitivity in ('private', 'confidential'),
             recurring_exceptions='',
             error=None,
             calendar=self.calendar,
             endpoints=[self.calendar.endpoint] if self.calendar and self.calendar.endpoint else None,
             cancelled=self.item.is_cancelled,
             has_body=False
        )

        # Reuse EmailParser.parse_text() and EmailParser.parse_calendar()
        if self.item.body:
            result['has_body'] = True
            result.update(self.parse_text(self.item.body))

        if self.item.location:
            result.update(self.parse_text(self.item.location))

        if self.item.mime_content:
            result.update(self.parse_calendar(self.item.mime_content))

        self.maybe_use_fallback_dialstring(result)

        return result

