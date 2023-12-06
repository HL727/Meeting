from policy.tests.base import PolicyTestMixin
from policy_rule.models import PolicyRule
from . import consts


class PolicyRuleTestCase(PolicyTestMixin):

    test_data = consts.POLICY_RULE_TEST_DATA

    def setUp(self):
        super().setUp()
        self.rule = PolicyRule.objects.create(cluster=self.cluster, name='test', enable=True, sync_back=False)

    def get_url(self, path=None):
        return '/json-api/v1/policy_rule/' + (str(path).strip('/') + '/' if path else '')

    url = property(get_url)

    def test_list(self):

        response = self.client.get(self.get_url())
        self.assertContains(response, 'id', status_code=200)

    def test_single(self):

        response = self.client.get(self.get_url(self.rule.id))
        self.assertContains(response, 'id', status_code=200)

    def test_create(self):

        response = self.client.post(self.url, self.test_data, format='json')
        self.assertContains(response, 'id', status_code=201)
        self.assertEqual(PolicyRule.objects.get(pk=response.json()['id']).external_id, None)

    def test_create_sync(self):

        response = self.client.post(self.url, {**self.test_data, 'sync_back': True}, format='json')
        self.assertContains(response, 'id', status_code=201)
        self.assertNotEquals(PolicyRule.objects.get(pk=response.json()['id']).external_id, None)

    def test_update(self):

        response = self.client.patch(self.get_url(self.rule.pk), self.test_data, format='json')
        self.assertContains(response, 'id', status_code=200)
        self.assertEqual(PolicyRule.objects.get(pk=response.json()['id']).external_id, None)

    def test_update_sync(self):

        response = self.client.patch(self.get_url(self.rule.pk), {**self.test_data, 'sync_back': True}, format='json')
        self.assertContains(response, 'id', status_code=200)
        self.assertNotEquals(PolicyRule.objects.get(pk=response.json()['id']).external_id, None)

    def test_sync(self):

        self.rule.delete()
        PolicyRule.objects.sync_down(self.cluster)
