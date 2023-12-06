from email.parser import Parser
from email.utils import getaddresses, parseaddr

import tnefparse

from django.conf import settings
from django.utils.encoding import force_text
from email.header import decode_header
from sentry_sdk import capture_exception

from calendar_invite.parser import InviteMessageParser, fix_subject
from calendar_invite.types import InviteMessageParseDict


class EmailParser(InviteMessageParser):

    def __init__(self, message_string):
        self.msg = Parser().parsestr(message_string)
        super().__init__()

    def decode_name(self, encoded_name, email):

        name, encoding = decode_header(encoded_name)[0]

        if isinstance(name, str):
            return name, email
        return name.decode(encoding or 'latin1'), email

    def parse(self) -> InviteMessageParseDict:

        result = InviteMessageParseDict(
            subject='',
            creator_name='',
            creator='',
            participants=[],
            skype_conference='',
            ts_start=None,
            ts_stop=None,
            uid='',
            recurrence_id='',
            dialstring='',
            recurring='',
            recurring_exceptions='',
            envelope='',
            error=None,
            cancelled=False,
            is_private=False,
            has_body=False,
        )

        result.update(self.parse_headers())

        try:
            self.parse_payloads(result)
        except Exception as e:
            if settings.TEST_MODE or settings.DEBUG:
                raise
            capture_exception()
            result['error'] = str(e)
        return result

    def parse_payloads(self, result):

        text_data = {}  # use text content as fallback

        orig_allow_scrape = self.allow_scrape

        for payload in self.msg.walk():

            if result.get('dialstring'):
                self.allow_scrape = False

            if isinstance(payload, str):
                text_data = self.parse_text(payload) or text_data
                continue

            content_type = payload.get_content_type()

            if content_type == 'application/ms-tnef':
                data, new_text_data = self.parse_tnef(payload)
                if data:
                    result.update(data)
                text_data.update(new_text_data)

            if content_type == 'text/calendar':
                data = self.parse_calendar(payload.get_payload(decode=True))
                result.update(data)
            elif content_type == 'text/x-vcard':
                data = self.parse_vcard(payload.get_payload(decode=True))
                result.update(data)
            elif content_type in ('text/html', 'text/plain'):
                new_text_data = self.parse_text(payload.get_payload(decode=True))
                result['has_body'] = True
                if new_text_data:
                    text_data = {**new_text_data, **text_data}

        if not result['dialstring'] and text_data:
            result.update(text_data)

        self.maybe_use_fallback_dialstring(result)

        self.allow_scrape = orig_allow_scrape

        return result

    def parse_tnef(self, payload):
        result = {}
        text_data = {}
        try:
            tnef = tnefparse.TNEF(payload.get_payload(decode=True))
            text_data = self.parse_text(force_text(tnef.body)) or text_data
        except UnicodeError:
            pass
        else:
            calendar_attachments = [a for a in tnef.attachments if a.name.endswith('.ics')]
            for cal in calendar_attachments:
                try:
                    data = self.parse_calendar(force_text(cal.data))
                except Exception:
                    if settings.TEST_MODE:
                        raise
                    capture_exception()
                else:
                    result.update(data)

        return result, text_data

    def parse_headers(self):

        msg = self.msg
        try:
            name, email = self.decode_name(*parseaddr(msg['Reply-To']))
        except Exception:
            name, email = '', None

        if not email:
            name, email = self.decode_name(*parseaddr(msg['From']))

        participants = []
        for header in ('Delivered-To', 'X-Original-To', 'To', 'CC', 'BCC'):
            participants.extend([self.decode_name(*s)[1] for s in getaddresses(msg.get_all(header, ()))])

        encoded_subject, encoding = decode_header(msg['Subject'])[0]
        if isinstance(encoded_subject, bytes):
            subject = encoded_subject.decode(encoding or 'latin1').strip()
        else:
            subject = encoded_subject.strip()

        subject = fix_subject(subject)

        return {
            'creator_name': name,
            'creator': email,
            'subject': subject[:100],
            'participants': participants,
            'is_private': (msg['Sensitivity'] or '').lower() == 'private',
            'envelope': (self.msg.get('Message-ID', '') or self.msg.get('Envelope', '')).strip(),
        }


