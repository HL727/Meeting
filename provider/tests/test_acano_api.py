import json

from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from django.urls import reverse
from django.contrib.auth.models import User

from conferencecenter.tests.mock_data import state as mock_state
from numberseries.models import NumberRange
from organization.models import OrganizationUnit, CoSpaceUnitRelation


class CoSpaceBaseTest(APITestCase, ConferenceBaseTest):
    data = {
        'name': 'Test',
        'uri': 'test',
        'call_id': '1234',
        'layout': 'telepresence',
        'password': '10203040',
        'group': '',
        'enable_chat': 'off',
        'lobby_pin': '3010045',
    }
    def setUp(self):
        self._init() # base

        self.api = self._get_api()

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

    def _get_api(self):
        provider = self.customer.get_provider()
        return provider.get_api(self.customer)


class CoSpaceCreateTest(CoSpaceBaseTest):

    @property
    def url(self):
        return '/json-api/v1/cospace-acano/'

    def test_increase(self):
        data = {
            **self.data,
            'call_id_generation_method': 'increase',
        }
        data.pop('call_id')

        number_range = self.customer.get_api().get_static_room_number_range()
        number_range.start = 3000
        number_range.save()
        self.assertEqual(number_range.next_number, None)

        response = self.client.post(self.url, data)
        self.assertContains(response, 'fbn', status_code=201)

        number_range = self.customer.get_api().get_static_room_number_range()

        number_range.refresh_from_db()
        self.assertEqual(number_range.next_number, 3001)

    def test_random(self):
        data = {
            **self.data,
            'call_id_generation_method': 'random',
            'organization_path': 'Test1 / Test 2',
        }
        data.pop('call_id')
        response = self.client.post(self.url, data)
        self.assertContains(response, 'fbn', status_code=201)

        number_range = self.customer.get_api().get_static_room_number_range()
        self.assertEqual(number_range.next_number, None)

        self.assertEqual(OrganizationUnit.objects.filter(customer=self.customer).count(), 2)

    def test_manual(self):
        data = {
            **self.data,
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, 'fbn', status_code=201)

        number_range = self.customer.get_api().get_static_room_number_range()
        self.assertEqual(number_range.next_number, None)


class CoSpaceUpdateTest(CoSpaceBaseTest):

    @property
    def url(self):
        return '/json-api/v1/cospace-acano/22f67f91-1948-47ec-ad4f-4793458cfe0c/'

    def test_update(self):
        response = self.client.put(self.url, self.data)
        self.assertContains(response, 'fbn', status_code=200)

    def test_update_tenant(self):
        response = self.client.put(self.url, {
            **self.data,
            'tenant': self.customer.acano_tenant_id,
        })
        self.assertContains(response, 'fbn', status_code=200)

    def test_update_org_unit(self):
        response = self.client.put(
            self.url,
            {
                **self.data,
                'organization_path': 'Root > Sub',
            },
        )
        self.assertTrue(response.json()['organization_unit'])

        response = self.client.put(
            self.url,
            {
                **self.data,
                'organization_path': '',
            },
        )
        self.assertEqual(response.json()['organization_unit'], None)


class CoSpaceBulkTest(CoSpaceBaseTest):
    def test_authentication(self):
        c = self.client

        data = {}
        result = c.post(reverse('cospace-bulk-create'), data)

        self.assertEqual(result.status_code, 400)

        c.logout()

        result = c.post(reverse('cospace-bulk-create'), data)

        self.assertEqual(result.status_code, 403)

    def _set_url_state(self, state):
        mock_state.url_state = state

    def _get_multiple_cospace_data(self):
        return [{
            'name': 'CoSpaceTestTitle1',
            'uri':  'CoSpaceTestUri1',
            'call_id': '123',
            'owner_jid': '',
            'organization_path': 'Test / Test 2',
        },{
            'name': 'CoSpaceTestTitle2',
            'uri':  'CoSpaceTestUri2',
            'organization_path': 'Test / Test 2 / Test 3',
            'owner_jid': ''
        }]

    def test_create_approved(self):
        c = self.client
        data = {
            'cospaces': self._get_multiple_cospace_data(),
        }

        static_range = self.api.get_static_room_number_range()
        static_range.start = 3000
        static_range.save()
        self.assertEqual(len(NumberRange.objects.all()), 1)

        # increase
        data['call_id_generation_method'] = 'increase'

        result = c.post(reverse('cospace-bulk-create'), json.dumps(data), content_type='application/json')

        self.assertEqual(result.status_code, 201)
        json_data = json.loads(result.content)['cospaces']
        first_cospace = json_data[0]
        second_cospace = json_data[1]

        static_range = self.api.get_static_room_number_range()
        self.assertEqual(static_range.next_number, 3001)

        # random
        data['call_id_generation_method'] = 'random'

        self.assertEqual(result.status_code, 201)
        self.assertEqual(first_cospace['id'], '22f67f91-1948-47ec-ad4f-4793458cfe0c')
        self.assertEqual(first_cospace['name'], 'CoSpaceTestTitle1')
        self.assertEqual(second_cospace['name'], 'CoSpaceTestTitle2')

        static_range = self.api.get_static_room_number_range()
        self.assertEqual(static_range.next_number, 3001)

        self.assertEqual(OrganizationUnit.objects.filter(customer=self.customer).count(), 3)
        self.assertEqual(CoSpaceUnitRelation.objects.filter(unit__customer=self.customer).count(), 2)


    def test_create_uri_error(self):
        c = self.client
        data = {
            'cospaces': self._get_multiple_cospace_data(),
            'call_id_generation_method': 'random',
        }
        self._set_url_state('uri-in-use')

        result = c.post(reverse('cospace-bulk-create'),
            json.dumps(data), content_type='application/json')

        first_cospace = json.loads(result.content)['cospaces'][0]

        self.assertEqual(first_cospace['status'], 'error')
        self.assertIsInstance(first_cospace['errors'], dict)
        self.assertIn('uri', first_cospace['errors'])

    def test_create_call_id_error(self):
        c = self.client
        data = {
            'cospaces': self._get_multiple_cospace_data(),
            'call_id_generation_method': 'random',
        }
        self._set_url_state('call-id-in-use')

        result = c.post(reverse('cospace-bulk-create'),
            json.dumps(data), content_type='application/json')

        self.assertEqual(result.status_code, 400)

        first_cospace = json.loads(result.content)['cospaces'][0]

        self.assertEqual(first_cospace['status'], 'error')
        self.assertIsInstance(first_cospace['errors'], dict)
        self.assertIn('call_id', first_cospace['errors'])

    def test_create_owner_error(self):
        c = self.client
        data = {
            'cospaces': self._get_multiple_cospace_data(),
            'call_id_generation_method': 'random',
        }
        self._set_url_state('owner-not-found')

        result = c.post(reverse('cospace-bulk-create'),
            json.dumps(data), content_type='application/json')

        self.assertEqual(result.status_code, 400)
        first_cospace = json.loads(result.content)['cospaces'][0]

        self.assertEqual(first_cospace['status'], 'error')
        self.assertIsInstance(first_cospace['errors'], dict)
        self.assertIn('owner_jid', first_cospace['errors'])

    def test_create_with_owner(self):
        c = self.client
        data = {
            'cospaces': self._get_multiple_cospace_data(),
            'call_id_generation_method': 'random',
        }
        data['cospaces'][0]['owner_jid'] = 'username@example.org'

        result = c.post(reverse('cospace-bulk-create'),
            json.dumps(data), content_type='application/json')

        self.assertEqual(result.status_code, 201)
        first_cospace = json.loads(result.content)['cospaces'][0]

        self.assertEqual(first_cospace['status'], 'ok')
        self.assertEqual(first_cospace['id'], '22f67f91-1948-47ec-ad4f-4793458cfe0c')
        self.assertEqual(first_cospace['owner_jid'], 'username@example.org')
