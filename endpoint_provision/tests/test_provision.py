from datetime import timedelta
from os import path

from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.timezone import now

from endpoint.consts import MANUFACTURER, PLACEHOLDER_PASSWORD
from endpoint.models import CustomerSettings, Endpoint
from endpoint.tests.base import EndpointBaseTest
from endpoint_provision.models import (
    EndpointProvision,
    EndpointProvisionedObjectHistory,
    EndpointTask,
    EndpointTemplate,
)
from endpoint_provision.views_poly_provision import PolyPassiveProvisionBase
from endpoint_provision.views_tms_provision import get_endpoint_tms_response
from provider.exceptions import AuthenticationError, ResponseError
from roomcontrol.models import RoomControl, RoomControlFile, RoomControlTemplate

root = path.dirname(path.abspath(__file__))


class TestProvisionViewsBase(EndpointBaseTest):
    def setUp(self):
        super().setUp()

        from address.models import AddressBook
        from endpoint_branding.models import EndpointBrandingFile, EndpointBrandingProfile
        from endpoint_provision.models import EndpointFirmware

        self.book_endpoint_meeting(self.endpoint)

        self.address_book = AddressBook.objects.create(title='test', customer=self.customer)
        self.firmware = EndpointFirmware.objects.create(
            version='test',
            model=self.endpoint.product_name,
            customer=self.customer,
            manufacturer=self.endpoint.manufacturer,
            file=ContentFile(b'', 'test.bin'),
        )

        self.branding_profile = EndpointBrandingProfile.objects.create(
            customer=self.customer, name='test'
        )
        self.branding_profile.files.create(
            type=EndpointBrandingFile.BrandingType.Background, file=ContentFile('test', name='test')
        )

        control = RoomControl.objects.create(title='test', customer=self.customer)
        RoomControlFile.objects.create(control=control, name='test.xml', content='<Extensions />')
        RoomControlFile.objects.create(control=control, name='test.js', content='test')

        self.endpoint_template = EndpointTemplate.objects.create(
            customer=self.customer, settings=[{'key': ['Test'], 'value': 'test'}]
        )

        template = RoomControlTemplate.objects.create(title='test', customer=self.customer)
        template.controls.add(control)

        self.control = control
        self.template = template

        self.firmware.customer = self.customer2
        self.firmware.is_global = True
        self.firmware.save()

    def _init_customer_settings(self, **kwargs):

        return CustomerSettings.objects.update_or_create(
            customer=self.customer,
            defaults={
                'ca_certificates': '''-----BEGIN CERTIFICATE-----
MIIFDDCCBLKgAwIBAgIQAwrlgaLVUqsuNytoUoykXzAKBggqhkjOPQQDAjBKMQsw
CQYDVQQGEwJVUzEZMBcGA1UEChMQQ2xvdWRmbGFyZSwgSW5jLjEgMB4GA1UEAxMX
Q2xvdWRmbGFyZSBJbmMgRUNDIENBLTMwHhcNMjEwNjMwMDAwMDAwWhcNMjIwNjI5
MjM1OTU5WjBvMQswCQYDVQQGEwJVUzETMBEGA1UECBMKQ2FsaWZvcm5pYTEWMBQG
A1UEBxMNU2FuIEZyYW5jaXNjbzEZMBcGA1UEChMQQ2xvdWRmbGFyZSwgSW5jLjEY
MBYGA1UEAxMPY3J5cHRvZ3JhcGh5LmlvMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcD
QgAEgRQ70Gzvm9BTASy1LSJaX1+f8oEhHqhnlk8rBlZVv/1o9Ck0YqJ92tsFoHfB
UZadpzGfvJGVd1TadcKFM5ToLqOCA1MwggNPMB8GA1UdIwQYMBaAFKXON+rrsHUO
lGeItEX62SQQh5YfMB0GA1UdDgQWBBQXfMy3TBrmgWsu5zlZhTZCHngwBzAaBgNV
HREEEzARgg9jcnlwdG9ncmFwaHkuaW8wDgYDVR0PAQH/BAQDAgeAMB0GA1UdJQQW
MBQGCCsGAQUFBwMBBggrBgEFBQcDAjB7BgNVHR8EdDByMDegNaAzhjFodHRwOi8v
Y3JsMy5kaWdpY2VydC5jb20vQ2xvdWRmbGFyZUluY0VDQ0NBLTMuY3JsMDegNaAz
hjFodHRwOi8vY3JsNC5kaWdpY2VydC5jb20vQ2xvdWRmbGFyZUluY0VDQ0NBLTMu
Y3JsMD4GA1UdIAQ3MDUwMwYGZ4EMAQICMCkwJwYIKwYBBQUHAgEWG2h0dHA6Ly93
d3cuZGlnaWNlcnQuY29tL0NQUzB2BggrBgEFBQcBAQRqMGgwJAYIKwYBBQUHMAGG
GGh0dHA6Ly9vY3NwLmRpZ2ljZXJ0LmNvbTBABggrBgEFBQcwAoY0aHR0cDovL2Nh
Y2VydHMuZGlnaWNlcnQuY29tL0Nsb3VkZmxhcmVJbmNFQ0NDQS0zLmNydDAMBgNV
HRMBAf8EAjAAMIIBfQYKKwYBBAHWeQIEAgSCAW0EggFpAWcAdwBGpVXrdfqRIDC1
oolp9PN9ESxBdL79SbiFq/L8cP5tRwAAAXpdjETIAAAEAwBIMEYCIQCHwdwC3XOQ
1QRgPQjL79ELT2Qbz+ItZL3NVbLTD6oJ2AIhALr+MC+AXAglONILwOxpTZcI7zgq
BJrfqeeapUpuKCvZAHUAIkVFB1lVJFaWP6Ev8fdthuAjJmOtwEt/XcaDXG7iDwIA
AAF6XYxEtQAABAMARjBEAiAdoY1Qea92qaOIHblj+49F3rlWmXd1DtraNo64HdMn
+AIgdEB8Fkx7rxMuXrx3cHWM4bp863pMQvJHDJlo5T0VN9AAdQBRo7D1/QF5nFZt
uDd4jwykeswbJ8v3nohCmg3+1IsF5QAAAXpdjET+AAAEAwBGMEQCIHayhEvF6M0y
zC3FXt82vdxXwow8m6BgBiroJkA6ElWyAiAmy5aNBDztpqWWSsA93OKSc7naiedR
KWg1zHZRv6iPuzAKBggqhkjOPQQDAgNIADBFAiEAhtfGftRcb4/mxjT/QJ0d6er3
A9mFwQfwiwmmeXfxtVQCIDqDeREHjE1f2HbjeiyYcFka1WcABl0fzlR5AvOt8Pfb
-----END CERTIFICATE-----
'''
                * 2,
                **kwargs,
            },
        )[0]


class TestProvisionViews(TestProvisionViewsBase):
    def _get_provision_items(self, constraint=None, endpoint_ids=None):

        self._init_customer_settings()

        if endpoint_ids is None:
            endpoint_ids = [
                self.endpoint.pk,
                self.endpoint_response_error.pk,
                self.endpoint_auth_error.pk,
            ]

        return {
            'addressbook': self.address_book.pk,
            'branding_profile': self.branding_profile.pk,
            'firmware': self.firmware.pk,
            'commands': [
                {'command': ['Dial', 'Dial'], 'arguments': {'a1': 'test'}, 'body': 'test'}
            ],
            'configuration': [{'key': ['Test'], 'value': 'test'}],
            'template': self.endpoint_template.pk,
            'head_count': True,
            'presence': True,
            'ca_certificates': True,
            'dial_info': {
                'name': 'test',
                'sip': 'sip@example.org',
                'sip_display_name': 'test',
                'sip_proxy': '1.2.3.4',
                'sip_proxy_username': 'user',
                'sip_proxy_password': 'pass',
                'h323': 'h323@example.org',
                'h323_e164': '111222',
                'h323_gatekeeper': '1.2.3.4',
                'register': True,
                'current': True,
            },
            'set_password': True,
            'standard_password': False,
            'passive': True,
            'passive_chain': False,
            'password': 'NewPassword',
            'room_controls': [self.control.pk],
            'room_control_templates': [self.template.pk],
            'clear_room_controls': True,
            'statistics': True,
            'events': True,
            'backup': True,
            'xapi_text': '''xCommand test test2 test: 1 test2: "test asdf sd" test3: ""
            xConfiguration test 3 subkey subkey2: 1''',
            'endpoints': endpoint_ids,
            'constraint': constraint,
        }

    def _run_provision(self, constraint=None, endpoint_ids=None, data=None):
        from endpoint_provision.models import EndpointProvision

        if data is None:
            data = self._get_provision_items(constraint=constraint, endpoint_ids=endpoint_ids)

        self.customer.lifesize_provider = self.pexip  # registration
        self.customer.save()

        data['delay'] = True
        response = self.client.post('/json-api/v1/endpoint/provision/', data, format='json')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        provision = EndpointProvision.objects.get(pk=data['id'])
        provision.prepare_all_tasks()
        self.assert_(provision)

        self.assertEqual(
            provision.data.get_actions(),
            'configuration commands events password address_book firmware passive room_controls statistics template ca_certificates dial_info room_analytics branding'.split(),
        )

        self.assertEqual(data['status'], 'OK')

        return provision

    def test_api(self):

        provision = self._run_provision()

        tasks = EndpointTask.objects.all()
        if self.endpoint.manufacturer == MANUFACTURER.CISCO_CE:
            count = len(provision.data.get_actions()) * 3
        else:
            count = len(provision.data.get_actions()) * 3  # TODO

        self.assertEqual(tasks.count(), count)

        error = ''

        for t in tasks:
            try:
                result = t.run()
            except (ResponseError, AuthenticationError):
                result = None
            except NotImplementedError:
                error += 'Not implemented: {}\n'.format(t.action)
                continue

            if t.endpoint.hostname in ('auth_error', 'response_error'):
                continue  # TODO
            if t.action == 'room_controls' and self.manufacturer != MANUFACTURER.CISCO_CE:
                continue 
            if t.action == 'room_controls_restart':
                continue
            if t.action == 'room_analytics':
                if t.endpoint.personal_system:
                    self.assertEqual(t.status, EndpointTask.TASKSTATUS.FAILED)
                continue  # TODO check supported system
            if t.action == 'branding':
                continue
            self.assertEqual(
                t.status,
                EndpointTask.TASKSTATUS.COMPLETED,
                '{} not completed: {}'.format(t.action, t.status),
            )
            if t.action == 'statistics':
                continue  # TODO mock data
            self.assert_(result)

        if error:
            self.fail(error)

        EndpointTask.objects.all().update(status=0, ts_last_attempt=None)

        from endpoint import tasks

        tasks.queue_pending_endpoint_tasks(self.endpoint.id)

        self.assertEqual(
            EndpointProvisionedObjectHistory.objects.filter(type='ca_certificates').count(), 2 * 2
        )

        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.password, 'NewPassword')

    def test_passive(self):

        self.endpoint.connection_type = Endpoint.CONNECTION.PASSIVE
        self.endpoint.save()

        provision = self._run_provision()
        self.assertNotEqual(self.endpoint.password, 'NewPassword')

        xml = self.get_passive_response(self.endpoint)
        root = safe_xml_fromstring(xml)
        ns = {'s': 'http://www.tandberg.net/2004/11/SystemManagementService/'}

        if settings.EPM_ENABLE_OBTP:
            self.assertEqual(len(self.endpoint.get_api().get_external_calendar_items(root)), 1)
        self.assertEqual(len(self.endpoint.get_api().get_external_configuration(root)), 9)
        self.assertEqual(len(self.endpoint.get_api().get_external_commands(root)), 16)

        self.assertNotEqual(root.find('.//s:Management/s:Command/Command', namespaces=ns), None)
        self.assertNotEqual(
            root.find('.//s:Management/s:Configuration/Configuration', namespaces=ns), None
        )

        self.assertFalse(root.findtext('.//s:Management/s:Command', '', namespaces=ns).strip())
        self.assertFalse(
            root.findtext('.//s:Management/s:Configuration', '', namespaces=ns).strip()
        )
        self.assertEquals(
            root.findtext(
                './/s:Management/s:Software/s:Package/s:URL', 'empty', namespaces=ns
            ).strip(),
            self.firmware.get_absolute_url(),
        )

        self.endpoint.refresh_from_db()
        self.assertNotIn('NewPassword', xml)
        self.assertEqual(self.endpoint.password, 'CurrentPassword')

        response = self.client.get('/json-api/v1/endpointtask/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), (len(provision.data.get_actions())) * 3 + 1)

        task = EndpointTask.objects.filter(endpoint=self.endpoint, action='password').first()
        response = self.client.get('/json-api/v1/endpointtask/{}/'.format(task.id))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<NewPassphrase>', response.json()['provision_content'])

        self.assertEqual(
            EndpointProvisionedObjectHistory.objects.filter(type='ca_certificates').count(), 1 * 2
        )

    def get_passive_response(self, endpoint: Endpoint):
        if self.endpoint.manufacturer == MANUFACTURER.CISCO_CE:
            return get_endpoint_tms_response(self.endpoint)
        else:
            return PolyPassiveProvisionBase.get_endpoint_instance(
                self.endpoint
            ).get_response_content()

    def test_api_provision_night_daytime(self):

        CustomerSettings._override_localtime = CustomerSettings.get_hour(now().replace(hour=14))
        provision = self._run_provision('night')

        tasks = EndpointTask.objects.all()
        for t in tasks:
            result = t.run()
            if t.endpoint.hostname in ('auth_error', 'response_error'):
                continue  # TODO
            self.assertEqual(t.status, EndpointTask.TASKSTATUS.PENDING)
            if t.action == 'statistics':
                continue  # TODO mock data
            self.assertEqual('Error: Trying to run before schedule', result)

        next_night = CustomerSettings._override_localtime.replace(hour=23)

        self.assertEqual(tasks.count(), len(provision.data.get_actions()) * 3)
        self.assertEqual(
            tasks.filter(status=EndpointTask.TASKSTATUS.PENDING).count(),
            len(provision.data.get_actions()) * 3,
        )
        self.assertEqual(tasks.filter(ts_schedule_attempt=next_night).count(), tasks.count())

        EndpointTask.objects.all().update(status=0, ts_last_attempt=None)
        xml = self.get_passive_response(self.endpoint)
        self.assertNotIn('<FeedbackSlot>4</FeedbackSlot>', xml)
        EndpointTask.objects.all().update(status=0, ts_last_attempt=None)

        from endpoint.tasks import queue_pending_endpoint_tasks

        queue_pending_endpoint_tasks(self.endpoint.id)

        self.assertEqual(tasks.filter(ts_schedule_attempt=next_night).count(), tasks.count())
        tasks.update(ts_schedule_attempt=None)

        EndpointProvision.objects.update_constraint_times()

        self.assertEqual(
            tasks.filter(status=EndpointTask.TASKSTATUS.PENDING).count(),
            len(provision.data.get_actions()) * 3,
        )
        self.assertEqual(tasks.filter(ts_schedule_attempt=next_night).count(), tasks.count())

    def test_api_provision_night_nighttime(self):
        CustomerSettings._override_localtime = now().replace(hour=23)
        provision = self._run_provision('night')

        tasks = EndpointTask.objects.all()

        EndpointTask.objects.all().update(status=0, ts_last_attempt=None)

        error = ''

        for t in tasks:
            try:
                result = t.run()
            except (ResponseError, AuthenticationError):
                result = None
            except NotImplementedError:
                error += 'Not implemented: {}\n'.format(t)
                continue

            if t.endpoint.hostname in ('auth_error', 'response_error'):
                continue  # TODO
            if t.action == 'statistics':
                continue  # TODO mock data
            if t.action == 'room_analytics':
                if t.endpoint.personal_system:
                    self.assertEqual(t.status, EndpointTask.TASKSTATUS.FAILED)
                continue  # TODO check supported system
            if t.action != 'room_controls_restart':  # TODO check while running between 00:00-02:00
                self.assertEqual(
                    t.status,
                    EndpointTask.TASKSTATUS.COMPLETED,
                    '{} not completed: {}'.format(t.action, t.status),
                )
            self.assert_(result)

        if error:
            self.fail(error)

        from endpoint.tasks import queue_pending_endpoint_tasks

        queue_pending_endpoint_tasks(self.endpoint.id)

        self.assertEqual(tasks.count(), len(provision.data.get_actions()) * 3)

        Endpoint.objects.all().update(connection_type=Endpoint.CONNECTION.PASSIVE)
        self.endpoint.refresh_from_db()

        EndpointTask.objects.all().update(status=0, ts_last_attempt=None)
        xml = self.get_passive_response(self.endpoint)
        self.assertIn('<FeedbackSlot>4</FeedbackSlot>', xml)

    def test_provision_single_system(self):
        self._run_provision(endpoint_ids=[self.endpoint.pk])

    def test_provision_sip_settings(self):
        c_settings = self._init_customer_settings(
            sip_proxy='sip.proxy',
            sip_proxy_username='username',
            sip_proxy_password='defaultPassword',
        )

        self.endpoint.sip = 'sip@example.org'
        self.endpoint.save()

        self.customer.lifesize_provider = self.pexip  # registration
        self.customer.save()

        def _assert(data):
            response = self.client.post('/json-api/v1/endpoint/provision/', data, format='json')
            self.assertEqual(response.status_code, 200)

            device_request = self._mock_requests.find_data('POST configuration/v1/device/')
            self.assertIn('"password": "defaultPassword"', device_request)

            if self.endpoint.manufacturer == MANUFACTURER.CISCO_CE:
                configuration_request = self._mock_requests.find_data('POST /putxml')
                self.assertIn(
                    b'<Password item="1">defaultPassword</Password>', configuration_request
                )
            else:
                pass  # TODO Poly

            EndpointTask.objects.all().update(
                status=0, ts_last_attempt=None, ts_created=now() - timedelta(hours=1)
            )

            xml = self.get_passive_response(self.endpoint)
            if self.endpoint.manufacturer == MANUFACTURER.CISCO_CE:
                self.assertIn('<Password item="1">defaultPassword</Password>', xml)
            # else:
            #     self.assertIn('defaultPassword', xml)

            EndpointTask.objects.all().delete()

        _assert(
            {
                'endpoints': [self.endpoint.pk],
                'dial_info': {
                    'current': True,
                    'sip_proxy': 'sip.proxy',
                    'sip_proxy_username': 'username',
                    'sip_proxy_password': PLACEHOLDER_PASSWORD,
                    'register': True,
                },
            }
        )
        c_settings.sip_proxy_password = 'other'
        c_settings.save()
        _assert(
            {
                'endpoints': [self.endpoint.pk],
                'dial_info': {
                    'sip': 'sip@example.org',
                    'sip_proxy': 'other.proxy',
                    'sip_proxy_username': 'other',
                    'sip_proxy_password': 'defaultPassword',
                    'register': True,
                },
            }
        )

    def test_provision_repeat(self, endpoint_ids=None):

        from endpoint_provision.models import EndpointProvision

        self._init_customer_settings()

        if endpoint_ids is None:
            endpoint_ids = [
                self.endpoint.pk,
                self.endpoint_response_error.pk,
                self.endpoint_auth_error.pk,
            ]

        data = {
            'configuration': [{'key': ['Test'], 'value': 'test'}],
            'endpoints': endpoint_ids,
            'repeat': True,
            'constraint': 'night',
        }
        response = self.client.post('/json-api/v1/endpoint/provision/', data, format='json')
        self.assertEqual(response.status_code, 200)

        provision = EndpointProvision.objects.first()

        tasks = EndpointTask.objects.all()
        self.assertEqual(tasks.count(), len(provision.data.get_actions()) * len(endpoint_ids))

        for t in tasks:
            try:
                t.run()
            except (ResponseError, AuthenticationError):
                pass

        self.assertFalse(tasks.exclude(status__lte=EndpointTask.TASKSTATUS.QUEUED))


TestProvisionViewsBase = None  # type: ignore  # noqa
