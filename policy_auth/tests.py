from datetime import timedelta
from hashlib import md5

from django.contrib.auth.models import User
from django.utils.timezone import now
from rest_framework.test import APITestCase

from customer.models import Customer, CustomerMatch
from policy_auth.models import PolicyAuthorization, PolicyAuthorizationOverride, match_regexp, md5_match
from provider.models.provider import Cluster
from supporthelpers.models import CustomerPermission


class PolicyAuthTestCase(APITestCase):

    def setUp(self):
        self.cluster = Cluster.objects.create(type=Cluster.TYPES.pexip_cluster, api_host='localhost')

        self.customer1 = Customer.objects.create(title='customer1', lifesize_provider=self.cluster)
        self.customer2 = Customer.objects.create(title='customer2', lifesize_provider=self.cluster)
        self.customer3 = Customer.objects.create(title='customer3', lifesize_provider=self.cluster)

        CustomerMatch.objects.create(customer=self.customer1, cluster=self.cluster, prefix_match='111')
        CustomerMatch.objects.create(customer=self.customer2, cluster=self.cluster, prefix_match='222')
        CustomerMatch.objects.create(customer=self.customer3, cluster=self.cluster, prefix_match='333')

        self.user = user = User.objects.create_user(username='test', password='test')
        CustomerPermission.objects.create(user=user, customer=self.customer1)
        CustomerPermission.objects.create(user=user, customer=self.customer2)
        # no permission to customer 3
        self.client.login(username='test', password='test')

    def test_override(self):

        response = self.client.post(
            '/json-api/v1/policy_authorization_override/',
            {
                'cluster': self.cluster.pk,
                'local_alias_match': r'111.*',
                'remote_list': 'test@test.com\nsip:test2@test.com\n{"remote_alias": "test3@test.com"}',
                'settings_override': {},
            },
            format='json',
        )

        self.assertContains(response, 'local_alias_match', status_code=201)

        match = PolicyAuthorizationOverride.objects.match(
            self.customer1,
            {'local_alias': '11123', 'remote_alias': 'other@test.com', 'protocol': 'sip'},
            cluster=self.cluster,
        )
        self.assertFalse(match)

        match = PolicyAuthorizationOverride.objects.match(
            self.customer1,
            {'local_alias': '33', 'remote_alias': 'test2@test.com', 'protocol': 'sip'},
            cluster=self.cluster,
        )
        self.assertFalse(match)  # explicit protocol in match value

        match = PolicyAuthorizationOverride.objects.match(
            self.customer1,
            {'local_alias': '33', 'remote_alias': 'test@test.com', 'protocol': 'sip'},
            cluster=self.cluster,
        )
        self.assertFalse(match)

        match = PolicyAuthorizationOverride.objects.match(
            self.customer1,
            {'local_alias': '11123', 'remote_alias': 'sip:test@test.com', 'protocol': 'sip'},
            cluster=self.cluster,
        )
        self.assertTrue(match)

        match = PolicyAuthorizationOverride.objects.match(
            self.customer1,
            {'local_alias': 'sip:11123', 'remote_alias': 'sip:test@test.com', 'protocol': 'sip'},
            cluster=self.cluster,
        )
        self.assertTrue(match)

        match = PolicyAuthorizationOverride.objects.match(
            self.customer1,
            {'local_alias': '11123', 'remote_alias': 'sip:test3@test.com', 'protocol': 'sip'},
            cluster=self.cluster,
        )
        self.assertTrue(match)

    def test_auth_timeout(self):

        response = self.client.post('/json-api/v1/policy_authorization/', {
            'local_alias': r'1111@test.com',
            'require_fields': {'name': 'test'},
            'timeout': 30,
        }, format='json')

        self.assertContains(response, 'local_alias', status_code=201)

    def test_get(self):

        auth = PolicyAuthorization.objects.create(customer=self.customer1, cluster=self.cluster, local_alias='1111@test.com',
                                           valid_to=now() + timedelta(seconds=30), require_fields={'name': 'test'}, user=self.user)

        response = self.client.get('/json-api/v1/policy_authorization/{}/'.format(auth.pk), {
            'local_alias': r'1111@test.com',
            'require_fields': {'name': 'test'},
            'timeout': 30,
        }, format='json')

        self.assertContains(response, 'local_alias', status_code=200)

    def test_match(self):

        PolicyAuthorization.objects.create(customer=self.customer1, cluster=self.cluster, local_alias='1111@test.com',
                                           valid_to=now() + timedelta(seconds=30), require_fields={'name': 'test'}, user=self.user)

        match = PolicyAuthorization.objects.match(self.customer1, {'local_alias': '1111@test.com', 'name': 'test'}, cluster=self.cluster)
        self.assertNotEquals(match, None)

        # diff
        match = PolicyAuthorization.objects.match(self.customer1, {'local_alias': '1111@test.com', 'name': 'test2'}, cluster=self.cluster)
        self.assertEqual(match, None)

    def test_regexp_match(self):

        target = 'user@test.com'

        result = match_regexp(r'/other.com/', target)
        self.assertEqual((False, target), result)

        result = match_regexp(r'/.*test.com/', target)
        self.assertEqual((True, target), result)

        result = match_regexp(r'/(.*)test.com/\1example.org/', target)
        self.assertEqual((True, 'user@example.org'), result)

        result = match_regexp(r'/.*test.com/example.org/user@other.org/', target)
        self.assertEqual((False, target), result)

        result = match_regexp(r'/(.*)test.com/\1example.org/user@example.org/', target)
        self.assertEqual((True, 'user@example.org'), result)

        result = match_regexp(r'/(.*)test.com//user/', target)
        self.assertEqual((True, target), result)

    def test_md5_match(self):

        obj = {'name': 'test', 'value2': 'test2'}
        self.assertEqual(True, md5_match(obj, ['name', 'other', 'value2'], md5(b'testtest2').hexdigest()))

        obj['other'] = 'test'
        self.assertEqual(False, md5_match(obj, ['name', 'other', 'value2'], md5(b'testtest2').hexdigest()))


    def test_auth_valid_to(self):

        response = self.client.post('/json-api/v1/policy_authorization/', {
            'local_alias': r'1111@test.com',
            'valid_to': now() + timedelta(hours=1),
        }, format='json')

        self.assertContains(response, 'local_alias', status_code=201)
        self.assertEqual(PolicyAuthorization.objects.get().customer, self.customer1)

    def test_auth_valid_invalid(self):

        response = self.client.post('/json-api/v1/policy_authorization/', {
            'local_alias': r'1111@test.com',
            'valid_from': now() + timedelta(hours=1),
            'valid_to': now() - timedelta(hours=1),
        }, format='json')

        self.assertContains(response, 'valid_to', status_code=400)

    def test_other_user(self):

        response = self.client.post('/json-api/v1/policy_authorization/', {
            'local_alias': r'2222@test.com',
            'valid_to': now() + timedelta(hours=1),
        }, format='json')

        self.assertContains(response, 'local_alias', status_code=201)
        self.assertEqual(PolicyAuthorization.objects.get().customer, self.customer2)

    def test_source(self):

        response = self.client.post(
            '/json-api/v1/policy_authorization/',
            {
                'local_alias': r'2222@test.com',
                'valid_to': now() + timedelta(hours=1),
                'source': 'test',
                'external_id': '1234',
            },
            format='json',
        )

        self.assertContains(response, 'local_alias', status_code=201)
        self.assertEqual(PolicyAuthorization.objects.get().source, 'test')

    def test_source_rewrite(self):

        response = self.client.post(
            '/json-api/v1/policy_authorization/',
            {
                'local_alias': r'2222@test.com',
                'valid_to': now() + timedelta(hours=1),
                'source': '2c755280-d36b-43ca-8f5d-ae94880fecb8',
            },
            format='json',
        )

        self.assertContains(response, 'local_alias', status_code=201)
        self.assertEqual(PolicyAuthorization.objects.get().source, '')

    def test_invalid_user(self):

        response = self.client.post('/json-api/v1/policy_authorization/', {
            'local_alias': r'3333@test.com',
            'valid_to': now() + timedelta(hours=1),
        }, format='json')

        self.assertContains(response, 'local_alias', status_code=403)
