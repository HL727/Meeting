
from os import path

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils.timezone import now
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from endpoint.models import CustomerSettings
from endpointproxy.models import EndpointProxy, EndpointProxyStatusChange

root = path.dirname(path.abspath(__file__))


class ProxyTest(APITestCase, ConferenceBaseTest):

    def setUp(self):
        super().setUp()
        self._init()

    def test_register_fail(self):

        data = {
            'secret_key': 1,
            'version': 1,
        }
        response = self.client.post('/epm/proxy/', data)
        self.assertContains(response, 'error', status_code=200)

    def test_register(self):

        self.assertEqual(EndpointProxy.objects.all().count(), 0)

        data = {
                'ssh_key': 'ssh-rsa ' + 'AAA' * 200,
                'version': 1,
                }
        response = self.client.post('/epm/proxy/', data)
        self.assertContains(response, 'proxy_status', status_code=200)

        self.assertEqual(response.json()['proxy_status'], 'Unconfirmed')

        self.assertEqual(EndpointProxy.objects.all().count(), 1)

        proxy = EndpointProxy.objects.get()
        self.assertEqual(proxy.is_online, False)
        self.assertEqual(proxy.ts_activated, None)

        proxy.activate()

        response = self.client.post('/epm/proxy/', data)
        self.assertEqual(response.json()['proxy_status'], 'OK')

        proxy = EndpointProxy.objects.get()
        self.assertEqual(proxy.is_online, False)
        self.assertNotEquals(proxy.ts_activated, None)

        data.pop('ssh_key')
        data['secret_key'] = proxy.secret_key
        response = self.client.post('/epm/proxy/', data)
        self.assertEqual(response.json().get('proxy_status'), 'OK')

        response = self.client.post('/epm/proxy/check_active/', data)
        self.assertEqual(response.json()['proxy_status'], 'OK')

        proxy = EndpointProxy.objects.get()
        self.assertEqual(proxy.is_online, False)

        # mock status
        EndpointProxy._post = lambda self, url: {'Status': 'OK'}

        response = self.client.post('/epm/proxy/check_active/', data)
        self.assertEqual(response.json()['proxy_status'], 'OK')

        proxy = EndpointProxy.objects.get()
        self.assertEqual(proxy.is_online, True)

    @override_settings(EPM_REQUIRE_PROXY_PASSWORD=True)
    def test_register_password(self):

        c_settings = CustomerSettings.objects.get_for_customer(self.customer)
        c_settings.proxy_password = 'test'
        c_settings.save()

        self.assertEqual(EndpointProxy.objects.all().count(), 0)

        data = {
            'ssh_key': 'ssh-rsa ' + 'AAA' * 200,
            'version': 1,
        }
        response = self.client.post('/epm/proxy/', data)
        self.assertContains(response, 'Invalid data', status_code=200)

        self.assertEqual(EndpointProxy.objects.all().count(), 0)

        data['password'] = 'invalid'
        response = self.client.post('/epm/proxy/', data)
        self.assertContains(response, 'Invalid data', status_code=200)

        self.assertEqual(EndpointProxy.objects.all().count(), 0)

        data['password'] = c_settings.proxy_password
        response = self.client.post('/epm/proxy/', data)
        self.assertContains(response, 'proxy_status', status_code=200)

        self.assertEqual(EndpointProxy.objects.all().count(), 1)

        self.assertEqual(EndpointProxy.objects.all().count(), 1)

        proxy = EndpointProxy.objects.get()
        self.assertEqual(proxy.is_online, False)
        self.assertEqual(proxy.ts_activated, None)
        self.assertEqual(proxy.customer, self.customer)

    def test_api(self):

        User.objects.create_user(username='test', password='test', is_staff=True)
        self.client.login(username='test', password='test')

        proxy = EndpointProxy.objects.create(
            customer=self.customer, name='Test123', ts_activated=now()
        )
        EndpointProxyStatusChange.objects.create(proxy=proxy)
        EndpointProxyStatusChange.objects.create(proxy=proxy)

        response = self.client.get('/json-api/v1/endpointproxy/status/latest/')
        self.assertContains(response, status_code=200, text='"proxy":')
        self.assertEqual(len(response.json()), 2)

        response = self.client.get(
            '/json-api/v1/endpointproxy/status/latest/?proxy={}'.format(proxy.pk)
        )
        self.assertContains(response, status_code=200, text='"proxy":')
        self.assertEqual(len(response.json()), 2)

        response = self.client.get('/json-api/v1/endpointproxy/status/per_proxy/')
        self.assertContains(response, status_code=200, text='"proxy":')
        self.assertEqual(len(response.json()), 1)


@override_settings(EPM_REQUIRE_PROXY_HASH=True)
class ProxyHashTest(APITestCase, ConferenceBaseTest):
    def setUp(self):
        super().setUp()
        self._init()
        self.proxy = EndpointProxy.objects.create(
            customer=self.customer,
            name='Test123',
            ts_activated=now(),
            ssh_key='ssh-rsa ' + 'AAA' * 200,
        )

    def test_no_time(self):

        data = {
            'secret_key': self.proxy.secret_key,
            'version': 1,
        }
        response = self.client.post('/epm/proxy/', data)
        self.assertContains(response, 'error', status_code=200)
        self.assertTrue('time' in response.json().get('errors'))

    def test_no_hash(self):

        data = {
            'secret_key': self.proxy.secret_key,
            'version': 1,
            'time': now().isoformat(),
        }
        response = self.client.post('/epm/proxy/', data)
        self.assertContains(response, 'error', status_code=200)
        self.assertTrue('hash' in response.json().get('errors'))

    def test_invalid_hash(self):

        data = {
            'secret_key': self.proxy.secret_key,
            'version': 1,
            'time': now().isoformat(),
            'hash': 'test',
        }
        response = self.client.post('/epm/proxy/', data)
        self.assertContains(response, 'error', status_code=200)
        self.assertTrue('hash' in response.json().get('errors'))

    def test_valid_hash(self):

        ts = now().isoformat()
        data = {
            'secret_key': self.proxy.secret_key,
            'version': 1,
            'time': ts,
            'hash': self.proxy.get_valid_hash(ts),
        }
        response = self.client.post('/epm/proxy/', data)
        self.assertNotContains(response, 'error', status_code=200)
        self.assertEqual(response.json()['status'], 'OK')
