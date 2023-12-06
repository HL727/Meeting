from datastore.models.customer import Tenant
from datastore.models.pexip import Conference, ConferenceAlias
from policy.tests.base import PolicyTestMixin
from policy_rule.models import PolicyRule, PolicyRuleResponse
from . import consts


class PolicyRuleTestMixin(PolicyTestMixin):
    test_data = consts.POLICY_RULE_TEST_DATA

    def _init(self):
        PolicyTestMixin._init(self)
        def _create_rule(**kwargs):
            "Handle reuse for mock test server"
            return PolicyRuleTestMixin._create_rule(self, **kwargs)

        self.rule = _create_rule(match_string='34534543')
        self.conference = Conference.objects.create(provider=self.cluster, name='test')
        tenant = Tenant.objects.create(tid=self.customer.get_pexip_tenant_id(), provider=self.cluster)
        self.conference = Conference.objects.create(name='meet.webapp', cid=123, provider=self.cluster,
                                                    tenant=tenant)
        self.alias = ConferenceAlias.objects.create(conference=self.conference, alias='1234@local.com',
                                                    provider=self.cluster)

        self.rule_behind_conference = _create_rule(match_string='1234.*', name='behind conference')

        try:
            self.customer.get_api().get_related_policy_objects()
        except AttributeError:
            pass

    def _create_rule(self, **kwargs):
        return PolicyRule.objects.create(cluster=self.cluster, **{
            **{**consts.POLICY_RULE_TEST_DATA, **kwargs},
        })


class PolicyRuleTraceTestCase(PolicyRuleTestMixin):

    def get_url(self, path=None):
        return '/json-api/v1/policy_rule/' + (str(path).strip('/') + '/' if path else '')

    url = property(get_url)

    def test_related_objects(self):

        response = self.client.get('/json-api/v1/provider/related_policy_objects/')
        self.assertContains(response, status_code=200, text='system_location')

        self.assertTrue(response.json()['system_location'])
        self.assertTrue(response.json()['sip_proxy'])
        self.assertTrue(response.json()['teams_proxy'])
        self.assertTrue(response.json()['gms_access_token'])
        self.assertTrue(response.json()['h323_gatekeeper'])
        self.assertTrue(response.json()['mssip_proxy'])
        self.assertTrue(response.json()['stun_server'])
        self.assertTrue(response.json()['turn_server'])
        self.assertTrue(response.json()['ivr_theme'])

        self.cluster.pexip.refresh_from_db()
        self.assertFalse(self.cluster.pexip.should_refresh_system_objects())

    def test_conference(self):
        data = {
            'local_alias': 'sip:1234@local.com',
            'remote_alias': 'sip:1234@remote.com',
            'call_direction': 'dial_in',
            'protocol': 'sip',
            'is_registered': False,
            'location': '',
        }
        response = self.client.get(self.get_url('trace/'), data)
        self.assertContains(response, 'id', status_code=200)

        data = response.json()

        self.assert_(data.get('conference'))
        self.assertEqual(data['conference']['name'], 'meet.webapp')
        self.assertEqual(len(data['rules']), 1)

    def test_source_match(self):

        self._create_rule(match_string='123.*', match_source_alias=r'.*remote.com', name='New rule')

        data = {
            'local_alias': 'sip:12345@local.com',
            'remote_alias': 'sip:9876@remote.com',
            'call_direction': 'dial_in',
            'protocol': 'sip',
            'is_registered': False,
            'location': '',
        }
        response = self.client.get(self.get_url('trace/'), data)
        self.assertContains(response, 'id', status_code=200)

        data = response.json()

        self.assertFalse(data.get('conference'))
        self.assertEqual(len(data['rules']), 2)

    def test_outgoing(self):

        self._create_rule(match_string=r'.*remote.com')

        data = {
            'local_alias': 'sip:12345@local.com',
            'remote_alias': 'sip:9876@remote.com',
            'call_direction': 'dial_out',
            'protocol': 'sip',
            'is_registered': False,
            'location': '',
        }
        response = self.client.get(self.get_url('trace/'), data)
        self.assertContains(response, 'id', status_code=200)

        data = response.json()

        self.assertFalse(data.get('conference'))
        self.assertEqual(len(data['rules']), 1)


class PolicyRuleResponseTestCase(PolicyRuleTestMixin):

    def _get_response(self, **rule_kwargs):
        rule_kwargs = {
            'turn_server': 1,
            'stun_server': 1,
            'gms_access_token': 1,
            'mssip_proxy': 1,
            'h323_gatekeeper': 1,
            **rule_kwargs,
        }
        rule = self._create_rule(**rule_kwargs)
        container = PolicyRuleResponse(rule, {
            'call_direction': 'dial_in',
            'local_alias': '1234@local.com',
            'remote_alias': 'test@example.org'
        })
        return container.response()

    def test_empty(self):

        response = self._get_response(replace_string='\\1')
        self.assertEqual(response['name'].split(':')[0], self.rule.name)
        self.assertEqual(response['remote_alias'], '1234')
        self.assertEqual(response['description'], self.rule.description)

    def test_rtmp(self):
        response = self._get_response(outgoing_protocol='rtmp', called_device_type='unknown')
        self.assertEqual(response['outgoing_protocol'], 'rtmp')
        self.assertEqual(response['remote_alias'], '1234@local.com')
        self.assertEqual(response.get('called_device_type'), 'external')

    def test_sip(self):
        response = self._get_response(outgoing_protocol='sip', called_device_type='external')
        self.assertEqual(response['outgoing_protocol'], 'sip')
        self.assertEqual(response['called_device_type'], 'external')

    def test_mssip(self):
        response = self._get_response(outgoing_protocol='mssip', called_device_type='mssip')
        self.assertEqual(response['outgoing_protocol'], 'mssip')
        self.assertEqual(response['called_device_type'], 'mssip')

    def test_teams(self):
        response = self._get_response(outgoing_protocol='teams', called_device_type='teams')
        self.assertEqual(response['outgoing_protocol'], 'teams')
        self.assertEqual(response['called_device_type'], 'teams')

    def test_gms(self):
        response = self._get_response(outgoing_protocol='gms', called_device_type='gms')
        self.assertEqual(response['outgoing_protocol'], 'gms')
        self.assertEqual(response['called_device_type'], 'gms')


class EmptyPolicyRuleResponseTestCase(PolicyRuleTestMixin):

    def _get_response(self, **rule_kwargs):
        rule_kwargs = {
            'turn_server': 1,
            'stun_server': 1,
            'gms_access_token': 1,
            'mssip_proxy': 1,
            'h323_gatekeeper': 1,
            **rule_kwargs,
        }
        rule = self._create_rule(**rule_kwargs)
        container = PolicyRuleResponse(rule)
        return container.response()
