from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from django.contrib.auth.models import User

from datastore.utils.pexip import sync_conferences_from_pexip, sync_users_from_pexip
from organization.models import OrganizationUnit


class TestStatusBaseTest(ConferenceBaseTest, APITestCase):

    def setUp(self):
        self._init() # base

        self.api = self._get_api()

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

    def _get_api(self):
        provider = self.customer.get_provider()
        return provider.get_api(self.customer)


class PexipMixin:

    def setUp(self):
        super().setUp()
        self.customer.lifesize_provider = self.pexip
        self.customer.save()
        self.api = self._get_api()


class PexipCachedMixin(PexipMixin):

    def setUp(self):
        super().setUp()

        sync_conferences_from_pexip(self.api)
        sync_users_from_pexip(self.api)

    def tearDown(self):
        super().tearDown()

        self.assertEqual(self._mock_requests.find_url('GET configuration/v1/conference/'), None)
        self.assertEqual(self._mock_requests.find_url('GET configuration/v1/conference/'), None)


class TestStatusApiTest(TestStatusBaseTest):

    def test_acano(self):
        response = self.client.get('/json-api/v1/provider/status/?type=acano')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())

    def test_pexip(self):
        self.switch_provider('pexip')
        response = self.client.get('/json-api/v1/provider/status/?type=pexip')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())

    def test_vcs(self):
        self.vcse.customer = self.customer
        self.vcse.save()

        response = self.client.get('/json-api/v1/provider/status/?type=vcs')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())


