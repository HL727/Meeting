import os.path

from django.utils.encoding import force_text

from conferencecenter.tests.mock_data import state
from conferencecenter.tests.mock_data.response import FakeResponse

MOCK_PATH = os.path.dirname(os.path.abspath(__file__)) + '/../data/'

cisco_ce_requests = {
    'GET configuration.xml': open(MOCK_PATH + 'configuration.xml'),
    'GET command.xml': open(MOCK_PATH + 'command.xml'),
    'GET status.xml': open(MOCK_PATH + 'status.xml'),
    'GET valuespace.xml': open(MOCK_PATH + 'valuespace.xml'),
    'CMD UserManagement/User/List': '<?xml version="1.0"?>\n<Command><UserListResult status="OK">\n  <User item="1" maxOccurrence="n">\n    <Active>True</Active>\n    <Blocked>False</Blocked>\n    <ClientCertificateDN/>\n    <FailedLoginAttempts>0</FailedLoginAttempts>\n    <LastLogin>2019-09-05T08:20:17Z</LastLogin>\n    <PassphraseChangeRequired>False</PassphraseChangeRequired>\n    <PassphraseExpired>False</PassphraseExpired>\n    <PinChangeRequired>False</PinChangeRequired>\n    <PinExpired>False</PinExpired>\n    <Roles item="1" maxOccurrence="n">\n      <Role>User</Role>\n    </Roles>\n    <Roles item="2" maxOccurrence="n">\n      <Role>Admin</Role>\n    </Roles>\n    <Roles item="3" maxOccurrence="n">\n      <Role>Audit</Role>\n    </Roles>\n    <ShellLogin>True</ShellLogin>\n    <Username>admin</Username>\n  </User>\n</UserListResult>\n</Command>\n',
    'CMD UserManagement/User/Passphrase/Set': '<?xml version="1.0"?> <Command><PassphraseSetResult status="OK"/> </Command>',
    'CMD Bookings Put': '<success />',
    'CMD Security/Certificates/CA/Add': '<?xml version="1.0"?> <Command><CAAddResult status="OK"/> </Command>',
    'POST bookingsputxml': '<success />',
    'POST /putxml': '<?xml version="1.0"?><Configuration><Success /></Configuration>',
    'GET status.xml/incoming_call': '''
                <?xml version="1.0"?>
                <Status product="Cisco Codec" version="ce9.6.1.4516ae5aaa1" apiVersion="4">
                  <Call item="80" maxOccurrence="n">
    <AnswerState>Unanswered</AnswerState>
    <CallType>Video</CallType>
    <CallbackNumber>sip:testcall@video.mividas.com</CallbackNumber>
    <DeviceType>MCU</DeviceType>
    <Direction>Incoming</Direction>
    <DisplayName>Test Call Service</DisplayName>
    <Duration>4</Duration>
    <Encryption>
      <Type>AES-256</Type>
    </Encryption>
    <FacilityServiceId>0</FacilityServiceId>
    <HoldReason>None</HoldReason>
    <Ice>Disabled</Ice>
    <PlacedOnHold>False</PlacedOnHold>
    <Protocol>SIP</Protocol>
    <ReceiveCallRate>3072</ReceiveCallRate>
    <RemoteNumber>testcall@video.mividas.com</RemoteNumber>
    <Status>Connected</Status>
    <TransmitCallRate>3072</TransmitCallRate>
  </Call>
  </Status>
  '''.strip(),
    'GET status.xml/in_call': '''
        <?xml version="1.0"?>
        <Status product="Cisco Codec" version="ce9.6.1.4516ae5aaa1" apiVersion="4">
          <Call item="80" maxOccurrence="n">
            <AnswerState>Answered</AnswerState>
            <CallType>Video</CallType>
            <CallbackNumber>sip:testcall@video.mividas.com</CallbackNumber>
            <DeviceType>MCU</DeviceType>
            <Direction>Incoming</Direction>
            <DisplayName>Test Call Service</DisplayName>
            <Duration>4</Duration>
            <Encryption>
              <Type>AES-256</Type>
            </Encryption>
            <FacilityServiceId>0</FacilityServiceId>
            <HoldReason>None</HoldReason>
            <Ice>Disabled</Ice>
            <PlacedOnHold>False</PlacedOnHold>
            <Protocol>SIP</Protocol>
            <ReceiveCallRate>3072</ReceiveCallRate>
            <RemoteNumber>testcall@video.mividas.com</RemoteNumber>
            <Status>Connected</Status>
            <TransmitCallRate>3072</TransmitCallRate>
          </Call>
          </Status>
          '''.strip(),
    'GET status.xml/muted': '''
        <?xml version="1.0"?>
        <Status product="Cisco Codec" version="ce9.6.1.4516ae5aaa1" apiVersion="4">
            <Audio>
                <Microphones>
                  <Mute>On</Mute>
                </Microphones>
            </Audio>
        </Status>
  '''.strip(),
    'GET status.xml/with_warnings': '''
        <?xml version="1.0"?>
        <Status product="Cisco Codec" version="ce9.6.1.4516ae5aaa1" apiVersion="4">
            <Diagnostics>
                <Message item="1" maxOccurrence="n">
                <Description>
                There is one or more users without a passphrase set
                </Description>
                <Level>Critical</Level>
                <References/>
                <Type>ValidPasswords</Type>
                </Message>
                <Message item="9" maxOccurrence="n">
                <Description>
                Provisioning mode is set, but provisioning status is not reporting Provisioned.
                </Description>
                <Level>Warning</Level>
                <References/>
                <Type>ProvisioningModeAndStatus</Type>
                </Message>
                <Message item="10" maxOccurrence="n">
                <Description>Provisioning is in an error state.</Description>
                <Level>Error</Level>
                <References>
                status=Failed&amp;host=192.168.1.216&amp;reason=Couldn't connect to server
                </References>
                <Type>ProvisioningStatus</Type>
                </Message>
                <Message item="11" maxOccurrence="n">
                <Description>
                Enabling SIP ListenPort when registered on SIP may cause higher connection load on the system
                </Description>
                <Level>Warning</Level>
                <References/>
                <Type>SIPListenPortAndRegistration</Type>
                </Message>
            </Diagnostics>
        </Status>
    '''.strip(),
}


def cisco_ce_post(self, url, *args, **kwargs):
    method = kwargs.pop('method', '') or 'POST'

    url = url.replace('/api/v1/', '')

    from provider.exceptions import AuthenticationError, ResponseError
    if 'auth_error' in self.endpoint.hostname:
        raise AuthenticationError('')

    if 'response_error' in self.endpoint.hostname:
        raise ResponseError('')

    if 'invalid_xml' in self.endpoint.hostname:
        return FakeResponse('''<?xml version="1.0"?><Status></Invalid>''')

    if url.startswith('/putxml'):
        data = force_text(args[0] if len(args) else kwargs.get('data', ''))
        if '<Command>' in data:
            method = 'CMD'
            url = data.split(' command="True"')[0].replace('<Command>', '').replace('<', '').replace('>', '/')

    def ret(response, url):

        if isinstance(response, state.State):
            response = response.get(state.url_state) or response.get('initial')

        if hasattr(response, 'read'):
            response.seek(0)
            response = response.read()

        if url == 'status.xml':
            response = fake_status(response, state.url_state)

        if isinstance(response, tuple):
            return FakeResponse(response[1], status_code=response[0], url=url)
        else:
            return FakeResponse(response, url=url)

    for call, response in sorted(iter(list(cisco_ce_requests.items())), key=lambda x: -len(x[0])):

        if call in '%s %s' % (method, url):
            return ret(response, url)

    return FakeResponse('''<?xml version="1.0"?><notfound_test url="{}" />'''.format(url), url=url)


def fake_status(content: bytes, url_state: str = 'default'):

    from defusedxml.cElementTree import fromstring as safe_xml_fromstring
    from xml.etree.cElementTree import tostring, SubElement

    url_state_key = 'GET status.xml/{}'.format(url_state)
    if url_state_key not in cisco_ce_requests:
        return content

    # add extra values
    root = safe_xml_fromstring(content)

    append_root = safe_xml_fromstring(cisco_ce_requests[url_state_key])

    def _rec_add_xml(parent, child):

        container = parent.find('./{}'.format(child.tag))

        if not list(child) and container is not None:
            parent.remove(container)
            container = None

        if container is None:
            parent.append(child)
            return

        for node in list(child):
            _rec_add_xml(container, node)

    for child in list(append_root):
        _rec_add_xml(root, child)

    return tostring(root, encoding='unicode')
