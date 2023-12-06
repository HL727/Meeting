from django.test import TestCase

from customer.models import Customer, CustomerMatch, clear_cache
from provider.models.provider import Cluster


class KeyTestCase(TestCase):

    def test_iter_keys(self):
        keys = list(Customer.objects.iter_all_keys('key0,key1,key2,key3'))
        self.assertEquals(keys, ['key1,key2,key3', 'key1,key2', 'key2,key3', 'key1', 'key2', 'key3'])


class MatcherTestCase(TestCase):

    def setUp(self):

        cluster = Cluster.objects.create(title='test', type=Cluster.TYPES.pexip_cluster)
        customer = Customer.objects.create(title='test', lifesize_provider=cluster)
        customer2 = Customer.objects.create(title='test', pexip_tenant_id='1234', lifesize_provider=cluster)

        CustomerMatch.objects.create(cluster=cluster, customer=customer, prefix_match='prefix')
        CustomerMatch.objects.create(cluster=cluster, customer=customer, suffix_match='suffix')
        CustomerMatch.objects.create(cluster=cluster, customer=customer, regexp_match=r'.*regexp@.*regsuffix')

        CustomerMatch.objects.create(cluster=cluster, customer=customer2, priority=0,
                                     prefix_match='prefix', suffix_match='suffix')

        self.cluster = cluster
        self.customers = [customer, customer2]

        clear_cache(None)

    def test_match_empty(self):

        match = CustomerMatch.objects.get_match_from_text('test.room@example.org', cluster=self.cluster)
        self.assertEqual(match, None)

    def test_match_prefix(self):

        match = CustomerMatch.objects.get_match_from_text('prefix.room@example.org', cluster=self.cluster)
        self.assertEqual(getattr(match, 'customer_id', None), self.customers[0].id)

    def test_match_both(self):
        match = CustomerMatch.objects.get_match_from_text('prefix.room@example.org.suffix', cluster=self.cluster)
        self.assertNotEqual(match, None)
        self.assertEqual(getattr(match, 'customer_id', None), self.customers[1].id)

    def test_match_object_alias(self):

        match = CustomerMatch.objects.get_match({
            'aliases': [{'alias': 'prefix.room.example.org'}]
        }, cluster=self.cluster)

        self.assertEqual(getattr(match, 'customer_id', None), self.customers[0].id)

    def test_match_object_tag(self):

        match = CustomerMatch.objects.get_match({
            'tag': 't=1234',
        }, cluster=self.cluster)

        self.assertEqual(getattr(match, 'customer_id', None), self.customers[1].id)

    def test_match_object_tag_wrong_cluster(self):

        self.customers[1].lifesize_provider = None
        self.customers[1].save()

        match = CustomerMatch.objects.get_match({
            'tag': 't=1234',
        }, cluster=self.cluster)

        self.assertEqual(getattr(match, 'customer_id', None), None)
        self.assertEqual(getattr(match, 'tenant_id', None), '1234')


