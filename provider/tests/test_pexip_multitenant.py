from datetime import timedelta

from django.contrib.auth.models import User
from django.utils.timezone import now
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from customer.models import CustomerMatch, Customer
from statistics.models import Call, Leg

MOCKED_CALLS_COUNT = 1
MOCKED_CALL_LEGS_COUNT = 1


class PexipCallMultitenantTest(ConferenceBaseTest, APITestCase):
    leg = '00000000-0000-0000-0000-000000000002'
    call = '00000000-0000-0000-0000-000000000001'
    space = 'VMR_1'

    def setUp(self):
        super().setUp()
        self._init()  # base

        self.api = self._get_api()

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

        self.customer.lifesize_provider = self.pexip
        self.customer.save()

        self.customer2 = Customer.objects.create(lifesize_provider=self.pexip, title='Test2')
        self.server = self.pexip.cluster.get_statistics_server()

    def _create_statistics_call(self, tenant=''):

        from statistics.models import Call, Leg

        server = self.server

        call = Call.objects.create(server=server, ts_start=now(), ts_stop=None, guid=self.call + tenant,
                                   cospace=self.space, tenant=tenant)
        leg = Leg.objects.create(server=server, ts_start=now(), ts_stop=None,
                                 local='65432@local.example.org', remote='remote@example.org',
                                 call=call, should_count_stats=True, guid=self.leg + tenant, tenant=tenant)

        self.assertTrue(leg.should_count_stats)
        self.assertTrue(self._get_api(allow_cached_values=True).has_cdr_events)

    def _reset_default_customer(self):
        self.pexip.cluster.default_customer = None
        self.pexip.cluster.save()

    def _set_customer_tenant_id(self, tenant_id):
        self.customer.pexip_tenant_id = tenant_id
        self.customer.save()

    def _get_api(self, allow_cached_values=False):
        provider = self.customer.get_provider()
        api = provider.get_api(self.customer, allow_cached_values=allow_cached_values)
        self.api = api
        return api

    def assertCallsCount(self, correct_count, tenant=True, has_cdr_events=None):
        if has_cdr_events is not None:
            self.assertEqual(self._get_api(allow_cached_values=True).has_cdr_events, has_cdr_events)
        if tenant is True:
            tenant = self.customer.get_pexip_tenant_id()
        calls, count = self._get_api(allow_cached_values=False).get_calls(tenant=tenant)
        self.assertEqual(len(calls), count)
        self.assertEqual(len(calls), correct_count)

    def assertCachedCallsCount(self, correct_count, tenant=True, has_cdr_events=None):
        if has_cdr_events is not None:
            self.assertEqual(self._get_api(allow_cached_values=True).has_cdr_events, has_cdr_events)
        if tenant is True:
            tenant = self.customer.get_pexip_tenant_id()
        calls, count = self._get_api(allow_cached_values=True).get_calls(tenant=tenant)
        self.assertEqual(len(calls), count)
        self.assertEqual(len(calls), correct_count)

    def assertCallLegsCount(self, correct_count, tenant=True, has_cdr_events=None):
        if tenant is True:
            tenant = self.customer.get_pexip_tenant_id()
        legs, count = self._get_api(allow_cached_values=False).get_call_legs(tenant=tenant)
        self.assertEqual(len(legs), count)
        self.assertEqual(len(legs), correct_count)

    def assertCachedCallLegsCount(self, correct_count, tenant=True, has_cdr_events=None):
        if tenant is True:
            tenant = self.customer.get_pexip_tenant_id()
        legs, count = self._get_api(allow_cached_values=True).get_call_legs(tenant=tenant)
        self.assertEqual(len(legs), count)
        self.assertEqual(len(legs), correct_count)


class PexipMultiTenantCallFromAPITest(PexipCallMultitenantTest):

    def tearDown(self):
        super().tearDown()

        self.assertNotEqual(self._mock_requests.find_url('GET status/v1/conference/'), None)

    def test_calls_uncached(self):
        self.assertCallsCount(MOCKED_CALLS_COUNT, has_cdr_events=False)
        self.assertCallsCount(MOCKED_CALLS_COUNT, tenant=None, has_cdr_events=False)

        self.assertCallLegsCount(MOCKED_CALL_LEGS_COUNT)
        self.assertCallLegsCount(MOCKED_CALL_LEGS_COUNT, tenant=None)

    def test_calls_cached_without_cdr(self):
        """same as uncached until call exists"""
        self.assertCallsCount(MOCKED_CALLS_COUNT, has_cdr_events=False)
        self.assertCallsCount(MOCKED_CALLS_COUNT, tenant=None, has_cdr_events=False)

        self.assertCallLegsCount(MOCKED_CALL_LEGS_COUNT)
        self.assertCallLegsCount(MOCKED_CALL_LEGS_COUNT, tenant=None)

    def test_customer_with_tenant_id_and_match_rules(self):
        self._reset_default_customer()

        CustomerMatch.objects.create(cluster=self.pexip.cluster, regexp_match=r'.', customer=self.customer)

        self.assertCallsCount(MOCKED_CALLS_COUNT, has_cdr_events=False)
        self.assertCachedCallsCount(MOCKED_CALLS_COUNT, has_cdr_events=False)

        self.assertCallsCount(MOCKED_CALLS_COUNT, tenant=None, has_cdr_events=False)
        self.assertCachedCallsCount(MOCKED_CALLS_COUNT, tenant=None, has_cdr_events=False)

        self.assertCallLegsCount(MOCKED_CALL_LEGS_COUNT)
        self.assertCachedCallLegsCount(MOCKED_CALL_LEGS_COUNT)

        self.assertCallLegsCount(MOCKED_CALL_LEGS_COUNT, tenant=None)
        self.assertCachedCallLegsCount(MOCKED_CALL_LEGS_COUNT, tenant=None)

        self.customer.refresh_from_db()
        self.assertTrue(self.customer.pexip_tenant_id)

    def test_wrong_customer_tenant(self):
        self._reset_default_customer()
        self._set_customer_tenant_id('1234')

        self.assertCallsCount(0, has_cdr_events=False)
        self.assertCachedCallsCount(0, has_cdr_events=False)

        self.assertCallsCount(0, has_cdr_events=False)
        self.assertCachedCallsCount(0, has_cdr_events=False)

        self.assertCallLegsCount(0, has_cdr_events=False)
        self.assertCachedCallLegsCount(0, has_cdr_events=False)

        self.assertCallLegsCount(0, has_cdr_events=False)
        self.assertCachedCallLegsCount(0, has_cdr_events=False)

    def test_wrong_call_tenant(self):
        CustomerMatch.objects.create(cluster=self.pexip.cluster, regexp_match=r'.', customer=self.customer2)

        self.assertCallsCount(0, has_cdr_events=False)
        self.assertCachedCallsCount(0, has_cdr_events=False)

        self.assertCallLegsCount(0, has_cdr_events=False)
        self.assertCachedCallLegsCount(0, has_cdr_events=False)

    def test_call_tenant_local_match(self):
        """calls should match using participant local alias"""
        self._reset_default_customer()
        CustomerMatch.objects.create(cluster=self.pexip.cluster, regexp_match=r'.*local', customer=self.customer)

        self.assertCallsCount(1, has_cdr_events=False)
        self.assertCachedCallsCount(1, has_cdr_events=False)

        self.assertCallLegsCount(1, has_cdr_events=False)
        self.assertCachedCallLegsCount(1, has_cdr_events=False)

    def test_call_tenant_remote_match(self):
        """calls should not match using only participant remote alias"""
        self._reset_default_customer()
        CustomerMatch.objects.create(cluster=self.pexip.cluster, regexp_match=r'.*remote', customer=self.customer2)

        self.assertCallsCount(0, has_cdr_events=False)
        self.assertCachedCallsCount(0, has_cdr_events=False)

        self.assertCallLegsCount(0, has_cdr_events=False)
        self.assertCachedCallLegsCount(0, has_cdr_events=False)

    def test_leg_from_another_tenant_call(self):
        """legs from calls belonging to another tenant should be included only to specific call"""
        self._create_statistics_call()
        CustomerMatch.objects.create(cluster=self.pexip.cluster, regexp_match=r'.*remote', customer=self.customer2)
        Leg.objects.all().update(tenant=self.customer2.get_pexip_tenant_id())

        self.assertCallsCount(1, has_cdr_events=True)
        self.assertCallLegsCount(0, has_cdr_events=True)

        self.assertCachedCallsCount(1, has_cdr_events=True)
        self.assertCachedCallLegsCount(0, has_cdr_events=True)

        call = self._get_api().get_call(self.call, include_participants=True)
        self.assertEqual(len(call['participants']), 1)

        call = self._get_api(allow_cached_values=True).get_call(self.call, include_participants=True)
        self.assertEqual(len(call['participants']), 1)


class PexipMultiTenantCallFromDatabaseTest(PexipCallMultitenantTest):

    def tearDown(self):
        super().tearDown()

        self.assertEqual(self._mock_requests.find_url('GET status/v1/conference/'), None)
        self.assertEqual(self._mock_requests.find_url('GET status/v1/participant/'), None)

    def test_calls_cached_empty(self):
        """no active calls (with legs) but cdr exists -> empty"""
        Call.objects.create(server=self.server, ts_start=now() - timedelta(hours=1), ts_stop=None,
                            guid='force-cdr')
        self.assertCachedCallsCount(0, has_cdr_events=True)
        self.assertCachedCallLegsCount(0, has_cdr_events=True)

    def test_calls_cached_valid(self):
        """active calls and cdr exists -> return"""
        self._create_statistics_call()
        self.assertCachedCallsCount(1, has_cdr_events=True)
        self.assertCachedCallLegsCount(1, has_cdr_events=True)

    def test_calls_multitenant(self):
        self._create_statistics_call(tenant='other')
        self._create_statistics_call(tenant='nr2')
        self.assertCachedCallsCount(2, tenant=None, has_cdr_events=True)
        self.assertCachedCallsCount(1, tenant='other', has_cdr_events=True)

        self.assertCachedCallLegsCount(2, tenant=None, has_cdr_events=True)
        self.assertCachedCallLegsCount(1, tenant='other', has_cdr_events=True)

    def test_wrong_customer_tenant(self):
        self._set_customer_tenant_id('1234')
        self._create_statistics_call()
        self.assertCachedCallsCount(0, has_cdr_events=True)
        self.assertCachedCallLegsCount(0, has_cdr_events=True)

    def test_wrong_call_tenant(self):
        self._create_statistics_call(tenant='other')
        self.assertCachedCallsCount(0, has_cdr_events=True)
        self.assertCachedCallLegsCount(0, has_cdr_events=True)
