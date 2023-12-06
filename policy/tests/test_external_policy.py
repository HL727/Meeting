import re

from policy.models import ClusterPolicy, ExternalPolicy
from policy.tests.base import PolicyTestMixin
import requests_mock

from policy.tests.test_pexip_policy import URL_EXAMPLE


class ExternalPolicyTestCase(PolicyTestMixin):

    def setUp(self):
        super().setUp()
        self.cluster_policy = ClusterPolicy.objects.create(cluster=self.cluster, secret_key='asdfadsf')

        self.external_policy = ExternalPolicy.objects.create(
            target_alias_match=self.target_alias,
            policy=self.cluster_policy,
            settings_override={'override': 123},
            remote_url='http://localhost/policy/',
        )

    def test_external_policy(self):

        with requests_mock.Mocker() as m:
            m.get(
                re.compile(r'http://localhost/policy/'),
                json={'status': 'success', 'action': 'reject'},
            )
            response = self.client.get(URL_EXAMPLE)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['action'], 'reject')

        with requests_mock.Mocker() as m:
            m.get(
                re.compile(r'http://localhost/policy/'),
                json={'status': 'success', 'action': 'continue', 'result': {'test': 1}},
            )
            response = self.client.get(URL_EXAMPLE)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['result'], {'test': 1, 'override': 123})

    def test_url(self):

        self.assertEqual(
            self.external_policy.build_request_url({'test': 1}), 'http://localhost/policy/?test=1'
        )

        self.external_policy.remote_url += '?test=2&test2=3'

        self.assertEqual(
            self.external_policy.build_request_url({'test': 1}),
            'http://localhost/policy/?test=1&test2=3',
        )
