import re
from datetime import datetime

from django.test.testcases import TestCase
from django.utils.timezone import now

from calendar_invite.tests import _get_full_message, _get_icalendar
from emailbook.parser import EmailParser
from provider.models.utils import date_format


class HeaderTest(TestCase):

    def test_headers(self):

        message = re.sub(r'^ *', '', '''
        From: Test <test@example.org>
        Subject: Subject
        To: other@example.org; record@book.example.org
        CC: cc@example.org
        Sensitivity: private
        BCC: bcc@example.org
        ''', flags=re.MULTILINE).strip()

        result = EmailParser(message).parse_headers()

        self.assertEqual(result['creator_name'], 'Test')
        self.assertEqual(result['creator'], 'test@example.org')
        self.assertEqual(result['subject'], 'Subject')
        self.assertEqual(result['is_private'], True)
        self.assertEqual(result['participants'], ['other@example.org', '', 'record@book.example.org', 'cc@example.org', 'bcc@example.org'])  # record should be included? TODO fix empty value

    def test_subject(self):

        message = re.sub(r'^ *', '', '''
        From: Test <test@example.org>
        Subject: Re: SV: Fwd: Re: Subject
        To: other@example.org; record@book.example.org
        CC: cc@example.org
        BCC: bcc@example.org
        ''', flags=re.MULTILINE).strip()

        result = EmailParser(message).parse_headers()

        self.assertEqual(result['subject'], 'Subject')

        message = re.sub(r'^ *', '', '''
        From: Test <test@example.org>
        Subject: Subject
        To: other@example.org; record@book.example.org
        CC: cc@example.org
        BCC: bcc@example.org
        ''', flags=re.MULTILINE).strip()

        result = EmailParser(message).parse_headers()

        self.assertEqual(result['subject'], 'Subject')

    def test_full_parse(self):

        result = EmailParser(_get_full_message().as_string()).parse()
        self.assertTrue(isinstance(result['ts_start'], datetime))
        self.assertEqual(result['uid'], 'uid1@example.com')

    def test_full_parse_rrule(self):

        ts = now()
        calendar = _get_icalendar(ts_start=ts, extra_ical='RRULE:FREQ=DAILY;COUNT=10')
        result = EmailParser(_get_full_message(calendar=calendar).as_string()).parse()
        self.assertTrue(result['recurring'])
        self.assertEqual(result['recurrence_id'], date_format(ts))

    def test_parse_private(self):

        result = EmailParser(_get_full_message(calendar=_get_icalendar(is_private=True)).as_string()).parse()
        self.assertTrue(isinstance(result['ts_start'], datetime))
        self.assertEqual(result['is_private'], True)
