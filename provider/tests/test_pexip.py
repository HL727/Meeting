from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest


class PexipBaseTest(ConferenceBaseTest, APITestCase):
    def setUp(self):
        super().setUp()
        self._init() # base

        self.customer.lifesize_provider = self.pexip
        self.customer.save()

        self.api = self._get_api()
        self.bulk_url = reverse('cospace-pexip-bulk-create')

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

    def _get_api(self):
        provider = self.customer.get_provider()
        return provider.get_api(self.customer)


class PexipMiscTestCase(PexipBaseTest):

    def test_get_domain_from_rule(self):

        domains = self.api._get_domains_from_regex(r'.*@(test1|test2)\.(com|se)')
        self.assertEquals(set(domains), {'test1.com', 'test1.se', 'test2.com', 'test2.se'})

        domains = self.api._get_domains_from_regex(r'.*@test.com')
        self.assertEquals(set(domains), {'test.com'})

        domains = self.api._get_domains_from_regex(r'.*@test\.com')
        self.assertEquals(set(domains), {'test.com'})
