from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.timezone import now
from django.test import override_settings

from conferencecenter.tests.base import ConferenceBaseTest
from customer.models import Customer
from organization.models import OrganizationUnit
from statistics.models import Server, Call, Leg, ServerTenant, Tenant


class StatsViewsBase(ConferenceBaseTest):

    def setUp(self):
        super().setUp()
        self._init()

        ts = dict(ts_start=now() - timedelta(hours=1), ts_stop=now())

        server = self.acano.cluster.get_statistics_server()
        self.server = server

        ServerTenant.objects.create(server=self.server, tenant=Tenant.objects.get_or_create(guid=self.customer.acano_tenant_id)[0])

        call = Call.objects.create(guid='123', cospace_id='123', server=server, **ts)
        self.call = call

        self.combined_server = Server.objects.create(name='Combined', type=Server.COMBINE, customer=self.customer)
        self.combined_server.combine_servers.add(server)

        call.legs.add(Leg.objects.create(target='target1@example.org', ou='ou1', tenant='123', duration=123, server=server, **ts))
        call.legs.add(Leg.objects.create(target='target2@example.org', ou='ou2', tenant='123', duration=123, server=server, **ts))
        call.legs.add(Leg.objects.create(target='target3@example.org', ou='ou1', tenant='', duration=123, server=server, **ts))
        call.legs.add(Leg.objects.create(target='targe34@example.org', ou='ou1', tenant='', duration=123, server=server, **ts))

        self.user = User.objects.create_user(username='test', password='test', is_superuser=True, is_staff=True)
        self.client.login(username='test', password='test')

    def assertEmptySummary(self, response):
        keys_with_values = set(k for k, v in response.json().get('summary', {}).items() if any(v.values()))

        not_total = [k for k in keys_with_values if not k.endswith('_total')]
        self.assertFalse(not_total)

    def assertHaveSummary(self, response):
        keys_with_values = set(k for k, v in response.json().get('summary', {}).items() if any(v.values()))

        not_total = [k for k in keys_with_values if not k.endswith('_total')]
        self.assertTrue(not_total)


class StatsViewsTestCase(StatsViewsBase):

    def test_stats(self):

        response = self.client.get(reverse('stats') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}'.format(self.server.id))
        self.assertEqual(response.status_code, 200)

    def test_stats_ajax(self):

        response = self.client.get(reverse('stats') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1&debug=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertHaveSummary(response)
        self.assertTrue(response.json().get('graphs', {}).get('graph'))

        # debug
        self.assertTrue(response.json().get('calls', []))
        self.assertTrue(response.json().get('legs', []))

    def test_stats_org_unit_filter(self):

        org_unit = OrganizationUnit.objects.create(customer=self.customer, name='test')

        response = self.client.get(reverse('stats') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&organization={}&ajax=1&debug=1'.format(self.server.id, org_unit.pk))
        self.assertEqual(response.status_code, 200)

        self.assertEmptySummary(response)
        self.assertFalse(response.json().get('graphs', {}).get('graph'))

        Leg.objects.all().update(org_unit=org_unit)

        response = self.client.get(reverse('stats') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&organization={}&ajax=1&debug=1'.format(self.server.id, org_unit.pk))
        self.assertEqual(response.status_code, 200)

        self.assertHaveSummary(response)
        self.assertTrue(response.json().get('graphs', {}).get('graph'))


    def test_combined_stats_ajax(self):

        response = self.client.get(reverse('stats') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1&debug=1'.format(self.combined_server.id))
        self.assertEqual(response.status_code, 200)
        self.assertHaveSummary(response)
        self.assertTrue(response.json().get('graphs', {}).get('graph'))

    def test_stats_settings(self):

        response = self.client.get(reverse('stats') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1&only_settings=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        choices = response.json().get('choices', {})
        self.assertEqual(choices['tenant'], [])
        self.assertTrue(choices['server'])

    def test_stats_settings_multitenant(self):

        customer2 = Customer.objects.create(title='test2', acano_tenant_id='asdf')
        ServerTenant.objects.create(server=self.server, tenant=Tenant.objects.create(guid=customer2.acano_tenant_id or ''))
        response = self.client.get(reverse('stats') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1&only_settings=1&multitenant=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        choices = response.json().get('choices', {})

        tenants = [t[0] for t in choices.get('tenant', [])]
        self.assertEqual(tenants, ['', 'none', customer2.acano_tenant_id])
        self.assertTrue(choices['server'])

    def test_stats_pdf(self):

        try:
            response = self.client.get(reverse('stats_pdf') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}'.format(self.server.id))
        except ValueError as e:
            if not e.args or 'orca executable' not in e.args[0]:
                raise
        else:
            self.assertEqual(response.status_code, 200)

    def test_stats_excel(self):

        response = self.client.get(reverse('stats_excel') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server=1')
        self.assertEqual(response.status_code, 200)


    def test_stats_excel_debug(self):

        response = self.client.get(
            reverse('stats_excel_debug') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server=1'
        )
        self.assertEqual(response.status_code, 200)

    def test_stats_debug(self):

        response = self.client.get(reverse('stats_debug', args=[self.call.guid]))
        self.assertEqual(response.status_code, 200)


class CallStatsAPITestCase(StatsViewsBase):

    def _get_params(self, **params):
        return urlencode({
            'ts_start': '2011-01-01T00:00',
            'ts_stop': '2050-01-01T00:00',
            'server': str(self.server.pk),
            'ajax': '1',
            **{k: str(v) for k, v in params.items()},
        })

    def _test_stats_api(self, **params):

        response = self.client.get('/json-api/v1/call_statistics/?{}'.format(self._get_params(**params)))
        self.assertEqual(response.status_code, 200)
        self.assertHaveSummary(response)
        self.assertTrue(response.json().get('graphs', {}).get('graph'))
        self.assertTrue(response.json().get('graphs', {}).get('sametime_graph'))

    @override_settings(ENABLE_GROUPS=False, ENABLE_ORGANIZATIONS=True)
    def test_stats_api_groups(self):
        self._test_stats_api()

    @override_settings(ENABLE_GROUPS=True, ENABLE_ORGANIZATIONS=False)
    def test_stats_api_org_unit(self):
        self._test_stats_api()

    def test_org_unit_filter(self):
        org_unit, created = OrganizationUnit.objects.get_or_create_by_full_name('test > test 2', self.customer)
        response = self.client.get('/json-api/v1/call_statistics/?{}'.format(self._get_params(organization=org_unit.pk)))
        self.assertEqual(response.status_code, 200)

    def test_tenant_filter(self):
        response = self.client.get('/json-api/v1/call_statistics/?{}'.format(self._get_params(tenant='none')))
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/json-api/v1/call_statistics/?{}'.format(self._get_params(tenant='other')))
        self.assertEqual(response.status_code, 200)

    def test_stats_api_graphs(self):

        response = self.client.get('/json-api/v1/call_statistics/graphs/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('graph'))
        self.assertTrue(response.json().get('sametime_graph'))

    def test_stats_api_debug(self):

        self.user.is_staff = True
        self.user.save()
        response = self.client.get('/json-api/v1/call_statistics/debug/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('calls'))
        self.assertTrue(response.json().get('legs'))

    def test_stats_api_settings(self):

        response = self.client.get('/json-api/v1/call_statistics/settings/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('choices'))

        response = self.client.get('/json-api/v1/room_statistics/settings/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('choices'))
