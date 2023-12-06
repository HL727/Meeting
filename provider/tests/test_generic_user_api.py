from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from django.contrib.auth.models import User

from datastore.utils.acano import sync_cospaces_from_acano, sync_users_from_acano
from datastore.utils.pexip import sync_conferences_from_pexip, sync_users_from_pexip
from organization.models import OrganizationUnit


class GenericUserBaseTest(ConferenceBaseTest, APITestCase):

    user_with_email = 'userguid111'
    username = 'username@example.org'

    user_without_email = 'userguid112'

    def setUp(self):
        self._init() # base

        self.api = self._get_api()

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

        self.org_unit = OrganizationUnit.objects.create(customer=self.customer, name='test')

    def _get_api(self):
        provider = self.customer.get_provider()
        return provider.get_api(self.customer)


class AcanoCachedMixin:

    sync_data = True

    def setUp(self):
        super().setUp()

        self.acano.cluster.use_local_database = True
        self.acano.cluster.use_local_call_state = True
        self.acano.cluster.save()
        self.api.allow_cached_values = True

        sync_cospaces_from_acano(self.api)
        sync_users_from_acano(self.api)
        self.assertTrue(self.api.use_cached_values)

        self._mock_requests.clear()

    def tearDown(self):
        super().tearDown()

        self.assertEqual(self._mock_requests.find_url('GET coSpaces/'), None)
        self.assertEqual(self._mock_requests.find_url('GET users/'), None)


class PexipMixin:

    user_with_email = '1'
    user_without_email = '1'
    username = 'test@example.org'

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

        self.assertEqual(self._mock_requests.find_url('GET configuration/v1/end_user/{}/'.format(self.user_with_email)), None)
        self.assertEqual(self._mock_requests.find_url('GET configuration/v1/end_user/{}/'.format(self.user_without_email)), None)


class GenericUserInviteTest(GenericUserBaseTest):

    @property
    def url(self):
        return '/json-api/v1/user/{}/invite/'.format(self.user_with_email)

    @property
    def url_without_email(self):
        return '/json-api/v1/user/{}/invite/'.format(self.user_without_email)

    def test_get_invite(self):
        response = self.client.get(self.url)
        if self.api.cluster.is_pexip:
            self.assertEqual(response.status_code, 404)
            return

        self.assertContains(response, self.username, status_code=200)

    def test_send_invite_no_email(self):
        response = self.client.post(self.url_without_email)
        self.assertEqual(response.status_code, 400)

    def test_send_invite(self):
        response = self.client.post(self.url)

        if self.api.cluster.is_pexip:
            self.assertEqual(response.status_code, 400)
            return

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'test@example.org')


class GenericPexipInviteTest(PexipMixin, GenericUserInviteTest):
    pass


class GenericPexipCachedInviteTest(PexipCachedMixin, GenericPexipInviteTest):
    pass


class GenericUserGetTest(GenericUserBaseTest):

    @property
    def url(self):
        return '/json-api/v1/user/'

    @property
    def url_single(self):
        return '/json-api/v1/user/{}/'.format(self.user_with_email)

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, '', status_code=200)

    def test_get_filter(self):
        response = self.client.get(
            self.url
            + '?include_call_stats=1&limit=10&offset=0&organization_unit={}&provider=&q=&search='.format(
                self.org_unit.pk
            )
        )
        self.assertContains(response, '', status_code=200)

    def test_get_single(self):
        response = self.client.get(self.url_single)
        self.assertContains(response, self.username, status_code=200)

    def test_get_call_stats(self):
        response = self.client.get(self.url + '?include_call_stats=1')
        self.assertContains(response, self.username, status_code=200)

    def test_get_single_whole_provider(self):
        response = self.client.get(self.url_single + '?provider={}'.format(self.api.cluster.pk))
        self.assertContains(response, self.username, status_code=200)

    def test_get_whole_provider(self):
        response = self.client.get(self.url + '?provider={}'.format(self.api.cluster.pk))
        self.assertContains(response, self.username, status_code=200)


class GenericAcanoUserGetTest(AcanoCachedMixin, GenericUserGetTest):
    pass


class GenericPexipUserGetTest(PexipMixin, GenericUserGetTest):
    pass


class GenericPexipCachedUserGetTest(PexipCachedMixin, GenericPexipUserGetTest):
    pass


class GenericUserOrgUnitTest(GenericUserBaseTest):

    @property
    def url(self):
        return '/json-api/v1/user/'

    @property
    def url_single(self):
        return '/json-api/v1/user/{}/'.format(self.user_with_email)

    def test_set_single_and_get(self):

        response = self.client.patch(self.url_single + 'set-organization-unit/', {'organization_path': 'OrgUnit > Nested'})
        self.assertContains(response, '', status_code=200)

        org_unit = OrganizationUnit.objects.filter(customer=self.customer, name='Nested')[0]
        response = self.client.patch(self.url_single + 'set-organization-unit/', {'organization_unit': org_unit.pk})
        self.assertContains(response, '', status_code=200)

        response = self.client.get(self.url_single)
        self.assertEquals(response.json()['organization_unit'], org_unit.pk)

    def test_set_bulk(self):
        response = self.client.patch(self.url + 'set-organization-unit/', {'ids': self.user_with_email, 'organization_path': 'OrgUnit > Nested'})
        self.assertContains(response, '', status_code=200)


class GenericPexipUserOrgUnitTest(PexipMixin, GenericUserOrgUnitTest):
    pass


class GenericPexipCachedUserOrgUnitTest(PexipCachedMixin, GenericPexipUserOrgUnitTest):
    pass



