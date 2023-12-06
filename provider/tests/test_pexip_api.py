import json
from datetime import timedelta

from django.utils.timezone import now
from rest_framework.test import APITestCase

from conferencecenter.tests.mock_data import state as mock_state
from customer.models import Customer
from meeting.models import Meeting
from numberseries.models import NumberRange
from organization.models import OrganizationUnit
from provider.models.pexip import PexipSpace
from provider.tests.test_pexip import PexipBaseTest


class ConferenceBaseTest(PexipBaseTest):

    def get_sent_api_value(self, key: str, index=0):
        reqs = self._mock_requests.find_urls_all('POST configuration/v1/conference/')
        self.assertTrue(reqs)
        req_data = json.loads(reqs[index].data)
        return req_data[key]


class ConferenceCreateTest(ConferenceBaseTest):

    @property
    def url(self):
        return '/json-api/v1/cospace-pexip/'

    def test_increase(self):
        data = {
            'name': 'test2',
            'call_id_generation_method': 'increase',
            'service_type': 'conference',
        }

        number_range = self.customer.get_api().get_static_room_number_range()
        number_range.start = 3000
        number_range.save()
        self.assertEqual(number_range.next_number, None)

        response = self.client.post(self.url, data)
        self.assertContains(response, 'VMR_1', status_code=201)

        number_range = self.customer.get_api().get_static_room_number_range()

        number_range.refresh_from_db()
        self.assertEqual(number_range.next_number, 3001)

        aliases = self.get_sent_api_value('aliases') or []
        self.assertEqual(aliases[0]['alias'], '3000')

    def test_random(self):
        data = {
            'name': 'test2',
            'call_id_generation_method': 'random',
            'service_type': 'conference',
            'organization_path': 'Test1 / Test 2',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, 'VMR_1', status_code=201)

        number_range = self.customer.get_api().get_static_room_number_range()
        self.assertEqual(number_range.next_number, None)

        self.assertEqual(OrganizationUnit.objects.filter(customer=self.customer).count(), 2)
        self.assertEqual(PexipSpace.objects.filter(organization_unit__isnull=False).count(), 1)

        aliases = self.get_sent_api_value('aliases') or []
        self.assertEqual(len(aliases), 2)

    def test_manual(self):
        data = {
            'name': 'test2',
            'aliases': [{'alias': 'test'}],
            'service_type': 'conference',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, 'VMR_1', status_code=201)

        number_range = self.customer.get_api().get_static_room_number_range()
        self.assertEqual(number_range.next_number, None)

    def test_ivr_theme(self):

        c_settings = self.pexip.cluster.get_cluster_settings(self.customer)
        c_settings.theme_profile = '/admin/api/configuration/v1/ivr_theme/1/'
        c_settings.save()

        data = {
            'name': 'test2',
            'aliases': [{'alias': 'test'}],
            'service_type': 'conference',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, 'VMR_1', status_code=201)

        self.assertEqual(self.get_sent_api_value('ivr_theme'), c_settings.theme_profile)


class ConferenceUpdateTest(PexipBaseTest, APITestCase):

    @property
    def url(self):
        return '/json-api/v1/cospace-pexip/123/'

    def test_update(self):
        response = self.client.patch(self.url, json.dumps(
            {
                'name': 'test2',
                'aliases': [
                    {'alias': 'test2'},
                    {'alias': '65432@local.example.org', 'description': 'new'},
                ],
            }), content_type='application/json'
        )
        self.assertContains(response, 'VMR_1', status_code=200)
        self.assertTrue(self._mock_requests.find_url('DELETE configuration/v1/conference_alias/2/'))
        self.assertTrue(self._mock_requests.find_url('PATCH configuration/v1/conference_alias/1/'))
        self.assertTrue(self._mock_requests.find_url('POST configuration/v1/conference_alias/'))

    def test_update_tenant(self):
        response = self.client.patch(self.url, {'tenant': 'invalid'})
        self.assertEqual(response.status_code, 400)

        response = self.client.patch(self.url, {'tenant': self.customer.get_pexip_tenant_id()})
        self.assertContains(response, 'VMR_1', status_code=200)


class ConferenceBulkTest(ConferenceBaseTest):
    def test_authentication(self):
        c = self.client

        data = {}
        result = c.post(self.bulk_url, data)

        self.assertEqual(result.status_code, 400)

        c.logout()

        result = c.post(self.bulk_url, data)

        # self.assertEqual(result.status_code, 403)

    def _set_url_state(self, state):
        mock_state.url_state = state

    def _get_multiple_cospace_data(self):
        return [{
            'service_type': 'ConferenceTestType1',
            'name': 'ConferenceTestTitle1',
            'description':  'ConferenceTestDesc1',
            'host_pin': 'ConferenceTestHostPin1',
            'allow_guests': False,
            'guest_pin': ''
        },
        {
            'service_type': 'ConferenceTestType2',
            'name': 'ConferenceTestTitle2',
            'description':  'ConferenceTestDesc2',
            'host_pin': 'ConferenceTestHostPin2',
            'allow_guests': False,
            'organization_path': 'Test1 / Test 2',
            'guest_pin': '',
            'aliases': [
                {'alias': '123'},
                {'alias': 'test'},
            ]
        }]

    def test_create_approved(self):
        c = self.client

        static_range = self.api.get_static_room_number_range()
        static_range.start = 3000
        static_range.save()
        self.assertEqual(len(NumberRange.objects.all()), 1)

        data = {
            'conferences': self._get_multiple_cospace_data(),
        }

        result = c.post(self.bulk_url, json.dumps(data), content_type='application/json')
        self.assertEqual(result.status_code, 400)

        # increase
        data['call_id_generation_method'] = 'increase'
        result = c.post(self.bulk_url, json.dumps(data), content_type='application/json')

        self.assertEqual(result.status_code, 201)

        reqs = self._mock_requests.find_urls_all('POST configuration/v1/conference/')
        self.assertTrue(reqs)

        aliases = self.get_sent_api_value('aliases') or []
        self.assertEqual(len(aliases), 2)
        self.assertFalse(any(a['alias'] == '3000' for a in aliases))

        aliases = self.get_sent_api_value('aliases', 1) or []
        self.assertEqual(len(aliases), 2)
        self.assertTrue(any(a['alias'] == '3000' for a in aliases))

        self.assertEqual(OrganizationUnit.objects.filter(customer=self.customer).count(), 2)
        self.assertEqual(PexipSpace.objects.filter(organization_unit__isnull=False).count(), 1)

        static_range = self.api.get_static_room_number_range()
        self.assertEqual(static_range.next_number, 3001)

        # random
        data['call_id_generation_method'] = 'random'

        result = c.post(self.bulk_url, json.dumps(data), content_type='application/json')
        self.assertEqual(result.status_code, 201)

        self.assertEqual(static_range.next_number, 3001)

        aliases = self.get_sent_api_value('aliases', index=1) or []
        self.assertEqual(len(aliases), 2)
        self.assertFalse(any(a['alias'] == '3000' for a in aliases))

        json_data = result.json()['conferences']
        first_conference = json_data[0]
        second_conference = json_data[1]

        self.assertEqual(first_conference['id'], 123)
        self.assertEqual(first_conference['name'], 'VMR_1')  # reloaded from api
        self.assertEqual(second_conference['name'], 'VMR_1')


class PexipDetailsTestCase(PexipBaseTest):

    def test_single(self):
        Meeting.objects.create(customer=self.customer, provider_ref2=123, ts_start=now() - timedelta(hours=1),
                               ts_stop=now(), title='test', provider=self.pexip, creator_ip='127.0.0.1')

        from statistics.models import Call, Leg
        Call.objects.create(cospace='VMR_1', cospace_id=123, server=self.pexip.cluster.get_statistics_server(),
                            ts_start=now() - timedelta(hours=1), ts_stop=now())
        call = Call.objects.create(cospace='VMR_1', cospace_id=123, server=self.pexip.cluster.get_statistics_server(),
                            ts_start=now() - timedelta(hours=1), ts_stop=None)

        Leg.objects.create(ts_start=now(), call=call, guid='test', server=call.server)

        response = self.client.get('/json-api/v1/cospace-pexip/123/')
        self.assertEqual(response.status_code, 200)

        self.assertTrue(response.json().get('latest_calls'))
        self.assertTrue(response.json().get('ongoing_calls'))
        self.assertTrue(response.json().get('booked_meeting'))

    def test_list(self):
        "Not available"
        response = self.client.get('/json-api/v1/cospace-pexip/')
        self.assertEqual(response.status_code, 405)


class PexipEndUserTestCase(PexipBaseTest):

    def test_single(self):
        response = self.client.get('/json-api/v1/user-pexip/1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tenant'], '')

    def test_change_tenant(self):

        customer2 = Customer.objects.create(lifesize_provider=self.pexip.cluster, title='test', pexip_tenant_id='abc123')
        response = self.client.patch('/json-api/v1/user-pexip/1/', {'tenant': customer2.pexip_tenant_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tenant'], customer2.pexip_tenant_id)

        response = self.client.patch('/json-api/v1/user-pexip/1/', {'tenant': ''})
