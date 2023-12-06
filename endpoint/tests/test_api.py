import json
import re
import binascii
from os import path

from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.core.files.base import ContentFile
from django.utils.timezone import now
from django.utils.encoding import force_bytes
from django.conf import settings

from conferencecenter.tests.base import ThreadedTestCase
from endpoint.tests.base import EndpointBaseTest
from endpoint.ext_api.base import EndpointProviderAPI
from endpoint_provision.models import EndpointFirmware, EndpointTask
from endpoint_provision.views_tms_provision import get_endpoint_tms_response
from organization.models import OrganizationUnit

from ..models import CustomerSettings, Endpoint


root = path.dirname(path.abspath(__file__))


class TestSingleAPIViews(EndpointBaseTest):

    def test_validate_ca_certificate(self):
        """Validate certificate and return tuple with content, sha1- and sha256-fingerprint"""
        with open('test.pem', 'r') as certfile:
            certificate_content = certfile.read()
            certificate_list = EndpointProviderAPI.validate_ca_certificates(certificate_content=certificate_content)
            print(certificate_list)

    def _get_url(self, args):
        return '/json-api/v1/endpoint/{}/{}'.format(self.endpoint.id, args)

    def test_set_configuration(self):
        data = {
            'settings': [{'key': ['Network', 'Alias'], 'value': '1'}, ],
        }
        response = self.client.post(self._get_url('set_configuration/'), data, format='json')
        self.assertContains(response, 'Configuration', status_code=200)

    def test_run_command(self):

        data = {
            'command': ['UserManagement', 'User', 'List'],
            'arguments': {'test': 1},
            'body': None,
        }
        response = self.client.post(self._get_url('run_command/'), data, format='json')
        self.assertContains(response, '<UserListResult', status_code=200)

    def test_api_backup(self):

        count = EndpointTask.objects.filter(endpoint=self.endpoint).count()
        response = self.client.post(self._get_url('backup/'))
        data = response.json()

        self.assertEqual(data['status'], 'OK')

        count2 = EndpointTask.objects.filter(endpoint=self.endpoint).count()
        self.assertEqual(count, count2 - 1)

        from endpoint_backup.models import EndpointBackup

        backup = EndpointBackup.objects.get()

        EndpointTask.objects.all().delete()
        response = self.client.post('/json-api/v1/endpointbackup/{}/restore/'.format(backup.pk))
        self.assertContains(response, text='OK', status_code=200)

        t = EndpointTask.objects.get(action='configuration')
        self.assertIn('Dereverberation', json.dumps(t.data.configuration))
        self.assertEqual(len(t.data.configuration), 223)


    def test_api_firmware(self):

        count = EndpointTask.objects.filter(endpoint=self.endpoint).count()

        firmware = EndpointFirmware.objects.create(customer=self.customer,
                                                   manufacturer=Endpoint.MANUFACTURER.CISCO_CE,
                                                   file=ContentFile('test', name='test.bin')
                                                   )
        response = self.client.post(self._get_url('install_firmware/'), {'firmware': firmware.pk})
        self.assertEqual(response.status_code, 200)
        data = response.json()

        count2 = EndpointTask.objects.filter(endpoint=self.endpoint).count()
        self.assertEqual(count, count2 - 1)

        self.assertEqual(data['status'], 'OK')

    def test_api_bookings(self):

        meeting = self._book_meeting()
        meeting.endpoints.add(self.endpoint)

        response = self.client.get(self._get_url('bookings/'))
        data = response.json()

        self.assertEqual(len(data), 1)

        xml = get_endpoint_tms_response(self.endpoint)
        safe_xml_fromstring(xml)

    def test_is_up(self):
        self.endpoint.set_status(status=10)
        response = self.client.get(self._get_url('is_up/'))
        self.assertContains(response, text='OK', status_code=200)

        self.endpoint.set_status(status=1)
        response = self.client.get(self._get_url('is_up/'))
        self.assertContains(response, text='WARNING', status_code=200)

        response = self.client.get(self._get_url('is_up/?warnings_code=402'))
        self.assertContains(response, text='WARNING', status_code=402)

        self.endpoint.set_status(status=0)

        response = self.client.get(self._get_url('is_up/'))
        self.assertContains(response, text='ERROR', status_code=200)
        response = self.client.get(self._get_url('is_up/?error_code=402'))
        self.assertContains(response, text='ERROR', status_code=402)

    def test_set_sip_aliases(self):

        aliases = ['test3@example.org', 'test2@example.org']

        response = self.client.post(self._get_url('set_sip_aliases/'), {'sip': aliases})
        data = response.json()

        self.assertEqual(data['id'], self.endpoint.id)
        self.assertEqual(sorted(data['sip_aliases']), sorted(aliases))

    def test_update(self):
        response = self.client.patch(self._get_url(''), {'mac': '00:11:22:33:44:55'})
        self.assertContains(response, text=self.endpoint.id, status_code=200)
        self.assert_(response.json()['id'])


class TestManyAPIViews(EndpointBaseTest, ThreadedTestCase):

    def _get_url(self, args):
        return '/json-api/v1/endpoint/{}'.format(args)

    def test_create(self, hostname=''):

        response = self.client.post(self._get_url(''), {
            'ip': '127.0.0.1',
            'hostname': hostname or '',
            'username': 'test',
            'password': 'test'
        })

        self.assertContains(response, text='test', status_code=201)
        self.assert_(response.json()['id'])

    def test_create_blank_ip(self):
        data = {
            "title": "test",
            "hostname": "",
            "sip": "",
            "connection_type": 1,
            "proxy": None,
            "h323": "",
            "h323_e164": "",
            "manufacturer": 10,
            "ip": "",
            "api_port": 443,
            "room_capacity": None,
            "track_ip_changes": True,
            "dial_protocol": "",
            "location": "",
            "username": "admin",
            "password": "__try__",
            "org_unit": None,
            "try_standard_passwords": True,
        }
        response = self.client.post(self._get_url(''), data, format='json')
        self.assertNotContains(response, text='test', status_code=400)

        data.update({
            'hostname': 'non-empty',
        })
        response = self.client.post(self._get_url(''), data, format='json')
        self.assertContains(response, text='test', status_code=201)

        data.update({
            'hostname': '',
            'connection_type': Endpoint.CONNECTION.PASSIVE,
        })
        response = self.client.post(self._get_url(''), data, format='json')
        self.assertContains(response, text='test', status_code=201)

        self.assert_(response.json()['id'])

    def test_create_auth_error(self):
        self.test_create(hostname='auth_error')

    def test_create_reponse_error(self):
        self.test_create(hostname='response_error')

    def test_create_empty_org_path(self):

        response = self.client.post(self._get_url(''), {
            'ip': '127.0.0.1',
            'username': 'test',
            'password': 'test',
            'organization_path': '',
        })

        self.assertContains(response, text='test', status_code=201)
        self.assert_(response.json()['id'])
        self.assertEqual(response.json()['org_unit'], None)

    def test_export(self):

        self.endpoint.status.ts_last_online = now()
        self.endpoint.status.save()

        response = self.client.post(self._get_url('export/'), {
            'endpoints': [self.endpoint.pk]
        }, format='json')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(self._get_url('export/?endpoints={}'.format(self.endpoint.pk)),
                                   format='json')
        self.assertEqual(response.status_code, 200)

    def test_bulk_create(self):

        response = self.client.post(self._get_url('bulk_create/'),[
            {
                'ip': '127.0.0.1',
                'hostname': 'response_error',
                'username': 'test',
                'password': '__try__',
                'organization_path': 'testar123',
            },
            {
                'ip': '127.0.0.1',
                'hostname': 'auth_error',
                'username': 'test',
                'password': '__try__',
                'organization_path': 'testar123',
            }
        ] + [{
            'ip': '127.0.0.1',
            'username': 'test',
            'password': 'test',
            'organization_path': 'testar123',
        }] * 4, format='json')

        self.assertContains(response, text='test', status_code=201)
        self.assertEqual(len(response.json()), 6)
        self.assertTrue(all(e['org_unit'] for e in response.json()))
        self.assertEqual(len({e['org_unit'] for e in response.json()}), 1)
        self.assert_(all(x['id'] for x in response.json()))

    def test_excel_bulk_update(self):
        READDED = False  # TODO re-add api view with EndpointBulkSerializer
        if not READDED:
            return

        data = [
            {'mac_address': self.endpoint.mac_address, 'title': 'NEW'},
            {'mac_address': '00:00:00:00:00:00'},
        ]
        response = self.client.post(self._get_url('bulk_update/'), data, format='json')

        self.assertContains(response, text='NEW', status_code=201)

        self.assertEqual(response.json()[0]['id'], self.endpoint.id)
        self.assertEqual(response.json()[0].get('unmatched', False), False)
        self.assertEqual(response.json()[0]['title'], 'NEW')

        self.assertEqual(response.json()[1].get('id'), None)
        self.assertEqual(response.json()[1].get('unmatched'), True)

        # invalid id
        data.append({'id': 12345, 'title': 'test'})
        response = self.client.post(self._get_url('bulk_update/'), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['id'], ['12345'])

    def test_bulk_update(self):

        data = {
            'org_unit': OrganizationUnit.objects.get_or_create_by_full_name('Test > test', self.customer)[0].pk,
            'password': 'test',
            'location': 'location',
            'room_capacity': 5,
            'endpoints': [self.endpoint.pk],
        }
        response = self.client.put(self._get_url('bulk_update/'), data, format='json')
        self.assertContains(response, text='location', status_code=201)

        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.org_unit_id, data['org_unit'])
        self.assertEqual(self.endpoint.location, data['location'])
        self.assertEqual(self.endpoint.room_capacity, data['room_capacity'])
        self.assertEqual(self.endpoint.password, data['password'])


class EndpointReportTestCase(ThreadedTestCase, EndpointBaseTest):
    @property
    def url(self):
        return '/json-api/v1/endpoint/report/'

    def test_report(self):

        self.endpoint.status.ts_last_online = now()
        self.endpoint.status.save()

        response = self.client.post(
            self.url,
            {'endpoints': [self.endpoint.pk], 'values': [['SystemUnit', 'Uptime']]},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()[str(self.endpoint.id)]['SystemUnit/Uptime'])


class TestListTestCase(EndpointBaseTest):
    def _get_url(self, arg=''):
        return '/json-api/v1/endpoint/{}'.format(arg)

    def test_list(self):
        response = self.client.get(self._get_url())
        self.assertContains(response, self.endpoint.title, status_code=200)

    def test_filter(self):

        self.endpoint.update_all_data()

        for q in [
            '?firmware={}'.format(self.endpoint.status.software_version[:-1] or '1'),
            '?product_name={}'.format(self.endpoint.product_name or 'cisco'),
            '?only_new=1',
        ]:
            response = self.client.get(self._get_url(q))
            self.assertContains(response, self.endpoint.title, status_code=200)


class TestXAPIViewTestCase(EndpointBaseTest):
    def _get_url(self, args):
        return '/json-api/v1/endpoint/{}'.format(args)

    def test_parse_xapi(self):

        data = {
            'input': '''
            xCommand test test2 test: 1 test2: "test asdf sd" test3: ""
            xConfiguration test 3 f t: 1
            '''
        }
        response = self.client.post(self._get_url('parse_xapi/'), data)
        self.assertEqual(response.status_code, 200)

        commands = response.json()['commands']
        configuration = response.json()['configuration']

        self.assertEqual(len(commands), 1)
        self.assertEqual(len(configuration), 1)

    def test_parse_xapi_multiline(self):
        data = {
            'input': '''
            xcommand HttpFeedback Register FeedbackSlot: 1 ServerUrl:
http://example.org/feedback/code.aspx
Expression: /History/CallLogs/Call Expression: /Status/Call[Status='Connected']
Expression: /Status/H323/Gatekeeper Expression: /Status/SIP/Registration
Expression: /Status/Network/Ethernet/Speed Expression: /Event/CallSuccessful
Expression: /Event/Message/Prompt/Response Expression: /Configuration
Expression: /Event/CallDisconnect Expression: /Status/Call
            '''
        }
        response = self.client.post(self._get_url('parse_xapi/'), data)
        self.assertEqual(response.status_code, 200)

        commands = response.json()['commands']
        configuration = response.json()['configuration']

        self.assertEqual(len(commands), 1)
        self.assertEqual(len(configuration), 0)

        self.assertEqual(commands[0]['arguments']['ServerUrl'], ['http://example.org/feedback/code.aspx'])
        self.assertEqual(list(commands[0]['arguments'].keys()), ['FeedbackSlot', 'ServerUrl', 'Expression'])
        self.assertEqual(len(commands[0]['arguments']['Expression']), 10)

    def test_parse_xapi_multiline2(self):
        data = {
            'input': '''
            xcommand test
            # comment
            xcommand UserInterface Branding Upload Type: Branding
            1234567890
            abcdefabcd
            1234567890
            +//+/+/+==
            .
            xCommand test
            '''
        }
        response = self.client.post(self._get_url('parse_xapi/'), data)
        self.assertNotContains(response, 'error', status_code=200)

        commands = response.json()['commands']
        configuration = response.json()['configuration']

        self.assertEqual(len(commands), 3)
        self.assertEqual(len(configuration), 0)

        self.assertEqual(list(commands[1]['arguments'].keys()), ['Type', 'body'])
        self.assertEqual(len(commands[1]['arguments']['body']), 1)
        self.assertEqual(len(commands[1]['arguments']['body'][0].replace(' ', '')), 10 * 4 + 3)


class CustomerSettingsTestCase(EndpointBaseTest):

    def test_get(self):
        CustomerSettings.objects.update_or_create(
            customer=self.customer,
            defaults={
                'sip_proxy_password': 'PWD',
            },
        )[0]

        response = self.client.get('/json-api/v1/endpointsettings/')
        self.assertNotContains(response, 'PWD', status_code=200)

        response = self.client.get('/json-api/v1/endpointsettings/passwords/')
        self.assertEqual(response.status_code, 403)

    def test_update(self):
        c_settings = CustomerSettings.objects.get_for_customer(self.customer)

        response = self.client.patch('/json-api/v1/endpointsettings/{}/'.format(c_settings.pk), {})
        self.assertEqual(response.status_code, 403)

        self.user.is_staff = True
        self.user.save()

        data = {
            'ip_nets': ['127.0.0.0/24', '172.21.4.0/24'],
            'passwords': ['123', '234'],
            'domains': ['example.org', 'example2.org'],
        }
        response = self.client.patch('/json-api/v1/endpointsettings/{}/'.format(c_settings.pk), data)
        self.assertEqual(response.status_code, 200)

        domains = self.client.get('/json-api/v1/endpointsettings/domains/').json()
        self.assertEqual(domains, [{'domain': d} for d in data['domains']])

        ip_nets = self.client.get('/json-api/v1/endpointsettings/ip_nets/').json()
        self.assertEqual(data['ip_nets'], [net['ip_net'] for net in ip_nets])

        passwords = self.client.get('/json-api/v1/endpointsettings/passwords/').json()
        self.assertEqual(data['passwords'], [p['password'] for p in passwords])

        response = self.client.get('/json-api/v1/endpointsettings/{}/'.format(c_settings.pk))
        self.assertEqual(response.status_code, 200)

