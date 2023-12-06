from datetime import timedelta
from urllib.parse import parse_qsl, urlparse

from django.utils.timezone import now

from customer.models import CustomerMatch
from policy.models import ClusterPolicy, CustomerPolicyState
from policy.tests.base import PolicyTestMixin

from policy_rule.models import PolicyRule, PolicyRuleHitCount
from policy_rule.tests.consts import POLICY_RULE_TEST_DATA

URL_EXAMPLE = ('/cdr/policy/asdfadsf/policy/v1/service/configuration?protocol=sip&node_ip=10.44.99.2'
               + '&registered=False&remote_address=10.44.75.249&version_id=16&bandwidth=0'
               + '&pseudo_version_id=36402.0.0&vendor=TANDBERG/518 (TC6.0.1.65adebe)&local_alias=65432'
               + '&remote_port=58435&call_direction=dial_in&remote_alias=sip:alice@example.com'
               + '&remote_display_name=Alice&trigger=invite&location=London')


URL_PARAMS = dict(parse_qsl(urlparse(URL_EXAMPLE).query))


class PexipPolicyTestCase(PolicyTestMixin):

    def setUp(self):
        super().setUp()
        self.cluster_policy = ClusterPolicy.objects.create(cluster=self.cluster, secret_key='asdfadsf')
        CustomerMatch.objects.create(cluster=self.cluster, prefix_match=self.target_alias, customer=self.customer)
        CustomerMatch.objects.create(cluster=self.cluster, prefix_match='meet', customer=self.customer)

    def test_service_empty(self):

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)

    def test_service_hard_limit(self):
        self.customer_policy.participant_normal_limit = 1
        self.customer_policy.participant_hard_limit = 1
        self.customer_policy.save()


        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)

        self.cluster_policy.hard_limit_action = ClusterPolicy.REJECT
        self.cluster_policy.save()

        state = CustomerPolicyState.objects.get(customer=self.customer)
        state.active_participants = 1
        state.save()

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'reject')

        # customer override
        self.customer_policy.hard_limit_action = ClusterPolicy.IGNORE
        self.customer_policy.save()
        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)

    def test_service_soft_limit(self):
        self.customer_policy.participant_normal_limit = 1
        self.customer_policy.participant_hard_limit = 10
        self.customer_policy.save()


        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)

        state = CustomerPolicyState.objects.get(customer=self.customer)
        state.active_participants = 1
        state.save()

        self.cluster_policy.soft_limit_action = ClusterPolicy.REJECT
        self.cluster_policy.save()

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'reject')

        # customer override
        self.customer_policy.soft_limit_action = ClusterPolicy.IGNORE
        self.customer_policy.save()
        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)

    def test_limit_quality(self):
        self.customer_policy.participant_normal_limit = 1
        self.customer_policy.save()


        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)

        state = CustomerPolicyState.objects.get(customer=self.customer)
        state.active_participants = 1
        state.save()

        self.cluster_policy.soft_limit_action = ClusterPolicy.QUALITY_SD
        self.cluster_policy.save()

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'continue')
        self.assertEqual(response.json()['result'].get('max_pixels_per_second'), 'sd')

        self.cluster_policy.soft_limit_action = ClusterPolicy.QUALITY_720P
        self.cluster_policy.save()

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'continue')
        self.assertEqual(response.json()['result'].get('max_pixels_per_second'), 'hd')

    def test_gateway_rule_toggle(self):

        self.cluster_policy.enable_gateway_rules = False
        self.cluster_policy.save()
        PolicyRule.objects.create(cluster=self.cluster, **{**POLICY_RULE_TEST_DATA, 'match_string': 'newname.*'})
        self.set_url_state('404conf')
        response = self.client.get(URL_EXAMPLE.replace(self.target_alias, 'newname.bob'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PolicyRuleHitCount.objects.values_list('count', flat=True).first(), 1)
        self.assertFalse(response.json().get('result'))

    def test_gateway_rule(self):

        self.cluster_policy.enable_gateway_rules = True
        self.cluster_policy.save()
        PolicyRule.objects.create(cluster=self.cluster, **{**POLICY_RULE_TEST_DATA, 'match_string': 'newname.*'})

        self.set_url_state('404conf')
        response = self.client.get(URL_EXAMPLE.replace(self.target_alias, 'newname.bob'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PolicyRuleHitCount.objects.count(), 1)
        self.assertEqual(PolicyRuleHitCount.objects.values_list('count', flat=True).first(), 1)

        PolicyRule.objects.create(cluster=self.cluster, **{**POLICY_RULE_TEST_DATA, 'match_string': 'meet.*'})
        self.client.get(URL_EXAMPLE.replace(self.target_alias, 'newname.bob'))
        self.assertEqual(PolicyRuleHitCount.objects.values_list('count', flat=True).first(), 2)

        self.assertTrue(response.json().get('result'))

    def test_skype_empty(self):
        url = '/cdr/policy/asdfadsf/policy/v1/service/configuration?P-Asserted-Identity="Alice"<sip:alice@example.com>&protocol=mssip&node_ip=10.47.2.43&registered=False&remote_address=10.47.2.20&version_id=16&bandwidth=0&pseudo_version_id=36402.0.0&vendor=UCCAPI/16.0.7967.5277 OC/16.0.7967.2139 (Skype for Business)&local_alias=sip:meet.alice@example.com&remote_port=63726&call_direction=dial_in&remote_alias=sip:alice@example.com&remote_display_name=Alice&trigger=invite&location=London'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_auth(self):
        CustomerMatch.objects.update(require_authorization=True)

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'reject')

        from policy_auth.models import PolicyAuthorization
        PolicyAuthorization.objects.create(customer=self.customer, cluster=self.cluster, user=self.user,
                                           local_alias=self.target_alias, valid_to=now() + timedelta(seconds=30))

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'continue')

    def test_auth_overrides(self):

        CustomerMatch.objects.update(require_authorization=True)

        from policy_auth.models import PolicyAuthorizationOverride
        l = PolicyAuthorizationOverride.objects.create(customer=self.customer, cluster=self.cluster, user=self.user,
                                       local_alias_match='333.*', remote_list='nonexistant',
                                       settings_override={
                                           'local_alias': r'/(.)5432/111\1@test.com/1116/',
                                       })

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'reject')

        l.remote_list = 'sip:alice@example.com'
        l.save()

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'reject')

        l.local_alias_match = self.target_alias + '.*'
        l.save()

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'continue')

        # override
        self.assertEqual(response.json().get('result')['local_alias'], '1116@test.com')

        # disable webrtc
        l.match_incoming_sip = False
        l.save()
        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('action'), 'reject')






