from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from policy.models import CustomerPolicy, CustomerPolicyState
from provider.models.pexip import PexipCluster
from provider.models.provider import Cluster


class PolicyTestMixin(ConferenceBaseTest, APITestCase):

    target_alias = '65432'

    def setUp(self) -> None:
        super().setUp()
        super()._init()
        self.customer.lifesize_provider = self.pexip
        self.customer.save()

        self._init()
        self.user = User.objects.create_user(username='test', password='test', is_staff=True)
        self.client.login(username='test', password='test')


    def _init(self):
        self.cluster = self.pexip.cluster.pexip
        self.customer.get_pexip_tenant_id()

        self.customer_policy = CustomerPolicy.objects.create(customer=self.customer, participant_limit=5)
        self.customer_policy_state = CustomerPolicyState.objects.create(customer=self.customer,
                                                                        active_participants=10,
                                                                        cluster=self.cluster)

    def _create_separate_cluster_and_customer(self):
        from provider.models.provider import Provider
        from customer.models import Customer

        provider = Provider.objects.create(subtype=Provider.SUBTYPES.pexip)
        customer = Customer.objects.create(title='Customer3', lifesize_provider=provider)
        provider.cluster.pexip.default_customer = customer
        provider.cluster.pexip.save()

        return provider, customer
