from django.contrib.auth.models import User
from django.test import RequestFactory

from conferencecenter.tests.base import ConferenceBaseTest

from django.contrib.admin import site

from customer.models import CustomerMatch
from policy.models import CustomerPolicy, CustomerPolicyState


class AdminTest(ConferenceBaseTest):

    def setUp(self):
        super().setUp()
        self._init()
        self.user = User.objects.create_user(username='test', password='test', is_staff=True, is_superuser=True)
        self.client.login(username='test', password='test')

        CustomerMatch.objects.create(cluster=self.pexip.cluster, customer=self.customer, regexp_match=r'.*regexp@.*regsuffix')
        self.customer_policy = CustomerPolicy.objects.create(customer=self.customer, participant_limit=5)
        self.customer_policy_state = CustomerPolicyState.objects.create(customer=self.customer, active_participants=10, cluster=self.pexip.cluster)


    def test_admin(self):

        request = RequestFactory().get('/admin/')
        request.user = self.user
        app_list = site.get_app_list(request)

        for app in app_list:
            for model in app['models']:
                response = self.client.get(model['admin_url'])
                self.assertEqual(response.status_code, 200, '{} should work'.format(model['admin_url']))

                if model.get('add_url'):
                    response = self.client.get(model['add_url'])
                    self.assertEqual(response.status_code, 200, '{} should work'.format(model['add_url']))

    def test_single_objects(self):


        urls = [
            '/admin/provider/provider/{}/change/'.format(self.acano.pk),
            '/admin/provider/cluster/{}/change/'.format(self.acano.cluster_id),
            '/admin/provider/provider/{}/change/'.format(self.pexip.pk),
            '/admin/provider/cluster/{}/change/'.format(self.pexip.cluster_id),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEquals(response.status_code, 200, '{} should work'.format(url))


