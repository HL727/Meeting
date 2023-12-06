from policy.tests.base import PolicyTestMixin


class PolicyReportTests(PolicyTestMixin):

    def get_url(self, path=None):
        return '/json-api/v1/policy/report/' + (path or '')

    def test_report(self):

        response = self.client.get(self.get_url())
        self.assertContains(response, 'soft_limit', status_code=200)


class CustomerPolicyTests(PolicyTestMixin):

    def get_url(self, path=None):
        return '/json-api/v1/customer_policy/' + (path or '')

    def test_list(self):

        response = self.client.get(self.get_url())
        self.assertContains(response, 'participant_limit', status_code=200)


class CustomerPolicyStateTests(PolicyTestMixin):

    def get_url(self, path=None):
        return '/json-api/v1/customer_policy_state/' + (path or '')

    def test_list(self):

        response = self.client.get(self.get_url())
        self.assertContains(response, 'active_participants', status_code=200)

