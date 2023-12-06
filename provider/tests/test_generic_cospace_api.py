from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from django.contrib.auth.models import User

from datastore.utils.acano import sync_cospaces_from_acano, sync_users_from_acano
from datastore.utils.pexip import sync_conferences_from_pexip, sync_users_from_pexip
from organization.models import OrganizationUnit


class GenericCoSpaceBaseTest(ConferenceBaseTest, APITestCase):

    cospace_with_user = 'fffffff-1948-47ec-ad4f-4793458cfe0c'
    cospace_without_user = '22f67f91-1948-47ec-ad4f-4793458cfe0c'
    uri = '61170'

    def setUp(self):
        self._init() # base

        self.api = self._get_api()

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

        self.org_unit = OrganizationUnit.objects.create(customer=self.customer, name='test')

    def _get_api(self):
        provider = self.customer.get_provider()
        return provider.get_api(self.customer)


class PexipBaseMixin:

    cospace_with_user = '222'
    cospace_without_user = '123'
    uri = '65432'

    def setUp(self):
        super().setUp()
        self.customer.lifesize_provider = self.pexip
        self.customer.save()
        self.api = self._get_api()


class AcanoCachedMixin:

    sync_data = True
    allow_uncached_requests = False

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

        self.assertEqual(
            bool(self._mock_requests.find_url('GET coSpaces/')), self.allow_uncached_requests
        )


class PexipMixin(PexipBaseMixin):
    def setUp(self):

        super().setUp()
        self.pexip.cluster.use_local_database = False
        self.pexip.cluster.use_local_call_state = False
        self.pexip.cluster.save()
        self.api.allow_cached_values = False
        self.assertFalse(self.api.use_cached_values)


class PexipCachedMixin(PexipBaseMixin):

    sync_data = True
    allow_uncached_requests = False

    def setUp(self):
        super().setUp()

        self.pexip.cluster.use_local_database = True
        self.pexip.cluster.use_local_call_state = True
        self.pexip.cluster.save()
        self.api.allow_cached_values = True

        sync_conferences_from_pexip(self.api)
        sync_users_from_pexip(self.api)
        self.assertTrue(self.api.use_cached_values)

        self._mock_requests.clear()

    def tearDown(self):
        super().tearDown()

        if not self.allow_uncached_requests:
            self.assertEqual(self._mock_requests.find_url('GET configuration/v1/conference/'), None)
        self.assertEqual(self._mock_requests.find_url('GET configuration/v1/conference/{}/'.format(self.cospace_with_user)), None)
        self.assertEqual(self._mock_requests.find_url('GET configuration/v1/conference/{}/'.format(self.cospace_without_user)), None)


class GenericInviteTest(GenericCoSpaceBaseTest):

    @property
    def url(self):
        return '/json-api/v1/cospace/{}/invite/'.format(self.cospace_with_user)

    @property
    def url_without_email(self):
        return '/json-api/v1/cospace/{}/invite/'.format(self.cospace_without_user)

    def test_get_invite(self):
        response = self.client.get(self.url)
        self.assertContains(response, self.uri, status_code=200)

    def test_send_invite_no_email(self):
        response = self.client.post(self.url_without_email)
        self.assertEqual(response.status_code, 400)

    def test_send_invite(self):

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'test@example.org')


class GenericPexipInviteTest(PexipMixin, GenericInviteTest):
    pass


class GenericPexipCachedInviteTest(PexipCachedMixin, GenericPexipInviteTest):
    pass


class GenericGetTest(GenericCoSpaceBaseTest):

    @property
    def url(self):
        return '/json-api/v1/cospace/'

    @property
    def url_single(self):
        return '/json-api/v1/cospace/{}/'.format(self.cospace_with_user)

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, '', status_code=200)

    def test_filter(self):
        self.allow_uncached_requests = True
        response = self.client.get(
            self.url
            + '?limit=10&offset=0&organization_unit={}&provider=&q=te&search=te&type='.format(
                self.org_unit.pk
            )
        )
        self.assertContains(response, '', status_code=200)

    def test_get_single(self):
        response = self.client.get(self.url_single)
        self.assertContains(response, self.uri, status_code=200)

    def test_get_single_whole_provider(self):
        response = self.client.get(self.url_single + '?provider={}'.format(self.api.cluster.pk))
        self.assertContains(response, self.uri, status_code=200)

    def test_get_whole_provider(self):
        response = self.client.get(self.url + '?provider={}'.format(self.api.cluster.pk))
        self.assertContains(response, self.uri, status_code=200)


class GenericAcanoCachetGetTest(AcanoCachedMixin, GenericGetTest):
    pass


class GenericPexipGetTest(PexipMixin, GenericGetTest):
    pass


class GenericPexipCachedGetTest(PexipCachedMixin, GenericPexipGetTest):
    pass


class GenericCoSpaceOrgUnitTest(GenericCoSpaceBaseTest):

    @property
    def url(self):
        return '/json-api/v1/cospace/'

    @property
    def url_single(self):
        return '/json-api/v1/cospace/{}/'.format(self.cospace_with_user)

    def test_set_single_and_get(self):

        response = self.client.patch(self.url_single + 'set-organization-unit/', {'organization_path': 'OrgUnit > Nested'})
        self.assertContains(response, '', status_code=200)

        org_unit = OrganizationUnit.objects.filter(customer=self.customer, name='Nested')[0]
        self.assertTrue(org_unit)

        response = self.client.patch(self.url_single + 'set-organization-unit/', {'organization_unit': org_unit.pk})
        self.assertContains(response, '', status_code=200)

        response = self.client.get(self.url_single)
        self.assertEquals(response.json()['organization_unit'], org_unit.pk)

    def test_set_bulk(self):
        response = self.client.patch(self.url + 'set-organization-unit/', {'ids': self.cospace_with_user, 'organization_path': 'OrgUnit > Nested'})
        self.assertContains(response, '', status_code=200)

        org_unit = OrganizationUnit.objects.filter(customer=self.customer, name='Nested')[0]
        self.assertTrue(org_unit)


class GenericAcanoCoSpaceOrgUnitTest(AcanoCachedMixin, GenericCoSpaceOrgUnitTest):
    pass


class GenericPexipCoSpaceOrgUnitTest(PexipMixin, GenericCoSpaceOrgUnitTest):
    pass


# class GenericPexipCachedOrgUnitTest(PexipCachedMixin, GenericCoSpaceOrgUnitTest):
#    pass  # Not necessary


class GenericCoSpaceTenantTest(GenericCoSpaceBaseTest):

    @property
    def url(self):
        return '/json-api/v1/cospace/'

    @property
    def url_single(self):
        return '/json-api/v1/cospace/{}/'.format(self.cospace_with_user)

    def test_set_bulk(self):

        from customer.models import Customer
        customer2 = Customer.objects.create(title='test2', acano_tenant_id='abc123', pexip_tenant_id='abc123', lifesize_provider=self.customer.lifesize_provider)
        response = self.client.patch(self.url + 'set-tenant/', {'ids': self.cospace_with_user, 'tenant': customer2.acano_tenant_id})
        self.assertContains(response, '', status_code=200)

        response = self.client.get(self.url_single)
        if self.customer.get_api().cluster.is_pexip:  # TODO update mock for acano
            cospace = self.customer.get_api().get_cospace(self.cospace_with_user)
            self.assertEquals(cospace['tenant'], customer2.acano_tenant_id)


class GenericAcanoCoSpaceTenantTest(AcanoCachedMixin, GenericCoSpaceTenantTest):
    pass


class GenericPexipCoSpaceTenantTest(PexipMixin, GenericCoSpaceTenantTest):
    pass


# class GenericPexipCachedTenantTest(PexipCachedMixin, GenericCoSpaceTenantTest):
#    pass  # Not necessary. Requires sync api call
