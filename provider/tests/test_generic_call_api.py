from django.utils.timezone import now
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from django.contrib.auth.models import User

from customer.models import CustomerMatch
from statistics.models import Call
from supporthelpers.models import CustomerPermission


class GenericCallBaseTest(ConferenceBaseTest, APITestCase):

    leg = '976dacd8-bc6b-4526-8bb7-d9050740b7c7'
    call = '935a38b8-0a80-4965-9db4-f02ab1a813d2'

    space = '22f67f91-1948-47ec-ad4f-4793458cfe0c'
    local_alias = 'local@example.org'
    remote_alias = 'remote@example.org'

    allow_status_call_api = True

    def setUp(self):
        super().setUp()
        self._init() # base

        self.api = self._get_api()

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

        self.user.is_staff = False  # non-staff should not be able to see other tenants
        self.user.save()


    def _get_api(self):
        provider = self.customer.get_provider()
        return provider.get_api(self.customer)


class GenericCallPexipBaseMixin:

    leg = '00000000-0000-0000-0000-000000000002'
    call = '00000000-0000-0000-0000-000000000001'
    space = 'VMR_1'
    local_alias = 'local@example.org'
    remote_alias = 'remote@example.org'

    def setUp(self):
        super().setUp()
        self.customer.lifesize_provider = self.pexip
        self.customer.save()
        self.api = self._get_api()

        from statistics.models import Call, Leg

        server = self.pexip.cluster.get_statistics_server()
        call = Call.objects.create(server=server, ts_start=now(), ts_stop=None, guid=self.call, cospace=self.space)
        leg = Leg.objects.create(server=server, ts_start=now(), ts_stop=None,
                                 local=self.local_alias, remote=self.remote_alias,
                                 call=call, should_count_stats=True, guid=self.leg)
        self.assertTrue(leg.should_count_stats)

    def tearDown(self):
        super().tearDown()

        conference_request = self._mock_requests.find_url(
            'GET status/v1/conference/{}/'.format(self.call)
        )
        participant_request = self._mock_requests.find_url(
            'GET status/v1/participant/{}/'.format(self.leg)
        )

        if not self.allow_status_call_api:
            self.assertFalse(conference_request)
            self.assertFalse(participant_request)


class GenericCallPexipMixin(GenericCallPexipBaseMixin):
    def setUp(self):
        super().setUp()
        self.pexip.cluster.use_local_database = False
        self.pexip.cluster.use_local_call_state = False
        self.pexip.cluster.save()
        self.api.allow_cached_values = False
        self.assertFalse(self.api.use_call_cache)


class GenericCallPexipCachedMixin(GenericCallPexipBaseMixin):

    allow_status_call_api = False

    def setUp(self):
        super().setUp()
        self.pexip.cluster.use_local_database = True
        self.pexip.cluster.use_local_call_state = True
        self.pexip.cluster.save()
        self.api.allow_cached_values = True
        self.assertTrue(self.api.use_call_cache)


class GenericHangupTest(GenericCallBaseTest):

    @property
    def url(self):
        return '/json-api/v1/calls/{}/?cospace={}'.format(self.call, self.space)

    def test_hangup(self):
        response = self.client.delete(self.url)
        self.assertContains(response, '', status_code=204)


class GenericCallPexipHangupTest(GenericCallPexipMixin, GenericHangupTest):
    pass


class GenericPexipCachedHangupTest(GenericCallPexipCachedMixin, GenericCallPexipHangupTest):
    pass


class GenericGetTest(GenericCallBaseTest):

    @property
    def url(self):
        return '/json-api/v1/calls/?cospace={}'.format(self.space)

    @property
    def url_single(self):
        return self.get_url_single()

    def get_url_single(self, suffix=''):
        return '/json-api/v1/calls/{}/{}?cospace={}'.format(self.call, suffix or '', self.space)

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, '', status_code=200)

    def test_get_single(self):
        response = self.client.get(self.url_single)
        self.assertContains(response, self.space, status_code=200)

    def test_lock(self):
        response = self.client.post(self.get_url_single('lock/'))
        self.assertContains(response, self.space, status_code=200)
        response = self.client.delete(self.get_url_single('lock/'))
        self.assertContains(response, self.space, status_code=200)


class GenericCallPexipGetTest(GenericCallPexipMixin, GenericGetTest):
    pass


class GenericPexipCachedGetTest(GenericCallPexipCachedMixin, GenericCallPexipGetTest):

    def test_lookup_id_call(self):
        call = Call.objects.all().first()
        response = self.client.get('/json-api/v1/calls/lookup.{}/'.format(call.id))
        self.assertContains(response, self.space, status_code=200)


class GenericCallPexipTenantTest(GenericCallPexipMixin, GenericGetTest):

    def setUp(self):
        super().setUp()

        provider = self.customer.get_api().cluster
        assert provider.is_pexip
        from datastore.models.pexip import Conference
        self.conference = Conference.objects.create(provider=provider,
                                                    name=self.space,
                                                    is_active=True,
                                                    )

    def _set_conference_tenant(self, tenant_id='1234'):
        from datastore.models.customer import Tenant
        self.conference.tenant = Tenant.objects.create(provider=self.pexip.cluster, tid=tenant_id)
        self.conference.save()
        from statistics.models import Call, Leg
        Call.objects.all().update(tenant=tenant_id)
        Leg.objects.all().update(tenant=tenant_id)

    def test_pexip_tenant_single_forbidden(self):
        self.customer.pexip_tenant_id = '1234'
        self.customer.save()

        response = self.client.get(self.url_single)
        self.assertNotContains(response, self.space, status_code=404)

    def test_pexip_tenant_single_valid(self):
        self.customer.pexip_tenant_id = '1234'
        self.customer.save()

        self._set_conference_tenant('1234')

        response = self.client.get(self.url_single)
        self.assertContains(response, self.space, status_code=200)

    def test_pexip_tenant_list_forbidden(self):
        self.customer.pexip_tenant_id = '1234'
        self.customer.save()

        response = self.client.get(self.url)
        self.assertNotContains(response, self.space, status_code=200)

    def test_pexip_tenant_list_valid(self):

        response = self.client.get(self.url)
        self.assertContains(response, self.space, status_code=200)

    def test_dynamic_provider(self):
        self.customer.lifesize_provider = self.acano
        self.customer.save()

        response = self.client.get(self.url + '&provider={}'.format(self.pexip.pk))
        self.assertContains(response, self.space, status_code=200)

        response = self.client.get(self.url_single + '&provider={}'.format(self.pexip.pk))
        self.assertContains(response, self.space, status_code=200)

    def test_dynamic_provider_same(self):
        response = self.client.get(self.url + '&provider={}'.format(self.pexip.pk))
        self.assertContains(response, self.space, status_code=200)

    def test_dynamic_provider_no_permission(self):
        CustomerPermission.objects.create(customer=self.customer, user=self.user)

        self.customer.lifesize_provider = self.acano
        self.customer.save()

        response = self.client.get(self.url + '&provider={}'.format(self.pexip.pk))
        self.assertNotContains(response, self.space, status_code=404)

    def test_customer_match(self):
        self.pexip.cluster.pexip.default_customer = None
        self.pexip.cluster.pexip.save()

        provider = self.customer.get_api().cluster
        CustomerMatch.objects.create(cluster=provider, regexp_match='.', customer=self.customer)

        self.assertNotEquals(self.customer.get_pexip_tenant_id(), '')

        self._set_conference_tenant('1234')

        response = self.client.get(self.url_single)
        self.assertNotContains(response, self.space, status_code=404)

        response = self.client.get(self.url)
        self.assertNotContains(response, self.space, status_code=200)

        match = CustomerMatch.objects.get_match_for_pexip(self.space, cluster=self.pexip.cluster)
        self.assertEqual(match.tenant_id, '1234')

        self.user.is_staff = True
        self.user.save()

        response = self.client.get(self.url_single)
        self.assertContains(response, self.space, status_code=200)

    def test_default_customer_with_other_tenant(self):
        self._set_conference_tenant('1234')
        self.conference.delete()

        self.pexip.cluster.default_customer = self.customer
        self.pexip.cluster.save()

        response = self.client.get(self.url)
        self.assertNotContains(response, self.space, status_code=200)

        response = self.client.get(self.url_single)
        self.assertNotContains(response, self.space, status_code=404)

    def test_default_tenant_valid(self):

        # match standard
        match = CustomerMatch.objects.get_match_for_pexip(self.space, cluster=self.pexip.cluster)
        self.assertEqual(match, None)

        response = self.client.get(self.url_single)
        self.assertContains(response, self.space, status_code=200)

        response = self.client.get(self.url)
        self.assertContains(response, self.space, status_code=200)


class GenericPexipCachedTenantTest(GenericCallPexipCachedMixin, GenericCallPexipTenantTest):
    pass

