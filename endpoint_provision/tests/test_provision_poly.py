from os import path

from defusedxml.cElementTree import fromstring as safe_xml_fromstring

from endpoint.consts import MANUFACTURER
from endpoint.models import Endpoint, CustomerSettings
from endpoint_provision.tests.test_provision import TestProvisionViews
from endpoint_provision.views_poly_provision import PolyPassiveProvisionBase

root = path.dirname(path.abspath(__file__))


class PolyBaseTest(TestProvisionViews):
    manufacturer = None

    def test_passive(self):

        self.endpoint.connection_type = Endpoint.CONNECTION.PASSIVE
        self.endpoint.save()

        provision = self._run_provision()
        self.assertNotEqual(self.endpoint.password, 'NewPassword')

        xml = PolyPassiveProvisionBase.get_endpoint_instance(self.endpoint).get_response_content()
        root = safe_xml_fromstring(xml)

        self.assertTrue(provision)
        self.assertTrue(root)
        self.assertIn('test.3.subkey.subkey2="1"', xml)
        # TODO check xml content

    def test_all_active(self):

        data = self._get_provision_items()
        self.customer.lifesize_provider = self.pexip  # registration
        self.customer.save()

        # TODO
        unsupported_tasks = {
            'branding',
            'room_controls',
            'room_control_templates',
            'template',
            'clear_room_controls',
            'head_count',
            'presence',
            'room_analytics',
            'branding_profile',
            'firmware',
            'addressbook',  # TODO enable
            'events',  # TODO enable
        }

        ignore = {
            'endpoints',
            'constraint',
            'backup',
        }

        read_only = {
            'statistics',
        }

        for k in data.keys():

            if k in unsupported_tasks or k in ignore:
                continue

            group = {
                'set_password': ['password', 'standard_password'],
                'passive': ['passive_chain'],
            }

            cur = {k: data[k], 'endpoints': data['endpoints'], 'constraint': data['constraint']}

            if k in group:
                cur.update({k: data[k] for k in group[k]})
            elif any(k in g for g in group.values()):
                continue

            self.endpoint.connection_type = Endpoint.CONNECTION.DIRECT
            self.endpoint.save()

            from endpoint_provision.models import EndpointProvision, EndpointTask

            EndpointProvision.objects.all().delete()
            EndpointTask.objects.all().delete()

            post_requests_before = self._get_post_requests()

            with self.subTest('provisioning {}'.format(k)):

                response = self.client.post('/json-api/v1/endpoint/provision/', cur, format='json')
                self.assertEqual(response.status_code, 200)

                provision = EndpointProvision.objects.get(pk=response.json()['id'])

                self.assertTrue(provision)

                self.assertEqual(response.json()['status'], 'OK')

                if k not in read_only:
                    self.assertGreater(
                        len(self._get_change_requests()),
                        len(post_requests_before),
                        'No new post requests sent for {} task'.format(k),
                    )

            self.endpoint.connection_type = Endpoint.CONNECTION.PASSIVE
            self.endpoint.save()

            EndpointProvision.objects.all().delete()
            EndpointTask.objects.all().delete()

            with self.subTest('passive provisioning {}'.format(k)):

                response = self.client.post('/json-api/v1/endpoint/provision/', cur, format='json')
                self.assertEqual(response.status_code, 200)

                provision = EndpointProvision.objects.get(pk=response.json()['id'])
                self.assertTrue(provision)

                print('\n=================Endpoint================\n')
                print(self.endpoint.manufacturer)
                xml = PolyPassiveProvisionBase.get_endpoint_instance(
                    self.endpoint
                ).get_response_content()

                root = safe_xml_fromstring(xml)
                self.assertTrue(root)

                for task in provision.prepare_tasks(self.endpoint):
                    self.assertEqual(
                        task.status,
                        EndpointTask.TASKSTATUS.COMPLETED,
                        'passive task {} not completed: {}'.format(task.action, task.result),
                    )


class TestPolyGroupProvisionViews(PolyBaseTest, TestProvisionViews):
    manufacturer = MANUFACTURER.POLY_GROUP

    def test_api(self):
        super().test_api()

    def test_passive(self):

        super().test_passive()

    def test_all_active(self):
        super().test_all_active()

    def test_api_provision_night_daytime(self):
        super().test_api_provision_night_daytime()

    def test_api_provision_night_nighttime(self):
        super().test_api_provision_night_daytime()

    def test_provision_single_system(self):
        super().test_provision_single_system()

    def test_provision_sip_settings(self):
        super().test_provision_sip_settings()

    def test_provision_repeat(self, endpoint_ids=None):
        super().test_provision_repeat(endpoint_ids=endpoint_ids)

    def test_passive_request(self):
        headers = {
            'HTTP_USER_AGENT': 'Dalvik/1.6.0 (Linux; U; Android 4.0.3; mars Build/IML74K)',
            'HTTP_AUTHORIZATION': 'NTLM TlRMTVNTUAABAAAAFZIIYAgACAAgAAAAAAAAAAAAAABLOFpLNTM5Nw==',
        }
        body = '''
        <?xml version="1.0" encoding="UTF-8"?><ProvisionRequestMessage xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xs:noNamespaceSchemaLocation="PolarisDeviceAPI.xsd">
        <protocolVersion>1.0</protocolVersion>
        <deviceType>GROUPSERIES</deviceType>
            <serialNumber>12345</serialNumber>
            <model>RealPresence Group 500</model>
            <pureVc2Device>TRUE</pureVc2Device>
        </ProvisionRequestMessage>
        '''.strip()
        c_settings = CustomerSettings.objects.get_for_customer(self.customer)
        response = self.client.post(
            '/ep/poly/{}/config-12345.cfg'.format(c_settings.secret_key),
            body,
            **headers,
            content_type='application/xml'
        )
        self.assertEqual(response.status_code, 401)


class TestPolyStudioXProvisionViews(PolyBaseTest, TestProvisionViews):
    manufacturer = MANUFACTURER.POLY_STUDIO_X

    def test_api(self):

        super().test_api()

    def test_all_active(self):
        super().test_all_active()

    def test_passive(self):

        super().test_passive()

    def test_api_provision_night_daytime(self):
        super().test_api_provision_night_daytime()

    def test_api_provision_night_nighttime(self):
        super().test_api_provision_night_daytime()

    def test_provision_single_system(self):
        super().test_provision_single_system()

    def test_provision_sip_settings(self):
        super().test_provision_sip_settings()

    def test_provision_repeat(self, endpoint_ids=None):
        super().test_provision_repeat(endpoint_ids=endpoint_ids)

    def test_passive_request(self):
        headers = {
            "HTTP_USER_AGENT": "FileTransport G_SERIES-PolyStudioX30-UA/3.10.0_362035 Type/Application",
            "HTTP_AUTHORIZATION": "Basic bWl2aWRhczprOHprNTM5",
            "HTTP_X_DEVICE": "12345/112233445566/172.21.16.35",
        }
        body = '''
        '''.strip()
        c_settings = CustomerSettings.objects.get_for_customer(self.customer)
        response = self.client.post(
            '/ep/poly/{}/112233445566.cfg'.format(c_settings.secret_key),
            body,
            **headers,
            content_type='application/xml'
        )
        self.assertEqual(response.status_code, 200)


class TestPolyTrioProvisionViews(PolyBaseTest, TestProvisionViews):
    manufacturer = MANUFACTURER.POLY_TRIO

    def test_api(self):

        super().test_api()

    def test_all_active(self):
        super().test_all_active()

    def test_passive(self):

        super().test_passive()

    def test_api_provision_night_daytime(self):
        super().test_api_provision_night_daytime()

    def test_api_provision_night_nighttime(self):
        super().test_api_provision_night_daytime()

    def test_provision_single_system(self):
        super().test_provision_single_system()

    def test_provision_sip_settings(self):
        super().test_provision_sip_settings()

    def test_provision_repeat(self, endpoint_ids=None):
        super().test_provision_repeat(endpoint_ids=endpoint_ids)

    def test_passive_request(self):
        headers = {
            "HTTP_USER_AGENT": "FileTransport PolycomRealPresenceTrio-Trio_8800-UA/7.2.2.1094 (SN:12345) Type/Application",
        }
        body = '''
        '''.strip()
        c_settings = CustomerSettings.objects.get_for_customer(self.customer)
        response = self.client.post(
            '/ep/poly/{}/12345.cfg'.format(c_settings.secret_key),
            body,
            **headers,
            content_type='application/xml'
        )
        self.assertEqual(response.status_code, 200)


class TestPolyHDXProvisionViews(PolyBaseTest, TestProvisionViews):
    manufacturer = MANUFACTURER.POLY_HDX

    def test_api(self):

        super().test_api()

    def test_all_active(self):
        super().test_all_active()

    def test_passive(self):

        super().test_passive()

    def test_api_provision_night_daytime(self):
        super().test_api_provision_night_daytime()

    def test_api_provision_night_nighttime(self):
        super().test_api_provision_night_daytime()

    def test_provision_single_system(self):
        super().test_provision_single_system()

    def test_provision_sip_settings(self):
        super().test_provision_sip_settings()

    def test_provision_repeat(self, endpoint_ids=None):
        super().test_provision_repeat(endpoint_ids=endpoint_ids)


PolyBaseTest = None  # type: ignore  # noqa
