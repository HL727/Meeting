from datetime import timedelta
from urllib.parse import parse_qsl, urlencode

from django.contrib.auth.models import User
from django.utils.timezone import now

from conferencecenter.tests.base import ConferenceBaseTest
from meeting.models import Meeting
from organization.models import OrganizationUnit


class TestMeetingsApi(ConferenceBaseTest):

    def setUp(self):
        self._init()
        super().setUp()
        self.organization = OrganizationUnit.objects.create(name='test', customer=self.customer)
        self.organization2 = OrganizationUnit.objects.create(name='test', customer=self.customer)
        self.meeting = Meeting.objects.create(customer=self.customer,
                                              provider=self.customer.get_provider(),
                                              title='Testmeeting',
                                              ts_start=now(),
                                              ts_stop=now() + timedelta(hours=1),
                                              organization_unit=self.organization,
                                              backend_active=True,
                                              )
        User.objects.create_user(username='test', password='test', is_staff=True, is_superuser=True)
        self.client.login(username='test', password='test')

    def get_url(self, suffix='', **params):
        default_params = {
            'ts_start': now().isoformat(),
            'ts_stop': (now() + timedelta(hours=1)).isoformat(),
        }
        return '/json-api/v1/meeting/{}?{}'.format(suffix,
                                                   urlencode({**default_params, **(params or {})})
                                                   ).rstrip('?')

    def test_single(self):
        return  # TODO add api endpoint

    def test_list(self):
        response = self.client.get(self.get_url())
        self.assertContains(response, 'Testmeeting', status_code=200)

    def test_include_other(self):
        from provider.models.provider import Provider
        self.meeting.provider = Provider.objects.get_active('external')
        self.meeting.save()

        response = self.client.get(self.get_url())
        self.assertNotContains(response, 'Testmeeting', status_code=200)

        response = self.client.get(self.get_url(include_other='1'))
        self.assertNotContains(response, 'Testmeeting', status_code=200)

    def test_filter_empty(self):
        response = self.client.get(self.get_url(organization=self.organization2.id))
        self.assertNotContains(response, 'Testmeeting', status_code=200)

    def test_empty_text_filter(self):

        response = self.client.get(self.get_url(title='empty'))
        self.assertNotContains(response, 'Testmeeting', status_code=200)

    def test_valid_filter(self):
        response = self.client.get(self.get_url(organization=self.organization.id, title='test'))
        self.assertContains(response, 'Testmeeting', status_code=200)

    def test_related_organization_filter(self):
        return  # TODO test for endpoint/cospace/creator organization unit


