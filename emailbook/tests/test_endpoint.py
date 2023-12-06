from django.utils.timezone import now

from calendar_invite.tests import _get_full_message, _get_icalendar
from conferencecenter.tests.base import ConferenceBaseTest
from emailbook.handler import EmailHandler
from endpoint.models import CustomerDomain


class EndpointTestCase(ConferenceBaseTest):

    def setUp(self):
        self._init()
        super().setUp()

        from endpoint.models import Endpoint

        self.endpoint = Endpoint.objects.create(customer=self.customer, manufacturer=10)
        self.endpoint2 = Endpoint.objects.create(customer=self.customer, manufacturer=10)

    def test_book_multiple(self):

        from endpoint.models import EndpointMeetingParticipant

        handler = EmailHandler(_get_full_message(mode=self.endpoint.email_key, cc=self.endpoint2.email_key, vcard=False).as_string())

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)
        self.assertEqual(content['mode'], 'external')
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint).count(), 1)
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint2).count(), 1)

    def test_extend_and_unbook(self):
        "add more than one endpoint in multiple emails"
        from endpoint.models import EndpointMeetingParticipant

        ts_start = now()

        calendar = _get_icalendar(ts_start=ts_start)
        cancelled = _get_icalendar(ts_start=ts_start, status='CANCELLED')

        handler = EmailHandler(_get_full_message(mode=self.endpoint.email_key, calendar=calendar, vcard=False).as_string())

        valid, content, error = handler.handle_locked()
        self.assertTrue(valid, error or 'Invalid handling of email')
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint).count(), 1)

        # add nr 2
        handler = EmailHandler(_get_full_message(mode=self.endpoint2.email_key, calendar=calendar, vcard=False).as_string())

        valid, content, error = handler.handle_locked()
        self.assertTrue(valid, error or 'Invalid handling of email')
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint2).count(), 1)
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint).count(), 1)

        # cancel nr 1
        handler = EmailHandler(
            _get_full_message(mode=self.endpoint.email_key, vcard=False, calendar=cancelled).as_string())

        valid, content, error = handler.handle_locked()
        self.assertTrue(valid, error or 'Invalid handling of email')

        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint).count(), 0)
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint2).count(), 1)
        self.assertEqual(content['meeting'].backend_active, True)

        # cancel nr 2
        handler = EmailHandler(
            _get_full_message(mode=self.endpoint2.email_key, vcard=False, calendar=cancelled).as_string())

        valid, content, error = handler.handle_locked()
        self.assertTrue(valid, error or 'Invalid handling of email')

        self.assertEqual(content['meeting'].backend_active, False)
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint).count(), 0)
        # not deleted, but left for archive:
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint2).count(), 1)


    def test_domain_book(self):

        from endpoint.models import EndpointMeetingParticipant
        from customer.models import CustomerKey

        CustomerKey.objects.filter(shared_key='example.org').delete()
        handler = EmailHandler(_get_full_message(mode=self.endpoint.email_key, vcard=False).as_string())

        # invalid
        valid, content, error = handler.handle_locked()
        self.assertEqual(valid, False)
        self.assertEqual(content.get('endpoints', []), [])
        self.assertEqual(EndpointMeetingParticipant.objects.filter(endpoint=self.endpoint).count(), 0)

        # valid
        CustomerDomain.objects.create(customer=self.customer, domain='example.org')

        valid, content, error = handler.handle_locked()
        self.assertEqual(error, '')
        self.assertEqual(valid, True)
        self.assertEqual(content['mode'], 'external')
        self.assertTrue(content['endpoints'])
        self.assertEqual(EndpointMeetingParticipant.objects.filter(meeting=content['meeting'], endpoint=self.endpoint).count(), 1)
