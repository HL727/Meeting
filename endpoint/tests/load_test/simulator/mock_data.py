import os
from os.path import dirname

identification = '''
<Identification>
<SystemName>System name</SystemName>
<MACAddress>11:22:33:44:55:66</MACAddress>
<IPAddress>192.168.1.123</IPAddress>
<ProductType>Cisco Codec</ProductType>
<ProductID>Cisco Webex Room Kit Mini</ProductID>

<SWVersion>ce9.8.0.be9359915d0</SWVersion>
<SerialNumber>1234567890</SerialNumber>
</Identification>'''

status_base_request = '<Status>%s {}</Status>' % identification
event_base_request = '<Event>%s {}</Event>' % identification

presence_request = status_base_request.format(
    '''
<RoomAnalytics>
<PeoplePresence>Yes</PeoplePresence>
</RoomAnalytics> '''
).strip()

head_count_request = status_base_request.format(
    '''
<RoomAnalytics>
<PeopleCount>
<Current>2</Current>
</PeopleCount>
</RoomAnalytics>
'''
).strip()


call_connect_request = status_base_request.format(
    '''<Call item="24" maxOccurrence="n">
    <Status>Connected</Status>
  </Call>> '''
).strip()

call_disconnect_request = event_base_request.format(
    '''<CallDisconnect>     </CallDisconnect> '''
).strip()

call_successful = event_base_request.format(
    '''
<CallSuccessful item="1">
    <Protocol item="1">Sip</Protocol>
    <Direction item="1">outgoing</Direction>
    <RemoteURI item="1">sip:test@mock.mividas.com</RemoteURI>
    <EncryptionIn item="1">On</EncryptionIn>
    <EncryptionOut item="1">On</EncryptionOut>
    <CallRate item="1">3072</CallRate>
    <CallId item="1">456</CallId>
</CallSuccessful>
'''
)
call_disconnect = event_base_request.format(
    '''
<CallDisconnect item="1">
    <CauseValue item="1">1</CauseValue>
    <CauseType item="1">LocalDisconnect</CauseType>
    <CauseString item="1"></CauseString>
    <OrigCallDirection item="1">outgoing</OrigCallDirection>
    <RemoteURI item="1">sip:test@mock.mividas.com</RemoteURI>
    <DisplayName item="1">Test</DisplayName>
    <CallId item="1">456</CallId>
    <CauseCode item="1">0</CauseCode>
    <CauseOrigin item="1">Internal</CauseOrigin>
    <Protocol item="1">Sip</Protocol>
    <Duration item="1">26</Duration>
    <CallType item="1">Video</CallType>
    <CallRate item="1">3072</CallRate>
    <Encryption item="1">Auto</Encryption>
    <RequestedURI item="1">sip:test@mividas.com</RequestedURI>
    <PeopleCountAverage item="1">-1</PeopleCountAverage>
</CallDisconnect>
'''
)

provision_beat = '''
 <?xml version="1.0" encoding="utf-8"?>
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"
              xmlns="http://www.tandberg.net/2004/11/SystemManagementService/">
  <env:Body xmlns="http://www.tandberg.net/2004/11/SystemManagementService/">
    <PostEvent>
      <Identification>
        <SystemName>System name</SystemName>
        <MACAddress>11:22:33:44:55:66</MACAddress>
        <IPAddress>192.168.1.123</IPAddress>
        <ProductType>TANDBERG Codec</ProductType>
        <ProductID>Cisco Codec</ProductID>
        <SWVersion>ce9.14.3.ecb8718a646</SWVersion>
        <HWBoard></HWBoard>
        <SerialNumber>1234567890</SerialNumber>
      </Identification>
    <Event>Beat</Event>
  </PostEvent></env:Body>
</env:Envelope>
'''.strip()


def load_files():
    status = []
    configuration = []

    root = os.path.join(os.path.abspath(dirname(__file__)), '..', '..', 'data') + '/'

    with open(root + 'status.xml') as fd:
        status.append(fd.read())

    with open(root + 'configuration.xml') as fd:
        configuration.append(fd.read())

    with open(root + 'status_dx80.xml') as fd:
        status.append(fd.read())

    with open(root + 'configuration_dx80.xml') as fd:
        configuration.append(fd.read())

    with open(root + 'status_roomkit.xml') as fd:
        status.append(fd.read())

    with open(root + 'configuration_roomkit.xml') as fd:
        configuration.append(fd.read())

    return status, configuration


status, configuration = load_files()
