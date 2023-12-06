# -*- coding: utf-8 -*-
import re
from datetime import timedelta
from sys import argv
from threading import Lock

import exchangelib
import exchangelib.services.common
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.test.testcases import SerializeMixin
from django.utils.timezone import now
from exchangelib import EWSDateTime
from exchangelib.protocol import BaseProtocol
from requests_mock import ANY

from customer.models import Customer
from endpoint.models import Endpoint
from endpoint.tests.mock_data import init as init_endpoint_mock
from meeting.models import Meeting
from provider.models.provider import Provider
from .fields import AutoDiscoverJSONField
from .handler import ExchangeHandler
from .models import EWSCredentials
from calendar_invite.models import Calendar
from api_key.models import OAuthCredential
from .tasks import poll_ews


# !!!
# settings.EXCHANGE_LIVE_TESTS must be set for these to be run. Requires online access
# !!!


class EWSKeyMixin:
    CLIENT_ID = 'a6fd7780-2e15-4adc-bb11-84f0ef767f68'
    TENANT_ID = '8d180419-72b8-4786-8c56-7adcc300da64'
    SECRET_KEY = '0Nh_or_.gW.52R21RwwnQNi-urv~h89UP9'

    ADMIN = 'AdeleV@mividasdev.onmicrosoft.com'
    PASSWORD = 'Uqd07MinVlRS'
    ROOM = 'room2@mividasdev.onmicrosoft.com'


class EWSTestCase(EWSKeyMixin, SerializeMixin, TestCase):
    lockfile = __file__


    BASIC_AUTODISCOVER_DATA = AutoDiscoverJSONField._decode('''
    {"service_endpoint": "https://outlook.office365.com/EWS/Exchange.asmx",
                         "auth_type": "basic",
                         "version": {"build": "15.20.3564.0", "api_version": "Exchange2016"}}
                         '''.strip())

    @classmethod
    def create_credentials(cls, customer):
        return EWSCredentials.objects.create(username=cls.ADMIN, password=cls.PASSWORD, customer=customer,
                                             autodiscover_data=cls.BASIC_AUTODISCOVER_DATA,
                                             is_working=True,
                                             )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = Customer.objects.create(title='test')
        cls.credentials = cls.create_credentials(cls.customer)

        username = cls.ADMIN
        cls.adele = cls.credentials.validate_account(username)[0]

    def setUp(self):
        super().setUp()
        init_endpoint_mock()

        from exchangelib import autodiscover
        autodiscover.clear_cache()  # need reset to mix oauth/basic for same domain

        self.provider = Provider.objects.get_active('external')
        self.endpoint = Endpoint.objects.create(customer=self.customer, title='test')

        self.mutex = Lock()

    def test_get_rooms(self):
        room_lists = self.credentials.get_room_lists()
        self.assertEqual(len(room_lists), 1)

        rooms = self.credentials.get_rooms(room_lists[0].email_address)
        self.assertGreater(len(rooms), 0)

        from .tasks import sync_ews_rooms
        sync_ews_rooms(self.credentials.pk)

    def test_count(self):
        self.assertEqual(EWSCredentials.objects.all().count(), 1)
        self.assertEqual(EWSCredentials.objects.first().username, self.ADMIN)

    def test_poll_ews(self):
        credentials = EWSCredentials.objects.all()

        def _poll():
            "re-implement to cache login status between runs"
            for cred_obj in credentials:
                handler = ExchangeHandler(cred_obj)
                handler.sync(now(), now() + timedelta(days=30))

        Calendar.objects.create(
            credentials=self.credentials,
            username=self.adele.identity.primary_smtp_address,
            folder_id=self.adele.calendar.id,
            endpoint=self.endpoint,
        )
        _poll()

        count0 = Meeting.objects.all().count()

        calendar = self.credentials.sync_room(self.ROOM)
        calendar.endpoint = self.endpoint
        calendar.save()

        _poll()

        self.assertEqual(EWSCredentials.objects.count(), 1)
        self.assertTrue(EWSCredentials.objects.first().is_working)

        count1 = Meeting.objects.all().count()
        self.assertGreater(count1, count0)
        self.assertTrue(count1)

        _poll()
        count2 = Meeting.objects.all().count()
        self.assertEqual(count1, count2)

        # new video
        item = exchangelib.CalendarItem(
            start=EWSDateTime.from_datetime(now()),
            end=EWSDateTime.from_datetime(now() + timedelta(hours=1)),
            account=self.adele,
            folder=self.adele.calendar,
            subject='Testmöte',
            body='sip:test@test.com',
        )
        item.save()

        _poll()
        count3 = Meeting.objects.all().count()
        self.assertEqual(count2 + 1, count3)

        # new non-video
        item = exchangelib.CalendarItem(
            start=EWSDateTime.from_datetime(now()),
            end=EWSDateTime.from_datetime(now() + timedelta(hours=1)),
            account=self.adele,
            folder=self.adele.calendar,
            subject='Testmöte',
            body='',
        )
        item.save()

        _poll()
        count3 = Meeting.objects.all().count()
        #  self.assertEqual(count2, count3)  # FIXME activate when filter is in place

        self.assertGreater(Meeting.objects.filter(endpoints__isnull=False).count(), 0)


class OauthTestCase(EWSTestCase):

    @classmethod
    def create_credentials(cls, customer):

        username = cls.ADMIN
        return EWSCredentials.objects.create(username=username, password=cls.PASSWORD, customer=customer,
                                             autodiscover_data=cls.BASIC_AUTODISCOVER_DATA,
                                             oauth_credential=OAuthCredential.objects.create(
                                                 customer=customer,
                                                 username=username,
                                                 client_id=cls.CLIENT_ID,
                                                 tenant_id=cls.TENANT_ID,
                                                 secret=cls.SECRET_KEY,
                                             ),
                                             )


class ExchangeAPITestCase(TestCase):

    def setUp(self):
        customer = Customer.objects.create(title='test')
        self.endpoint = Endpoint.objects.create(customer=customer, title='test', ip='127.0.0.1')
        User.objects.create_user(username='test', password='test', is_staff=True, is_superuser=True)

        self.client.login(username='test', password='test')

    def test_api(self):

        response = self.client.get('/json-api/v1/ews_credentials/')
        self.assertEqual(response.status_code, 200)

        data = {
            'username': EWSKeyMixin.ADMIN,
            'password': EWSKeyMixin.PASSWORD,
        }
        response = self.client.post('/json-api/v1/ews_credentials/', data)
        self.assertEqual(response.status_code, 201)


if settings.EXCHANGE_LIVE_TESTS:
    from conferencecenter.tests import mocker

    if mocker:
        mocker.register_uri('POST', re.compile(r'https://outlook.office365.com'), real_http=True)
        mocker.register_uri('POST', re.compile(r'https://login.microsoftonline.com'), real_http=True)
        mocker.register_uri(ANY, re.compile(r'https?://autodiscover.*/Autodiscover.xml'), real_http=True)
else:

    EWSTestCase = OauthTestCase = ExchangeAPITestCase = TestCase  # noqa
    if any(arg.startswith('exchange') for arg in argv):
        raise ValueError('settings.EXCHANGE_LIVE_TESTS must be True')


