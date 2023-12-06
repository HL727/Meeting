import json
import re
import sys
from datetime import timedelta
from importlib import reload
from sys import argv

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import clear_url_caches
from django.utils.timezone import now

from customer.models import Customer
from endpoint.models import Endpoint
from calendar_invite.models import Calendar, CalendarItem
from msgraph.handler import MSGraphHandler
from msgraph.models import MSGraphCredentials
from api_key.models import OAuthCredential
from provider.models.provider import Provider


class MSGraphKeyMixin:

    GETTING_STARTED_CLIENT_ID = '79d5b598-5fe9-4a10-b260-d06223a52e52'
    GETTING_STARTED_SECRET = 'ylqJWJF99?(~hcklMMF727?'

    CLIENT_ID = 'a6fd7780-2e15-4adc-bb11-84f0ef767f68'
    TENANT_ID = '8d180419-72b8-4786-8c56-7adcc300da64'
    SECRET_KEY = '0Nh_or_.gW.52R21RwwnQNi-urv~h89UP9'

    ADMIN = 'AdeleV@mividasdev.onmicrosoft.com'
    ROOM = 'room2@mividasdev.onmicrosoft.com'
    ROOM2 = 'room1@mividasdev.onmicrosoft.com'


class MSGraphTests(MSGraphKeyMixin, TestCase):

    customer: Customer

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = Customer.objects.create(title='test')
        cls.credentials = cls.create_credentials()

    @classmethod
    def create_credentials(cls):
        oauth_credentials = OAuthCredential.objects.create(
            customer=cls.customer,
            username=cls.ADMIN,
            client_id=MSGraphTests.CLIENT_ID,
            tenant_id=MSGraphTests.TENANT_ID,
            secret=MSGraphTests.SECRET_KEY,
            use_app_authorization=True,
            type=OAuthCredential.MSGRAPH,
        )
        return MSGraphCredentials.objects.create(oauth_credential=oauth_credentials, customer=cls.customer)

    def test_get_rooms(self):
        rooms_lists = self.credentials.get_room_lists()
        self.assertTrue(rooms_lists)

        self.credentials.get_rooms(rooms_lists[0]['emailAddress'])

    def test_sync_rooms(self):
        self.credentials.sync_rooms()
        self.assertTrue(Calendar.objects.filter(credentials=self.credentials))

    def test_get_events(self):

        events = self.credentials.api.calendar_view(self.ROOM, now(), now() + timedelta(days=14))
        self.assertTrue(events)

    def test_sync(self):
        endpoint = Endpoint.objects.create(customer=self.customer, hostname='endpoint')
        endpoint2 = Endpoint.objects.create(customer=self.customer, hostname='endpoint')

        calendar = Calendar.objects.create(credentials=self.credentials, username=self.ROOM, endpoint=endpoint)
        Calendar.objects.create(credentials=self.credentials, username=self.ROOM2, endpoint=endpoint2)

        handler = MSGraphHandler(self.credentials)
        result = handler.sync(now(), now() + timedelta(days=14))
        self.assertTrue(result.new)
        self.assertFalse(result.changed)
        self.assertFalse(result.removed)

        item = CalendarItem.objects.first()  # create duplicate
        item.meeting = item.meeting.copy()
        item.pk = None
        item.item_id += '0'
        item.save()

        from meeting.models import Meeting
        Meeting.objects.all().update(ts_start=now())

        self.assertTrue(endpoint.meetings.all())
        self.assertTrue(endpoint2.meetings.all())
        CalendarItem.objects.create(
            calendar=calendar,
            credentials=self.credentials,
            item_id='temp',
            meeting=Meeting.objects.create(
                customer=self.customer,
                provider=Provider.objects.get_active('external'),
                ts_start=now(),
                ts_stop=now() + timedelta(hours=1),
                backend_active=True,
            ),
        )

        result = handler.sync(now(), now() + timedelta(days=14))
        self.assertFalse(result.new)
        self.assertTrue(result.changed)
        self.assertTrue(result.removed)

        self.assertFalse(CalendarItem.objects.filter(pk=item.pk).first())


@override_settings(EPM_ENABLE_CALENDAR=True)
class MSGraphAPITestCase(TestCase):

    def setUp(self):
        self.customer = Customer.objects.create(title='test')
        User.objects.create_user(username='test', password='test', is_staff=True, is_superuser=True)

        self.client.login(username='test', password='test')

        reload(sys.modules['json_api.urls'])
        reload(sys.modules['conferencecenter.urls'])
        clear_url_caches()

    def test_api(self):

        response = self.client.get('/json-api/v1/msgraph_credentials/')
        self.assertEqual(response.status_code, 200)

        data = {
            'username': MSGraphKeyMixin.ADMIN,
            'oauth_credential': {
                'client_id': MSGraphKeyMixin.CLIENT_ID,
                'tenant_id': MSGraphKeyMixin.TENANT_ID,
                'secret': MSGraphKeyMixin.SECRET_KEY,
                'use_app_authorization': True,
            },
        }
        response = self.client.post('/json-api/v1/msgraph_credentials/',
                                    json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_oauth(self):

        response = self.client.get('/json-api/v1/msgraph_oauth/')
        self.assertEqual(response.status_code, 200)

        data = {
            'client_id': MSGraphKeyMixin.CLIENT_ID,
            'tenant_id': MSGraphKeyMixin.TENANT_ID,
            'secret': MSGraphKeyMixin.SECRET_KEY,
            'type': OAuthCredential.MSGRAPH,
        }
        response = self.client.post('/json-api/v1/msgraph_oauth/', data)
        self.assertEqual(response.status_code, 201)


if settings.EXCHANGE_LIVE_TESTS:
    from conferencecenter.tests import mocker

    if mocker:
        mocker.register_uri('GET', re.compile(r'https://graph.microsoft.com'), real_http=True)
        mocker.register_uri('POST', re.compile(r'https://endpoint:443/bookingsputxml'))
        mocker.register_uri('POST', re.compile(r'https://login.microsoftonline.com'), real_http=True)
else:
    MSGraphTests = TestCase  # noqa
    if any(arg.startswith('msgraph') for arg in argv):
        raise ValueError('settings.EXCHANGE_LIVE_TESTS must be True')
