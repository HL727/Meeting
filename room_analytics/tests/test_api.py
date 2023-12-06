
from django.urls import reverse

from customer.models import Customer
from organization.models import OrganizationUnit
from room_analytics.tests.test_stats import PeopleCountTestBase
from statistics.models import ServerTenant, Tenant, Leg, Server
from statistics.tests.test_views import StatsViewsBase


class EPMStatsBase(PeopleCountTestBase, StatsViewsBase):

    def setUp(self):
        super().setUp()
        self.people_server = Server.objects.create(customer=self.customer, type=Server.ENDPOINTS)
        Leg.objects.all().update(endpoint=self.endpoint)


class EPMStatsViewsTestCase(EPMStatsBase):

    def test_stats(self):

        response = self.client.get(reverse('endpoint_statistics') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}'.format(self.server.id))
        self.assertEqual(response.status_code, 200)

    def test_stats_ajax(self):

        response = self.client.get(reverse('endpoint_statistics') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(response.json().get('summary').values()))
        self.assertTrue(response.json().get('graphs', {}).get('graph'))

    def test_stats_endpoint_id(self):

        response = self.client.get(reverse('endpoint_statistics') + '?ts_start=2011-01-01&ts_stop=2050-01-01&endpoints={}&server={}&ajax=1'.format(self.endpoint.id, self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(response.json().get('summary').values()))
        self.assertTrue(response.json().get('graphs', {}).get('graph'))

    def test_stats_endpoint_id_404(self):

        response = self.client.get(reverse('endpoint_statistics') + '?ts_start=2011-01-01&ts_stop=2050-01-01&endpoints={}&server={}&ajax=1'.format(999999, self.server.id))
        self.assertEqual(response.status_code, 400)

    def test_stats_no_endpoint(self):
        self.endpoint.delete()
        response = self.client.get(reverse('endpoint_statistics') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(response.json().get('summary', {}).get('cospace', {}).values()))
        self.assertFalse(response.json().get('graphs', {}).get('graph'))

    def test_combined_stats_ajax(self):

        response = self.client.get(reverse('endpoint_statistics') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1'.format(self.combined_server.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(response.json().get('summary').values()))
        self.assertTrue(response.json().get('graphs', {}).get('graph'))

    def test_stats_settings(self):

        response = self.client.get(reverse('endpoint_statistics') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1&only_settings=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        choices = response.json().get('choices', {})

        endpoint_servers = Server.objects.filter(type=Server.ENDPOINTS).values_list('pk', 'customer')
        tenant_id = 'endpoint.{}.{}'.format(*endpoint_servers[0])

        self.assertEqual(choices['tenant'], [[tenant_id, str(self.customer)]])
        self.assertTrue(choices['server'])

    def test_stats_settings_multitenant(self):

        customer2 = Customer.objects.create(title='test2', acano_tenant_id='asdf')
        ServerTenant.objects.create(server=self.server, tenant=Tenant.objects.create(guid=customer2.acano_tenant_id or ''))
        response = self.client.get(reverse('endpoint_statistics') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server={}&ajax=1&only_settings=1&multitenant=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        choices = response.json().get('choices', {})

        endpoint_servers = Server.objects.filter(type=Server.ENDPOINTS).values_list('pk', 'customer')

        tenants = [t[0] for t in choices.get('tenant', [])]
        self.assertEqual(tenants, ['', 'none', 'endpoint.{}.{}'.format(*endpoint_servers[0]), customer2.acano_tenant_id])
        self.assertTrue(choices['server'])

    def test_stats_excel(self):

        response = self.client.get(reverse('endpoint_statistics_excel') + '?ts_start=2011-01-01&ts_stop=2050-01-01&server=1')
        self.assertEqual(response.status_code, 200)


class EPMPeopleCountStatsAPITestCase(EPMStatsBase):
    def test_dashboard_api(self):

        response = self.client.get('/json-api/v1/room_statistics/dashboard/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&server={}&ajax=1'.format('person'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('graphs', {}).get('now'))
        self.assertTrue(response.json().get('graphs', {}).get('per_hour'))
        self.assertTrue(response.json().get('graphs', {}).get('per_day'))

    def test_stats_api(self):

        response = self.client.get('/json-api/v1/room_statistics/head_count/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&ajax=1&fill_gaps=1')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('graphs', {}).get('now'))
        self.assertTrue(response.json().get('graphs', {}).get('per_hour'))
        self.assertTrue(response.json().get('graphs', {}).get('per_day'))
        self.assertFalse(response.json().get('graphs', {}).get('empty'))

    def test_org_unit_filter(self):
        org_unit = OrganizationUnit.objects.create(customer=self.customer, name='test')

        response = self.client.get('/json-api/v1/room_statistics/head_count/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&organization={}&ajax=1&fill_gaps=1'.format(org_unit.pk))
        self.assertEqual(response.status_code, 200)

        self.assertTrue(response.json().get('graphs', {}).get('empty'))

        self.endpoint.org_unit = org_unit
        self.endpoint.save()

        response = self.client.get('/json-api/v1/room_statistics/head_count/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&organization={}&ajax=1&fill_gaps=1'.format(org_unit.pk))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get('graphs', {}).get('empty'))


class EPMCallStatsAPITestCase(EPMStatsBase):

    def test_stats_api(self):

        response = self.client.get('/json-api/v1/room_statistics/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(response.json().get('summary').values()))
        self.assertFalse(response.json().get('graphs', {}).get('now'))
        self.assertFalse(response.json().get('graphs', {}).get('per_hour'))
        self.assertFalse(response.json().get('graphs', {}).get('per_day'))

    def test_stats_no_endpoint(self):
        self.endpoint.delete()
        response = self.client.get('/json-api/v1/room_statistics/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(response.json().get('summary', {}).get('cospace', {}).values()))
        self.assertFalse(any(response.json().get('graph', {}).values()))

    def test_stats_api_graphs(self):

        response = self.client.get('/json-api/v1/room_statistics/graphs/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get('now'))
        self.assertFalse(response.json().get('per_hour'))
        self.assertFalse(response.json().get('per_day'))

    def test_stats_api_settings(self):

        response = self.client.get('/json-api/v1/room_statistics/settings/?ts_start=2011-01-01T00:00&ts_stop=2050-01-01T00:00&server={}&ajax=1'.format(self.server.id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('choices'))

        response = self.client.get('/json-api/v1/room_statistics/settings/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('choices'))
