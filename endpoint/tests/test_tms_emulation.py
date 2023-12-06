from os import path

import requests_mock
from django.contrib.auth.models import User
from django.test.utils import override_settings
from django.utils.timezone import now
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from endpoint.models import CustomerSettings, Endpoint

from .. import consts

root = path.dirname(path.abspath(__file__))
from defusedxml.cElementTree import fromstring as safe_xml_fromstring

posted_base_request = '''
<PostedDocument>\n   <Identification>    <SystemName>Test</SystemName>    <MACAddress>11:22:33:44:55:66</MACAddress>    <IPAddress>192.168.2.2</IPAddress>    <ProductType>Cisco Codec</ProductType>    <ProductID>Cisco Webex Room Kit Mini</ProductID>    <SWVersion>ce9.8.0.be9359915d0</SWVersion>    <SerialNumber>1234</SerialNumber>  </Identification> {} </PostedDocument>'''

configuration_request = posted_base_request.format('<Location>/Configuration</Location><Configuration product="Cisco Codec" version="ce9.8.0.be9359915d0"> <Audio>\n    <DefaultVolume valueSpaceRef="/Valuespace/INT_0_100">80</DefaultVolume></Audio></Configuration>')

status_request = posted_base_request.format('<Location>/Status</Location><Status product="Cisco Codec" version="ce9.8.0.be9359915d0">\n  <Audio></Audio> </Status>')


event_request = '''
<?xml version="1.0" encoding="utf-8"?>
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"
          xmlns="http://www.tandberg.net/2004/11/SystemManagementService/">
<env:Body xmlns="http://www.tandberg.net/2004/11/SystemManagementService/">
<PostEvent>
  <Identification>
    <SystemName></SystemName>
    <MACAddress>{mac_adress}</MACAddress>
    <IPAddress>{ip}</IPAddress>
    <ProductType>TANDBERG Codec</ProductType>
    <ProductID>Cisco Codec</ProductID>
    <SWVersion>ce9.6.1.4516ae5aaa1</SWVersion>
    <HWBoard></HWBoard>
    <SerialNumber>{serial}</SerialNumber>
  </Identification>
<Event>{event}</Event>
</PostEvent></env:Body>
</env:Envelope>
   '''.strip()


class TestTMSProvision(APITestCase, ConferenceBaseTest):

    def setUp(self):
        super().setUp()
        self._init()
        self.endpoint = Endpoint.objects.create(customer=self.customer, ip='192.168.1.117', username='admin',
                manufacturer=consts.MANUFACTURER.CISCO_CE, mac_address='11:22:33:44:55:66')
        self.user = User.objects.create_user(username='test', password='test')
        self.client.login(username=self.user.username, password='test')

    @property
    def auth_url(self):
        return '/tms/{}/'.format(
            CustomerSettings.objects.get_for_customer(self.customer).secret_key
        )

    def test_status(self):

        self.assertEqual(self.endpoint.status.ts_last_provision_document, None)
        self.assertTrue(self.endpoint.should_update_provision_document)
        response = self.client.post(
            self.endpoint.get_document_path(), status_request, content_type='text/xml'
        )
        self.assertContains(response, text='<OK />', status_code=200)

        self.endpoint.status.refresh_from_db()
        self.assertNotEquals(self.endpoint.status.ts_last_provision_document, None)
        self.assertFalse(self.endpoint.should_update_provision_document)

        with override_settings(EPM_EVENT_CUSTOMER_SECRET=False):
            response = self.client.post(
                '/tms/event/document/', status_request, content_type='text/xml'
            )
            self.assertContains(response, text='OK', status_code=200)

        with override_settings(EPM_EVENT_CUSTOMER_SECRET=True):
            response = self.client.post(
                '/tms/event/document/', status_request, content_type='text/xml'
            )
            self.assertContains(response, text='', status_code=403)

    def test_configuration(self):

        response = self.client.post(
            self.endpoint.get_document_path(), configuration_request, content_type='text/xml'
        )
        self.assertContains(response, text='<OK />', status_code=200)

    def test_ip_address(self):
        self.endpoint.track_ip_changes = True
        self.endpoint.save()

        self.assertEqual(self.endpoint.ip, '192.168.1.117')

        response = self.client.post(
            self.endpoint.get_document_path(), configuration_request, content_type='text/xml'
        )
        self.assertContains(response, text='<OK />', status_code=200)

        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.ip, '192.168.2.2')

    def test_document_status(self):
        xml = event_request.format(
            event='Beat',
            mac_adress=self.endpoint.mac_address,
            serial=self.endpoint.serial_number,
            ip=self.endpoint.ip,
        )
        response = self.client.post(
            self.endpoint.get_provision_path(), xml, content_type='text/xml'
        )
        self.assertContains(response, text='<DocumentToPost><Location>', status_code=200)

        self.endpoint.set_status(ts_last_provision_document=now())

        response = self.client.post(
            self.endpoint.get_provision_path(), xml, content_type='text/xml'
        )
        self.assertNotContains(response, text='<DocumentToPost><Location>', status_code=200)

    def test_register(self):

        xml = event_request.format(
            event='Register',
            mac_adress='11:11:11:11:11:11',
            serial='000000',
            ip='192.168.1.2',
        )

        self.assertEqual(Endpoint.objects.all().count(), 1)

        with override_settings(EPM_EVENT_CUSTOMER_SECRET=False):
            # non auth
            response = self.client.post('/tms/', xml, content_type='text/xml')
            self.assertContains(response, text='PostEventResponse', status_code=200)
            self.assertEqual(Endpoint.objects.all().count(), 1)

        with override_settings(EPM_EVENT_CUSTOMER_SECRET=True):
            response = self.client.post('/tms/', xml, content_type='text/xml')
            self.assertContains(response, text='', status_code=403)
            self.assertEqual(Endpoint.objects.all().count(), 1)

        # auth
        response = self.client.post(self.auth_url, xml, content_type='text/xml')
        self.assertContains(response, text='PostEventResponse', status_code=200)
        self.assertEqual(Endpoint.objects.all().count(), 2)

    @override_settings(EPM_ENABLE_OBTP=True)
    def _test_booking(self):
        meeting = self._book_meeting(title='Nytt test')
        meeting.endpoints.add(self.endpoint)

        xml = event_request.format(
            event='Beat',
            mac_adress=self.endpoint.mac_address,
            serial=self.endpoint.serial_number,
            ip=self.endpoint.ip,
        )
        response = self.client.post(
            self.endpoint.get_provision_path(), xml, content_type='text/xml'
        )
        safe_xml_fromstring(response.content)
        self.assertContains(response, text='Nytt test', status_code=200)

    def test_chained_request(self):

        with requests_mock.Mocker() as m:
            m.post(
                'https://mocked/tms/',
                text='''
                <?xml version="1.0" encoding="UTF-8"?>
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"
              xmlns:xsd="http://www.w3.org/2001/XMLSchema"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <env:Body>
    <PostEventResponse xmlns="http://www.tandberg.net/2004/11/SystemManagementService/">
      <PostEventResult>
        <HeartBeatInterval>900</HeartBeatInterval>
        <Management>
          <Configuration>
            <Configuration xmlns="http://www.tandberg.com/XML/CUIL/2.0">
<Provisioning>
  <ExternalManager>
    <Address>prov.example.org</Address>
    <Path>/prov/cisco/ce/777777777-5e2e-43d8-8ca1-345345345/aedf54wsreg4wse5grstgrtg45</Path>
    <Protocol>HTTPS</Protocol>
  </ExternalManager>
  <HttpMethod>POST</HttpMethod>
  <Mode>TMS</Mode>
</Provisioning>
<Phonebook>
  <Server>
    <ID>default</ID>
    <Type>TMS</Type>
    <URL>https://api.moon.vp.vc/api/phonebook/v1/cisco/tms/tags/00000000-5e2e-43d8-8ca1-000000000000/en_US</URL>
  </Server>
</Phonebook>
<Conference>
  <MaxTransmitCallRate>3072</MaxTransmitCallRate>
  <MaxReceiveCallRate>3072</MaxReceiveCallRate>
  <MultiStream>
    <Mode>Off</Mode>
  </MultiStream>
  <DefaultCall>
    <Protocol>Sip</Protocol>
    <Rate>3072</Rate>
  </DefaultCall>
</Conference>
<SIP>
  <URI>test@example.org</URI>
  <DisplayName>Test test</DisplayName>
  <DefaultTransport>TLS</DefaultTransport>
  <Type>Standard</Type>
  <Authentication>
    <UserName>Testar/T7ywU=</UserName>
    <Password>sdafASDF</Password>
  </Authentication>
  <Proxy item="1">
    <Address>test.proxy</Address>
  </Proxy>
  <Proxy item="2">
    <Address />
  </Proxy>
  <Proxy item="3">
    <Address />
  </Proxy>
  <Proxy item="4">
    <Address />
  </Proxy>
  <Ice>
    <Mode>Off</Mode>
  </Ice>
  <Turn>
    <Server />
    <UserName />
    <Password />
  </Turn>
</SIP>
<NetworkServices>
  <SIP>
    <Mode>On</Mode>
  </SIP>
  <NTP>
    <Mode>Manual</Mode>
    <Server item="1">
      <Address>time.example.org</Address>
    </Server>
    <Server item="2">
      <Address item="2"></Address>
    </Server>
    <Server item="3">
      <Address item="3"></Address>
    </Server>
  </NTP>
</NetworkServices>
<SystemUnit>
  <Name>Test</Name>
</SystemUnit>

            </Configuration>
          </Configuration>
        </Management>
      </PostEventResult>
    </PostEventResponse>
  </env:Body>
</env:Envelope>
                '''.strip(),
            )
            self.endpoint.external_manager_service = 'https://mocked/tms/'
            self.endpoint.save()

            xml = event_request.format(
                event='Beat',
                mac_adress=self.endpoint.mac_address,
                serial=self.endpoint.serial_number,
                ip=self.endpoint.ip,
            )
            response = self.client.post(
                self.endpoint.get_provision_path(), xml, content_type='text/xml'
            )
            safe_xml_fromstring(response.content)
            self.assertContains(response, text='PostEventResponse', status_code=200)

            self.assertIn('time.example.org', response.content.decode('utf-8'))
            self.assertIn('test.proxy', response.content.decode('utf-8'))
            self.assertNotIn('prov.example.org', response.content.decode('utf-8'))

    def test_provision_chained(self):

        data = {
            'endpoints': [self.endpoint.pk],
            'passive': True,
            'passive_chain': True,
        }
        response = self.client.post('/json-api/v1/endpoint/provision/', data, format='json')
        self.assertEqual(response.status_code, 200)

        self.endpoint.refresh_from_db()

        self.assertEqual(
            self.endpoint.external_manager_service, 'https://ext.prov.example.org/tms/provision/'
        )
