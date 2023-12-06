from conferencecenter.tests.base import ConferenceBaseTest
from meeting.models import Meeting
from provider.models.provider import TandbergProvider, LdapProvider
from .models import LdapSync, SeeviaSync
from datetime import timedelta, date
from django.urls import reverse

from os import environ
from django.conf import settings

LDAP_IP = environ.get('LDAP_IP') or getattr(settings, 'LDAP_IP', '')
LDAP_USERNAME = environ.get('LDAP_USERNAME') or getattr(settings, 'LDAP_USERNAME', '')
LDAP_PASSWORD = environ.get('LDAP_PASSWORD') or getattr(settings, 'LDAP_PASSWORD', '')


class LdapTestCase(ConferenceBaseTest):

    def test_ldap(self):

        try:
            import ldap  # noqa
        except ImportError:
            print('no ldap, skipping')
            return

        self._init()

        provider = LdapProvider.objects.create(title='test', ip=LDAP_IP, hostname=LDAP_IP,
            username=LDAP_USERNAME, password=LDAP_PASSWORD)

        LdapSync.objects.create(provider=provider, customer=self.customer, base_dn='test')

        LdapSync.objects.sync(self.customer)

    def test_tms(self):

        self._init()
        tb = TandbergProvider(hostname='localhost', mac_address='00:11:22:33:44', default_domain='example.org',
                              phonebook_url='phonebookservice.asmx?op=%s')

        result = tb.get_api().get_phonebooks()
        self.assertTrue(result)

    def test_seevia(self):

        self._init()
        self.customer.lifesize_provider = self.acano
        self.customer.save()
        c = self.client

        # book
        data = {
            'creator': 'john',
            'key': self.customer_shared_key,
            'internal_clients': 1,
            'room_info': '''[{"title": "test", "dialstring": "1.2.3.4##1234", "dialout": true}]''',
            'recording': '''{"record": true, "is_live": true, "is_public": true}''',
        }
        data['external_clients'] = 3

        data.update({
            'ts_start': '{}T060000Z'.format(str(date.today()).replace('-', '')),
            'ts_stop': '{}T050000Z'.format(str(date.today() + timedelta(days=1)).replace('-', '')),
        })

        files = {}
        c.post(reverse('api_book'), data, files=files)
        SeeviaSync.objects.sync(self.customer)

        # book another
        data['ts_start'] = '{}T070000Z'.format(str(date.today()).replace('-', '')),
        response = c.post(reverse('api_book'), data, files=files)
        self.assertEqual(response.status_code, 200)
        SeeviaSync.objects.sync(self.customer)

        # remove
        Meeting.objects.all().update(backend_active=False)

        SeeviaSync.objects.sync(self.customer)


