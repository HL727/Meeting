import json

from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from pytz import utc

from calendar_invite.tests import _get_full_message, _get_icalendar
from conferencecenter.tests.base import ConferenceBaseTest
from debuglog.models import EmailLog
from emailbook.handler import EmailHandler
from emailbook.models import EmailMeeting
from endpoint.models import Endpoint
from provider.models.utils import date_format


class HandlerTestCase(ConferenceBaseTest):

    def setUp(self):
        self._init()

        #self.provider = Provider.objects.create(type=0, subtype=1, ip='127.0.0.1', is_standard=True)
        #self.customer = Customer.objects.create(title='test', shared_key='example.org', lifesize_provider=self.provider)

    def test_redacted(self):

        msg = _get_full_message('endpoint', calendar=False).as_string()
        handler = EmailHandler(msg)
        valid, content, error = handler.validate()

        self.assertEqual(content.get('mode'), '')
        self.assertEqual(content.get('no_invite'), True)

        endpoint = Endpoint.objects.create(customer=self.customer, title='Endpoint', email_key='endpoint')

        handler = EmailHandler(msg)
        valid, content, error = handler.validate()
        self.assertEqual(content.get('mode'), 'external')

        self.assertEqual(EmailLog.objects.all().count(), 0)
        response = self.client.post('/email/book/', {'message': msg})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(EmailLog.objects.all().count(), 1)
        log = EmailLog.objects.all().first()
        self.assertEqual(log.content_text, 'External meeting without calendar attachment. Redacted.')

        msg = _get_full_message('endpoint', calendar=True).as_string()
        response = self.client.post('/email/book/', {'message': msg})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(endpoint.get_bookings()), 1)

    def test_handle_private(self):

        endpoint = Endpoint.objects.create(customer=self.customer, title='Endpoint', email_key='endpoint')

        msg = _get_full_message('endpoint', calendar=_get_icalendar(is_private=True)).as_string()
        response = self.client.post('/email/book/', {'message': msg})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(endpoint.get_bookings()), 1)
        self.assertEqual(endpoint.get_bookings()[0].title, '-- Private --')

        self.assertEqual(EmailLog.objects.all().count(), 1)
        log = EmailLog.objects.all().first()
        self.assertEqual(log.content_text, 'Private meeting. Redacted.')
        self.assertEqual(log.subject, '-- Private --')

    def test_handle_valid(self):
        ts_start = now().replace(microsecond=0)

        calendar = _get_icalendar(ts_start.replace(tzinfo=None).replace(tzinfo=utc), timezone=True)

        handler = EmailHandler(_get_full_message(calendar=calendar).as_string())

        valid, content, error = handler.handle_locked()
        self.assertEqual(valid, True)
        self.assertEqual(content['email_meeting'].meeting.ts_start, ts_start)

    def test_ical_with_timezone(self):
        content = '''
BEGIN:VCALENDAR
METHOD:REQUEST
PRODID:Microsoft Exchange Server 2010
VERSION:2.0
BEGIN:VTIMEZONE
TZID:W. Europe Standard Time
BEGIN:STANDARD
DTSTART:16010101T030000
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
RRULE:FREQ=YEARLY;INTERVAL=1;BYDAY=-1SU;BYMONTH=10
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:16010101T020000
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
RRULE:FREQ=YEARLY;INTERVAL=1;BYDAY=-1SU;BYMONTH=3
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
ORGANIZER;CN=Christian Wåhlin:mailto:christian.wahlin@mividas.com
DESCRIPTION;LANGUAGE=sv-SE:1234@example.org&lt;mailto:1234@exampl
 e.org&gt;\n
UID:040000008200E00074C5B7101A82E0080000000060A3AA222626D701000000000000000
 0100000008840C8B0DE76774B86E896D51817EAC7
SUMMARY;LANGUAGE=sv-SE:SMTP
RECURRENCE-ID;TZID=W. Europe Standard Time:20210331T103000
DTSTART;TZID=W. Europe Standard Time:20210331T103000
DTEND;TZID=W. Europe Standard Time:20210331T104500
RRULE:FREQ=DAILY;COUNT=5
CLASS:PUBLIC
PRIORITY:5
DTSTAMP:20210331T103757Z
TRANSP:OPAQUE
STATUS:CONFIRMED
SEQUENCE:2
LOCATION;LANGUAGE=sv-SE:
X-MICROSOFT-CDO-APPT-SEQUENCE:2
X-MICROSOFT-CDO-OWNERAPPTID:-1228982299
X-MICROSOFT-CDO-BUSYSTATUS:TENTATIVE
X-MICROSOFT-CDO-INTENDEDSTATUS:BUSY
X-MICROSOFT-CDO-ALLDAYEVENT:FALSE
X-MICROSOFT-CDO-IMPORTANCE:1
X-MICROSOFT-CDO-INSTTYPE:0
X-MICROSOFT-DONOTFORWARDMEETING:FALSE
X-MICROSOFT-DISALLOW-COUNTER:FALSE
X-MICROSOFT-LOCATIONS:[]
END:VEVENT
END:VCALENDAR
        '''.strip()

        handler = EmailHandler(_get_full_message(calendar=content).as_string())
        valid, content, error = handler.validate()

        self.assertTrue(valid)
        self.assertEqual(content['ts_start'], parse_datetime('2021-03-31T10:30:00+0200'))
        self.assertEqual(content['recurrence_id'], date_format(parse_datetime('2021-03-31T10:30:00+0200')))

    def test_handle_invalid(self):

        handler = EmailHandler(_get_full_message(calendar=False).as_string())

        valid, content, error = handler.handle_locked()
        self.assertEqual(valid, False)

    def test_handle_valid_record(self):

        handler = EmailHandler(_get_full_message().as_string())

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)
        self.assertEqual(content['mode'], 'record')

    def test_handle_valid_rebook(self):

        message = _get_full_message().as_string()
        handler = EmailHandler(message)

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)
        self.assertEqual(content['mode'], 'record')

        email_meeting = content['email_meeting']

        email_body = handler.get_confirmation_message(email_meeting, content)
        if settings.LANGUAGE_CODE != 'en-us':
            self.assertNotIn('var redan bokat', email_body)

        # duplicate
        handler = EmailHandler(message)

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)
        self.assertEqual(content['mode'], 'record')
        self.assertEqual(content.get('is_duplicate'), True)

        email_meeting2 = content['email_meeting']

        self.assertEqual(email_meeting.meeting_id, email_meeting2.meeting_id)

        email_body = handler.get_confirmation_message(email_meeting, content)
        if settings.LANGUAGE_CODE != 'en-us':
            self.assertIn('var redan bokat', email_body)

        # rebook
        handler = EmailHandler(_get_full_message(mode='record+stream').as_string())

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)
        self.assertEqual(content['mode'], 'record+stream')
        self.assertTrue(content.get('rebook'))

        email_meeting2 = content['email_meeting']

        self.assertNotEqual(email_meeting.meeting_id, email_meeting2.meeting_id)

        email_body = handler.get_confirmation_message(email_meeting, content)
        if settings.LANGUAGE_CODE != 'en-us':
            self.assertNotIn('var redan bokat', email_body)
            self.assertIn('har bokats om', email_body)


    def test_handle_valid_record_stream(self):

        handler = EmailHandler(_get_full_message(mode='record+stream').as_string())

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)
        self.assertEqual(content['mode'], 'record+stream')

        email_meeting = content['email_meeting']
        self.assertEqual(json.loads(email_meeting.meeting.recording)['is_live'], True)

    def test_handle_valid_stream(self):

        handler = EmailHandler(_get_full_message(mode='stream').as_string())

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)
        self.assertEqual(content['mode'], 'stream')

    def test_http(self):
        c = self.client
        count = EmailMeeting.objects.all().count()

        response = c.post('/email/book/', dict(message=_get_full_message().as_string()))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(json.loads(response.content)['status'], 'OK')

        self.assertEqual(EmailMeeting.objects.all().count(), count + 1)

    def test_http_auth(self):
        with self.settings(EMAIL_REQUIRE_EXTENDED_KEY=True, EXTENDED_API_KEY='test'):
            response = self.client.post('/email/book/', dict(message=_get_full_message().as_string()))
            self.assertEqual(response.status_code, 403)

            response = self.client.post(
                '/email/book/',
                dict(message=_get_full_message().as_string()),
                HTTP_X_MIVIDAS_TOKEN='test',
            )
            self.assertEqual(response.status_code, 200)

    def test_handle_valid_book_and_unbook(self):

        handler = EmailHandler(_get_full_message(mode='book', vcard=False).as_string())

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)

        e_meeting = content['email_meeting']

        msg = handler.get_confirmation_message(e_meeting, content)

        unbook_url = e_meeting.get_unbook_url()
        self.assertTrue(unbook_url)
        self.assertIn(unbook_url, msg)

        response = self.client.get(e_meeting.get_unbook_url())
        self.assertEqual(response.status_code, 200)

        response = self.client.post(e_meeting.get_unbook_url(), {'unbook': 1})
        self.assertEqual(response.status_code, 200)

        e_meeting = EmailMeeting.objects.get(pk=e_meeting.pk)
        self.assertTrue(e_meeting.ts_deleted)
