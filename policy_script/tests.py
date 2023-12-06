from django.http import QueryDict

from datastore.utils.pexip import sync_all_pexip
from policy.models import ClusterPolicy
from policy.tests.base import PolicyTestMixin
from policy.tests.test_pexip_policy import URL_EXAMPLE, URL_PARAMS
from policy.views import get_policy_service_response
from policy_script.models import ClusterPolicyScript, get_cluster_policy_response


class TestPolicyView(PolicyTestMixin):
    def setUp(self):
        super().setUp()
        self.cluster_policy = ClusterPolicy.objects.create(
            cluster=self.cluster, secret_key='asdfadsf'
        )

    def test_policy_views(self):

        from policy_script.models import ClusterPolicyScript

        ClusterPolicyScript.objects.create(
            cluster=self.cluster,
            content='''
        % if request.local_alias == '65432':
        send_response(response, {'override': 1},
            local_alias='bob2')
        % endif
            ''',
        )

        response = self.client.get(URL_EXAMPLE)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEquals(data.get('override'), 1)
        self.assertEquals(data['result']['local_alias'], 'bob2')

    def synced_policy_view(self):
        sync_all_pexip(self.pexip.cluster)
        response = get_policy_service_response(
            self.cluster_policy, QueryDict(URL_EXAMPLE.split('?')[-1])
        ).get_response_data()
        self.assertTrue(response.get('result'))
        self.test_policy_views()


class TestClusterPolicyScript(PolicyTestMixin):
    def _run_script(self, content: str, require_response=None):

        ClusterPolicyScript.objects.create(cluster=self.cluster, content=content)

        response, has_response = get_cluster_policy_response(self.cluster, URL_PARAMS, {})

        if require_response is not None:
            self.assertEqual(has_response, require_response)

        return response

    def test_send_response(self):

        response = self._run_script(
            '''
        % if request.local_alias == '65432':
        send_response(response, {'override': 1},
            local_alias='bob2')
        % endif
            ''',
            require_response=True,
        )

        self.assertEquals(response.get('override'), 1)
        self.assertEquals(response.get('status'), 'success')
        self.assertTrue(response.get('action') in ('continue', None))
        self.assertEquals(response['result']['local_alias'], 'bob2')

    def test_exit(self):

        response = self._run_script(
            '''
        % if request.local_alias == '65432':
            exit()
        % endif
            ''',
            require_response=False,
        )

        self.assertEquals(response, None)

    def test_deny(self):

        response = self._run_script(
            '''
        % if request.local_alias == '65432':
            deny()
        % endif
            ''',
            require_response=True,
        )

        self.assertEquals(response.get('status'), 'success')
        self.assertEquals(response.get('action'), 'reject')
