import json
import os, django
from unittest import SkipTest

os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE', 'conferencecenter.settings'
) and django.setup()  # noqa


from provider.models.utils import date_format
from meeting.models import Meeting


from datetime import timedelta
from typing import List, Union
from urllib.parse import urljoin

import requests
from django.utils.timezone import now, localtime

from django.conf import settings
import unittest

from api_key.models import BookingAPIKey

from customer.models import Customer
from provider.models.acano import AcanoCluster
from provider.models.pexip import PexipCluster
from provider.ext_api.acano import AcanoAPI
from provider.ext_api.pexip import PexipAPI


API_KEY = settings.API_KEYS[0] or 'portal'
URL = settings.BASE_URL + '/api/v1/'

counter = 0

ts = date_format


class BookMeetingTestBase(unittest.TestCase):

    session: requests.Session
    meetings: List[str]
    customer: Customer
    api: Union[AcanoAPI, PexipAPI]
    api_key: str

    @classmethod
    def setUpClass(cls):
        cls.meetings = []
        super().setUpClass()
        session = requests.Session()
        session.headers['X-Mividas-Ou'] = cls.api_key
        session.headers['X-Mividas-Token'] = BookingAPIKey.objects.filter(enabled=True).first().key
        cls.session = session
        cls.api = cls.customer.get_api(allow_cached_values=True)
        if not settings.RUN_INTEGRATION_TESTS:
            print('Not running integration tests', __name__)
            raise SkipTest()

    @classmethod
    def tearDownClass(cls):
        for obj in cls.meetings:
            try:
                cls.session.post(urljoin(URL, 'meeting/unbook/{}/'.format(obj)))
            except Exception as e:
                print('Error unbooking meeting {}: {}'.format(obj, e))

        super().tearDownClass()

    def _book(self, rebook=None, **kwargs):
        global counter

        settings = {}
        if kwargs.get('settings'):
            settings.update(kwargs.pop('settings'))

        webinar = {}
        if kwargs.get('webinar'):
            webinar.update(kwargs.pop('webinar'))

        counter += 1
        data = {
            'title': 'Integration test nr {}:{} - {}'.format(
                localtime().hour, counter, self.customer
            ),
            'ts_start': ts(now()),
            'ts_stop': ts((now() + timedelta(minutes=10))),
            'creator': 'integration_test',
            'external_clients': 1,
            'internal_clients': 0,
            'settings': json.dumps(settings),
            'webinar': json.dumps(webinar),
            'confirm': 1,
            **kwargs,
        }
        if rebook:
            url = urljoin(URL, 'meeting/update/{}/'.format(rebook))
        else:
            url = urljoin(URL, 'meeting/')

        response = self.session.post(url, data)
        if response.status_code != 200:
            self.fail(response.json())

        api_id = response.json()['meeting_id']
        self.meetings.append(api_id)
        print('Booked meeting {}'.format(api_id))

        return api_id

    def _check_data(self, api_id):
        meeting = Meeting.objects.get_by_id_key(api_id)
        from supporthelpers.forms import CoSpaceForm

        data = CoSpaceForm(cospace=meeting.provider_ref2).load(self.customer)

        self.assertEqual(meeting.provider_ref, data['call_id'])
        self.assertEqual(meeting.password, data['password'])
        self.assertEqual(meeting.moderator_password, data.get('moderator_password', ''))

        api_data = meeting.as_dict()
        self.assertEqual(meeting.password, api_data['password'])
        self.assertEqual(meeting.moderator_password, api_data['moderator_password'])
        self.assertEqual(meeting.join_url, api_data['web_url'])

        m2 = Meeting.objects.get_by_id_key(api_id)
        m2.is_moderator = True

        api_data2 = m2.as_dict()
        self.assertEqual(m2.moderator_password, api_data2['moderator_password'])
        self.assertEqual(m2.join_url, api_data2['web_url'])

        if self.api.cluster.is_acano:
            methods = self.api.get_cospace_accessmethods(meeting.provider_ref2)
            if not methods and m2.moderator_password:
                self.fail('No access method for moderator')
            elif methods:
                real_secret = self.api.get_secret_for_access_method(
                    meeting.provider_ref2, methods[0]['id']
                )
                self.assertTrue(real_secret)
                self.assertIn(
                    real_secret,
                    api_data2['web_url'],
                )
                self.assertIn(
                    real_secret,
                    api_data2['message'],
                )
                self.assertIn(
                    real_secret,
                    m2.join_url,
                )

    def _update_settings(self, api_id, **kwargs):

        data = {
            **kwargs,
        }

        response = self.session.post(urljoin(URL, 'meeting/settings/{}/'.format(api_id)), data)
        if response.status_code != 200:
            self.fail(response.json())

        new_api_id = response.json()['meeting_id']
        self.meetings.append(new_api_id)
        print('Rebooked meeting {} to {}'.format(api_id, new_api_id))

        return new_api_id

    def test_book(self, initial_kwargs=None):
        api_id = self._book(**(initial_kwargs or {}))
        self._check_data(api_id)

        rebook_api_id = self._book(rebook=api_id, **(initial_kwargs or {}))
        self._check_data(rebook_api_id)

        # change set both
        update_api_id = self._update_settings(
            rebook_api_id,
            password='1234',
            moderator_password='2345',
        )
        self._check_data(update_api_id)

        # change only guest
        update_api_id = self._update_settings(
            rebook_api_id,
            password='1233',
            moderator_password='2345',
        )
        self._check_data(update_api_id)

        # change only moderator
        update_api_id = self._update_settings(
            rebook_api_id,
            password='1233',
            moderator_password='2346',
        )
        self._check_data(update_api_id)

        # reset moderator
        update_api_id2 = self._update_settings(
            update_api_id,
            password='1235',
            moderator_password='',
        )
        self._check_data(update_api_id2)

    def test_book_initial_moderator(self):
        self.test_book(initial_kwargs=dict(moderator_password='3456'))


def get_cluster_test_classes():
    new_test_classes = {}
    for cluster in AcanoCluster.objects.all():
        for customer in Customer.objects.filter(lifesize_provider=cluster):
            cur = get_customer_class('Acano', customer)
            if cur:
                new_test_classes[cur.__name__] = cur

    for cluster in PexipCluster.objects.all():
        for customer in Customer.objects.filter(lifesize_provider=cluster):
            cur = get_customer_class('Pexip', customer)
            if cur:
                new_test_classes[cur.__name__] = cur

    return new_test_classes


def get_customer_class(prefix, customer):
    keys = customer.get_non_domain_keys()
    if not keys:
        return

    name = prefix + 'CustomerTestClass'
    cur = type(
        name,
        (BookMeetingTestBase,),  # noqa
        {'api_key': customer.get_non_domain_keys()[0], 'customer': customer},
    )
    return cur


if settings.RUN_INTEGRATION_TESTS:
    locals().update(get_cluster_test_classes())
del BookMeetingTestBase  # noqa
