from os import path

from django.contrib.auth.models import User
from django.test.utils import override_settings
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from endpoint.models import Endpoint
from provider.models.provider import Provider
from room_analytics.models import EndpointHeadCount, EndpointRoomPresence

from .. import consts

root = path.dirname(path.abspath(__file__))


identification = '''
<Identification>    <SystemName>Test</SystemName>    <MACAddress>11:22:33:44:55:66</MACAddress>    <IPAddress>192.168.2.2</IPAddress>    <ProductType>Cisco Codec</ProductType>    <ProductID>Cisco Webex Room Kit Mini</ProductID>    <SWVersion>ce9.8.0.be9359915d0</SWVersion>    <SerialNumber>1234</SerialNumber>  </Identification>'''

status_base_request = '<Status>%s {}</Status>' % identification
event_base_request = '<Event>%s {}</Event>' % identification

presence_request = status_base_request.format('''<RoomAnalytics>    <PeoplePresence>Yes</PeoplePresence>  </RoomAnalytics> ''').strip()

head_count_request = status_base_request.format('''
 <RoomAnalytics>    <PeopleCount>      <Current>2</Current>    </PeopleCount>  </RoomAnalytics>
''').strip()


call_connect_request = status_base_request.format(
    '''<Call item="24" maxOccurrence="n">
    <Status>Connected</Status>
  </Call>> '''
).strip()

call_disconnect_request = event_base_request.format(
    '''<CallDisconnect>     </CallDisconnect> '''
).strip()

call_successful = event_base_request.format('''
<CallSuccessful item="1">
    <Protocol item="1">Sip</Protocol>
    <Direction item="1">outgoing</Direction>
    <RemoteURI item="1">sip:test@mividas.com</RemoteURI>
    <EncryptionIn item="1">On</EncryptionIn>
    <EncryptionOut item="1">On</EncryptionOut>
    <CallRate item="1">3072</CallRate>
    <CallId item="1">456</CallId>
</CallSuccessful>
''')
call_disconnect = event_base_request.format('''
<CallDisconnect item="1">
    <CauseValue item="1">1</CauseValue>
    <CauseType item="1">LocalDisconnect</CauseType>
    <CauseString item="1"></CauseString>
    <OrigCallDirection item="1">outgoing</OrigCallDirection>
    <RemoteURI item="1">sip:test@mividas.com</RemoteURI>
    <DisplayName item="1">Test</DisplayName>
    <CallId item="1">456</CallId>
    <CauseCode item="1">0</CauseCode>
    <CauseOrigin item="1">Internal</CauseOrigin>
    <Protocol item="1">Sip</Protocol>
    <Duration item="1">526</Duration>
    <CallType item="1">Video</CallType>
    <CallRate item="1">3072</CallRate>
    <Encryption item="1">Auto</Encryption>
    <RequestedURI item="1">sip:test@mividas.com</RequestedURI>
    <PeopleCountAverage item="1">-1</PeopleCountAverage>
</CallDisconnect>
''')


class CiscoHttpEventBase(APITestCase, ConferenceBaseTest):

    def setUp(self):
        super().setUp()
        self._init()
        self.endpoint = Endpoint.objects.create(
            customer=self.customer,
            ip='192.168.1.117',
            username='admin',
            manufacturer=consts.MANUFACTURER.CISCO_CE,
            mac_address='11:22:33:44:55:66',
        )
        self.user = User.objects.create_user(username='test', password='test')
        self.client.login(username=self.user.username, password='test')

    @property
    def url(self):
        return self.endpoint.get_feedback_url()


class TestTMSEvents(CiscoHttpEventBase):

    def test_presence_request(self):

        response = self.client.post(self.url, presence_request, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(EndpointRoomPresence.objects.filter(endpoint=self.endpoint).count(), 1)

    def test_head_count_request(self):
        response = self.client.post(self.url, head_count_request, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            list(
                EndpointHeadCount.objects.filter(endpoint=self.endpoint).values_list(
                    'value', flat=True
                )
            ),
            [2],
        )

    def test_secret_key(self):

        with override_settings(EPM_EVENT_CUSTOMER_SECRET=False):
            response = self.client.post(
                '/tms/event/', call_connect_request, content_type='text/xml'
            )
            self.assertEqual(response.status_code, 200)

        with override_settings(EPM_EVENT_CUSTOMER_SECRET=True):
            response = self.client.post(
                '/tms/event/', call_connect_request, content_type='text/xml'
            )
            self.assertEqual(response.status_code, 403)

    def test_call_request(self):
        response = self.client.post(self.url, call_connect_request, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status.status, consts.STATUS.IN_CALL)

        response = self.client.post(self.url, call_disconnect_request, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status.status, consts.STATUS.ONLINE)

    def test_ip_change(self):
        self.endpoint.track_ip_changes = True
        self.endpoint.save()

        self.assertEqual(self.endpoint.ip, '192.168.1.117')

        response = self.client.post(self.url, call_disconnect_request, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.ip, '192.168.2.2')

    def test_call_request_without_mcu(self):
        self.customer.lifesize_provider = None
        self.customer.save()
        Provider.objects.all().update(is_standard=False)
        response = self.client.post(self.url, call_disconnect_request, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

    def test_call_parse(self):
        from statistics.models import Leg

        self.assertEqual(Leg.objects.filter(endpoint=self.endpoint).count(), 0)

        response = self.client.post(self.url, call_successful, content_type='text/xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Leg.objects.filter(endpoint=self.endpoint, ts_stop__isnull=True).count(), 1)
        self.assertEqual(Leg.objects.filter(endpoint=self.endpoint, ts_stop__isnull=False).count(), 0)

        response = self.client.post(self.url, call_disconnect, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Leg.objects.filter(endpoint=self.endpoint, ts_stop__isnull=True).count(), 0)
        self.assertEqual(Leg.objects.filter(endpoint=self.endpoint, ts_stop__isnull=False).count(), 1)
        self.assertTrue(Leg.objects.filter(endpoint=self.endpoint).get().should_count_stats)


class TestCallStatusTestCase(CiscoHttpEventBase):
    def assert_endpoint_call_after_status(self, status: consts.STATUS, status_content: str):
        response = self.client.post(
            self.url, status_base_request.format(status_content), content_type='text/xml'
        )
        self.assertEqual(response.status_code, 200)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status.status, status)

    def assert_endpoint_call_after_event(self, status: consts.STATUS, event_content: str):
        response = self.client.post(
            self.url, event_base_request.format(event_content), content_type='text/xml'
        )
        self.assertEqual(response.status_code, 200)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.status.status, status)

    def test_call_disconnect_chain(self):

        self.assert_endpoint_call_after_status(
            consts.STATUS.ONLINE,
            '''<Call item="8" maxOccurrence="n">
                <Status>Dialling</Status>
            </Call>''',
        )

        self.assert_endpoint_call_after_event(
            consts.STATUS.ONLINE,
            '''<OutgoingCallIndication item="1">
                 <CallId item="1">8</CallId>
               </OutgoingCallIndication>''',
        )

        self.assert_endpoint_call_after_status(
            consts.STATUS.ONLINE,
            '''<Call item="8" maxOccurrence="n">
                <Status>Connecting</Status>
               </Call>''',
        )

        self.assert_endpoint_call_after_status(
            consts.STATUS.ONLINE, '''<Call ghost="True" item="8" maxOccurrence="n"/>'''
        )

        self.assert_endpoint_call_after_event(
            consts.STATUS.ONLINE,
            '''<CallDisconnect item="1">
                <CauseValue item="1">13</CauseValue>
                <CauseType item="1">RemoteBusy</CauseType>
                <CauseString item="1">Call rejected</CauseString>
                <OrigCallDirection item="1">outgoing</OrigCallDirection>
                <RemoteURI item="1">spark:44444444-3333-3ce3-a2e6-740d94dc7a96</RemoteURI>
                <DisplayName item="1">Testar</DisplayName>
                <CallId item="1">8</CallId>
                <CauseCode item="1">0</CauseCode>
                <CauseOrigin item="1">Spark</CauseOrigin>
                <Protocol item="1">Spark</Protocol>
                <Duration item="1">0</Duration>
                <CallType item="1">Video</CallType>
                <CallRate item="1">6000</CallRate>
                <Encryption item="1">Auto</Encryption>
                <RequestedURI item="1">77777777-3333-4eef-83c1-63f53a8164dd</RequestedURI>
                <PeopleCountAverage item="1">-1</PeopleCountAverage>
              </CallDisconnect>''',
        )

    def test_call_successfull_chain(self):
        self.assert_endpoint_call_after_status(
            consts.STATUS.ONLINE,
            '''<Call item="2" maxOccurrence="n">
                <Status>Dialling</Status>
              </Call>''',
        )
        self.assert_endpoint_call_after_event(
            consts.STATUS.ONLINE,
            '''<OutgoingCallIndication item="1">
    <CallId item="1">2</CallId>
  </OutgoingCallIndication>''',
        )
        self.assert_endpoint_call_after_status(
            consts.STATUS.ONLINE,
            '''<Call item="2" maxOccurrence="n">
    <Status>Connecting</Status>
  </Call>''',
        )
        self.assert_endpoint_call_after_status(
            consts.STATUS.IN_CALL,
            '''<Call item="2" maxOccurrence="n">
    <Status>Connected</Status>
  </Call>''',
        )

        self.assert_endpoint_call_after_event(
            consts.STATUS.IN_CALL,
            '''<CallSuccessful item="1">
                <Protocol item="1">Spark</Protocol>
                <Direction item="1">outgoing</Direction>
                <RemoteURI item="1">spark:99999999-4444-3b8d-a8ee-ef7920be96a3</RemoteURI>
                <EncryptionIn item="1">On</EncryptionIn>
                <EncryptionOut item="1">On</EncryptionOut>
                <CallRate item="1">6000</CallRate>
                <CallId item="1">2</CallId>
              </CallSuccessful>''',
        )

        self.assert_endpoint_call_after_status(
            consts.STATUS.ONLINE,
            '''<Call item="7" maxOccurrence="n">
                <Status>Disconnecting</Status>
              </Call>''',
        )
        self.assert_endpoint_call_after_status(
            consts.STATUS.ONLINE,
            '''<Call item="7" maxOccurrence="n">
                <Status>Idle</Status>
              </Call>''',
        )

        self.assert_endpoint_call_after_event(
            consts.STATUS.ONLINE,
            '''<CallDisconnect item="1">
            <CauseValue item="1">1</CauseValue>
            <CauseType item="1">LocalDisconnect</CauseType>
            <CauseString item="1"></CauseString>
            <OrigCallDirection item="1">outgoing</OrigCallDirection>
            <RemoteURI item="1">spark:99999999-4444-3b8d-a8ee-ef7920be96a3</RemoteURI>
            <DisplayName item="1">Test call</DisplayName>
            <CallId item="1">7</CallId>
            <CauseCode item="1">0</CauseCode>
            <CauseOrigin item="1">Internal</CauseOrigin>
            <Protocol item="1">Spark</Protocol>
            <Duration item="1">3686</Duration>
            <CallType item="1">Video</CallType>
            <CallRate item="1">6000</CallRate>
            <Encryption item="1">Auto</Encryption>
            <RequestedURI item="1">test.test@testsson.se</RequestedURI>
            <PeopleCountAverage item="1">1</PeopleCountAverage>
          </CallDisconnect>''',
        )
