from .response import FakeResponse
from .state import State
import re

distinct_ids = {
    'cospace_with_user': 'fffffff-1948-47ec-ad4f-4793458cfe0c',
    'cospace_without_user': '22f67f91-1948-47ec-ad4f-4793458cfe0c',
    'uri': '61170',

    'leg': '976dacd8-bc6b-4526-8bb7-d9050740b7c7',
    'call': '935a38b8-0a80-4965-9db4-f02ab1a813d2',
    'cospace_with_call': '22f67f91-1948-47ec-ad4f-4793458cfe0c',
}

acano_requests = {
    'GET coSpaces': r'''
        <?xml version="1.0"?><coSpaces total="1">
        <coSpace id="22f67f91-1948-47ec-ad4f-4793458cfe0c">
        <name>fbn</name><uri>61170</uri>
        <callId>61170</callId>
        <autoGenerated>false</autoGenerated>
        <uri>61170</uri>
        <nonMemberAccess>true</nonMemberAccess>
        <ownerId>userguid111</ownerId>
        <ownerJid>username@example.org</ownerJid>
        <secret>BBBBBBBBBBBBBBBBBBBBBB</secret>
        </coSpace></coSpaces>''',

    'GET coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c': r'''
        <?xml version="1.0"?><coSpace id="22f67f91-1948-47ec-ad4f-4793458cfe0c"><name>fbn</name><autoGenerated>false</autoGenerated><uri>61170</uri><callId>61170</callId>
        <numAccessMethods>1</numAccessMethods>
        <secret>BBBBBBBBBBBBBBBBBBBBBB</secret>
        </coSpace>
    ''',

    'GET coSpaces/fffffff-1948-47ec-ad4f-4793458cfe0c': r'''
        <?xml version="1.0"?><coSpace id="fffffff-1948-47ec-ad4f-4793458cfe0c"><name>fbn</name><autoGenerated>true</autoGenerated><uri>61170</uri><callId>61170</callId>
        <ownerId>userguid111</ownerId>
        <ownerJid>username@example.org</ownerJid>
        </coSpace>
    ''',

    'GET coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/coSpaceUsers': r'''
        <?xml version="1.0"?><coSpaceUsers total="1">
        <member id="1234"><userJid id="userguid111">username@example.org</userJid></member>
        </coSpaceUsers>
    ''',

    'POST coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/coSpaceUsers': {'Location': '/api/v1/coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/coSpaceUsers/1234'},



    'PUT coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c': {'Location': '/api/v1/coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c'},
    'PUT coSpaces/fffffff-1948-47ec-ad4f-4793458cfe0c': {'Location': '/api/v1/coSpaces/fffffff-1948-47ec-ad4f-4793458cfe0c'},

    'GET coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/accessMethods': '''<?xml version="1.0"?><accessMethods total="1">
    <accessMethod id="aasit-ash-ashtna-123">
      <uri>am123</uri>
      <callId>630362516</callId>
      <passcode>87654321</passcode>
      <name>Moderator</name>
    </accessMethod></accessMethods>''',
    'PUT coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/accessMethods': {'Location': '/api/v1/coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c'},
    'POST coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/accessMethods': {'Location': '/api/v1/coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/accessMethods/aasit-ash-ashtna-123'},
    'GET coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/accessMethods/aasit-ash-ashtna-123': '''
        <?xml version="1.0"?>
        <accessMethod id="aasit-ash-ashtna-123">
          <uri>am123</uri><secret>abc123</secret>
          <callLegProfile>856dc4f9-b011-49bb-b3ef-4e954c72bea8</callLegProfile>
          <secret>abc123</secret>
          <scope>private</scope>
        </accessMethod>
    ''',

    'POST coSpaces': State({
        'initial': {'Location': '/api/v1/coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c'},
        'owner-cospace': {'Location': '/api/v1/coSpaces/fffffff-1948-47ec-ad4f-4793458cfe0c'},
        'uri-in-use': '<failureDetails><duplicateCoSpaceUri /></failureDetails>',
        'call-id-in-use': '<failureDetails><duplicateCoSpaceId /></failureDetails>',
        'owner-not-found': '<failureDetails><userDoesNotExist /></failureDetails>',
    }),
    'POST calls': {'Location': '/api/v1/calls/935a38b8-0a80-4965-9db4-f02ab1a813d2'},
    'POST calls/935a38b8-0a80-4965-9db4-f02ab1a813d2/callLegs':{'Location': '/api/v1/callLegs/976dacd8-bc6b-4526-8bb7-d9050740b7c7'},

    'GET callProfiles/': '''
            <?xml version="1.0"?>
        <callProfiles total="1">
            <callProfile id="call-1948-47ec-ad4f-4793458cfe0c">
            </callProfile>
        </callProfiles>
    ''',
    'POST callProfiles': {'Location': '/api/v1/callProfiles/call-1948-47ec-ad4f-4793458cfe0c'},
    'DELETE callProfiles/call-1948-47ec-ad4f-4793458cfe0c': '',

    'POST callLegProfiles': {'Location': '/api/v1/callLegProfiles/callLeg-1948-47ec-ad4f-4793458cfe0c'},
    'GET callLegProfiles': '''
        <?xml version="1.0"?>
        <callLegProfiles total="1">
            <callLegProfile id="callLeg-1948-47ec-ad4f-4793458cfe0c">
            </callLegProfile>
        </callLegProfiles>
    ''',
    'DELETE callLegProfiles/callLeg-1948-47ec-ad4f-4793458cfe0c': '',

    'POST callBrandingProfiles': {'Location': '/api/v1/callBrandingProfiles/callBranding-1948-47ec-ad4f-4793458cfe0c'},
    'PUT callBrandingProfiles/callBranding-1948-47ec-ad4f-4793458cfe0c': {'Location': '/api/v1/callBrandingProfiles/callBranding-1948-47ec-ad4f-4793458cfe0c'},
    'GET callBrandingProfiles/callBranding-1948-47ec-ad4f-4793458cfe0c': '''
            <?xml version="1.0"?>
            <callBrandingProfile id="callBranding-1948-47ec-ad4f-4793458cfe0c">
            </callBrandingProfile>
    ''',
    'GET callBrandingProfiles': '''
        <?xml version="1.0"?>
        <callBrandingProfiles total="1">
            <callBrandingProfile id="callBranding-1948-47ec-ad4f-4793458cfe0c">
            </callBrandingProfile>
        </callBrandingProfiles>
    ''',
    'DELETE callBrandingProfiles/callBranding-1948-47ec-ad4f-4793458cfe0c': '',

    'POST ivrBrandingProfiles':{'Location': '/api/v1/ivrBrandingProfiles/ivrBranding-1948-47ec-ad4f-4793458cfe0c'},
    'GET ivrBrandingProfiles': '''
        <?xml version="1.0"?>
        <ivrBrandingProfiles total="1">
            <ivrBrandingProfile id="ivrBranding-1948-47ec-ad4f-4793458cfe0c">
            </ivrBrandingProfile>
        </ivrBrandingProfiles>
    ''',
    'DELETE ivrBrandingProfiles/ivrBranding-1948-47ec-ad4f-4793458cfe0c': '',

    'POST ldapSyncs':{'Location': '/api/v1/ldapSyncs/ldap-1948-47ec-ad4f-4793458cfe0c'},
    'GET ldapServers': '''<?xml version="1.0" ?>
<ldapServers total="1">
  <ldapServer id="010c4c7d-ce57-4d04-b5db-edca20412534">
    <address>ldap.seevia.me</address>
    <name/>
    <username/>
    <portNumber>389</portNumber>
    <secure>false</secure>
  </ldapServer></ldapServers>''',
    'GET ldapSources': '''<?xml version="1.0" ?>
<ldapSources total="1">
  <ldapSource id="0d5c2403-576a-4733-8c3e-eee680188123">
    <server>49a83b75-9252-42e7-b307-d72960c5c152</server>
    <mapping>cf89d355-c4dd-47c3-af4a-afe08fa009f4</mapping>
    <tenant>fb51554b-d67c-4955-824f-a4c2e177ac1f</tenant>
    <baseDn>dc=example,dc=local</baseDn>
    <filter>(&amp;(objectCategory=person)(objectClass=user)(!(cn=admin))(!(cn=acano))(!(cn=Guest))(!(cn=krbtgt))(!(cn=Gäst))(|(ou=sembly)))</filter>
    <nonMemberAccess>true</nonMemberAccess>
  </ldapSource></ldapSources>''',
    'GET ldapMappings': '''<?xml version="1.0" ?>
<ldapMappings total="1">
  <ldapMapping id="cf89d355-c4dd-47c3-af4a-afe08fa009f3">
    <jidMapping>$sAMAccountName$@example.org</jidMapping>
    <nameMapping>$displayName$</nameMapping>
  </ldapMapping>
</ldapMappings>''',
    'GET calls': '''
    <calls total="1"><call id="935a38b8-0a80-4965-9db4-f02ab1a813d2"><name>test</name><coSpace>22f67f91-1948-47ec-ad4f-4793458cfe0c</coSpace><callCorrelator>ff94a293-32e2-45fb-b497-6eb7b04cc315</callCorrelator></call></calls>
    '''.strip(),

    'GET calls/935a38b8-0a80-4965-9db4-f02ab1a813d2': '''
        <?xml version="1.0"?>
        <call id="935a38b8-0a80-4965-9db4-f02ab1a813d2">
            <coSpace>22f67f91-1948-47ec-ad4f-4793458cfe0c</coSpace>
            <ownerName>
            </ownerName>
            <durationSeconds>193</durationSeconds>
            <numCallLegs>7</numCallLegs>
            <maxCallLegs>7</maxCallLegs>
            <numParticipantsLocal>7</numParticipantsLocal>
            <locked>false</locked>
            <recording>false</recording>
            <streaming>false</streaming>
            <allowAllMuteSelf>false</allowAllMuteSelf>
            <allowAllPresentationContribution>false</allowAllPresentationContribution>
            <messagePosition>middle</messagePosition>
            <messageDuration>0</messageDuration>
            <activeWhenEmpty>false</activeWhenEmpty>
        </call>
    ''',
    'GET calls/935a38b8-0a80-4965-9db4-f02ab1a813d2/callLegs': '''
        <?xml version="1.0"?>
        <callLegs total="1">
            <callLeg id="976dacd8-bc6b-4526-8bb7-d9050740b7c7">
                <name>Test</name>
                <remoteParty>test@example.org</remoteParty>
                <originalRemoteParty>test@example.or</originalRemoteParty>
                <call>935a38b8-0a80-4965-9db4-f02ab1a813d2</call>
            </callLeg>
        </callLegs>
    ''',
    'GET participants': '''
        <?xml version="1.0"?>
    <participants total="1">
        <participant id="0e44325e-8fec-47a6-9924-ad70f80d0939">
            <name>test</name>
            <call>935a38b8-0a80-4965-9db4-f02ab1a813d2</call>
        </participant>
        </participants>
        '''.strip(),
    'GET calls/935a38b8-0a80-4965-9db4-f02ab1a813d2/participants': State({
        'initial': '''
        <?xml version="1.0"?>
    <participants total="1">
        <participant id="0e44325e-8fec-47a6-9924-ad70f80d0939">
            <name>test</name>
            <call>935a38b8-0a80-4965-9db4-f02ab1a813d2</call>
        </participant>
        </participants>
        '''.strip(),

        'multiple_participants': '''
        <?xml version="1.0"?>
    <participants total="2">
        <participant id="0e44325e-8fec-47a6-9924-ad70f80d0939">
            <name>test</name>
            <call>935a38b8-0a80-4965-9db4-f02ab1a813d2</call>
        </participant>
         <participant id="fffffff-8fec-47a6-9924-ad70f80d0939">
            <name>test2</name>
            <call>935a38b8-0a80-4965-9db4-f02ab1a813d2</call>
        </participant>
        </participants>
        '''.strip(),

        'after_call': '''
        <?xml version="1.0"?>
    <participants total="0">
       </participants>
        '''.strip(),
    }),

    'POST calls/935a38b8-0a80-4965-9db4-f02ab1a813d2/participants': {'Location': '/0e44325e-8fec-47a6-9924-ad70f80d0939'},

    'POST tenants': {'Location': '/api/v1/tenants/05284483-deec-41d0-a470-08e562cd6b8f'},
    'POST ldapSources': {'Location': '/api/v1/ldapSources/ldapsource-123'},

    'GET tenants': '''
        <tenants total="1">
            <tenant id="05284483-deec-41d0-a470-08e562cd6b8f">
                <name>Test</name>
            </tenant>
        </tenants>
    ''',

    'GET callLegs': '''
        <?xml version="1.0"?>
        <callLegs total="1">
            <callLeg id="976dacd8-bc6b-4526-8bb7-d9050740b7c7">
                <name>Test</name>
                <remoteParty>test@example.org</remoteParty>
                <originalRemoteParty>test@example.or</originalRemoteParty>
                <call>935a38b8-0a80-4965-9db4-f02ab1a813d2</call>
            </callLeg>
        </callLegs>
    ''',
    'GET callLegs/976dacd8-bc6b-4526-8bb7-d9050740b7c7': '''
        <?xml version="1.0"?>
        <callLeg id="976dacd8-bc6b-4526-8bb7-d9050740b7c7">
            <name>Test</name>
            <remoteParty>test@example.org</remoteParty>
            <originalRemoteParty>test@example.or</originalRemoteParty>
            <call>935a38b8-0a80-4965-9db4-f02ab1a813d2</call>
          <type>acano</type>
          <direction>incoming</direction>
          <canMove>false</canMove>
          <configuration>
            <defaultLayout>telepresence</defaultLayout>
            <participantLabels>true</participantLabels>
            <joinToneParticipantThreshold>1</joinToneParticipantThreshold>
            <leaveToneParticipantThreshold>1</leaveToneParticipantThreshold>
            <sipMediaEncryption>optional</sipMediaEncryption>
            <telepresenceCallsAllowed>false</telepresenceCallsAllowed>
            <sipPresentationChannelEnabled>true</sipPresentationChannelEnabled>
            <changeLayoutAllowed>true</changeLayoutAllowed>
            <bfcpMode>serverOnly</bfcpMode>
            <recordingControlAllowed>false</recordingControlAllowed>
            <streamingControlAllowed>false</streamingControlAllowed>
            <maxCallDurationTime>43200</maxCallDurationTime>
          </configuration>
          <status>
            <state>connected</state>
            <durationSeconds>154</durationSeconds>
            <direction>incoming</direction>
            <groupId>ab76c84c-74be-46e5-81d4-22e06e7de3ac</groupId>
            <encryptedMedia>true</encryptedMedia>
            <unencryptedMedia>false</unencryptedMedia>
            <cipherSuite>AES_CM_128_HMAC_SHA1_80</cipherSuite>
            <layout>allEqual</layout>
            <cameraControlAvailable>false</cameraControlAvailable>
            <rxAudio>
              <codec>opus</codec>
              <packetLossPercentage>0.0</packetLossPercentage>
              <jitter>2</jitter>
              <bitRate>35961</bitRate>
              <gainApplied>0.0</gainApplied>
            </rxAudio>
            <txAudio>
              <codec>opus</codec>
              <packetLossPercentage>0.7</packetLossPercentage>
              <jitter>3</jitter>
              <bitRate>64000</bitRate>
              <roundTripTime>4</roundTripTime>
            </txAudio>
            <rxVideo role="main">
              <codec>h264</codec>
              <width>1280</width>
              <height>720</height>
              <frameRate>9.9</frameRate>
              <bitRate>20969</bitRate>
              <packetLossPercentage>0.0</packetLossPercentage>
              <jitter>10</jitter>
            </rxVideo>
            <txVideo role="main">
              <codec>h264</codec>
              <width>640</width>
              <height>480</height>
              <frameRate>6.9</frameRate>
              <bitRate>450018</bitRate>
              <packetLossPercentage>0.0</packetLossPercentage>
              <jitter>4</jitter>
              <roundTripTime>2</roundTripTime>
            </txVideo>
          </status>
        </callLeg>
    ''',

    '''GET callBridges''': '''
    <?xml version="1.0" ?>
<callBridges total="2">
  <callBridge id="11111111-071a-4e2b-b6ac-b6b8a19fa364">
    <name>cms-1</name>
  </callBridge>
  <callBridge id="22222222-7b18-48f6-8175-baf77efb36bf">
    <name>cms-2</name>
  </callBridge>
</callBridges>
    ''',

    '''GET callBridges/11111111-071a-4e2b-b6ac-b6b8a19fa364''': '''
    <?xml version="1.0" ?>
  <callBridge id="11111111-071a-4e2b-b6ac-b6b8a19fa364">
    <name>cms-1</name>
  </callBridge>
    ''',
    'GET system/configuration/cluster': '''
    <?xml version="1.0" ?>
<cluster>
  <uniqueName>cms-1</uniqueName>
  <maxPeerVideoStreams/>
  <participantLimit/>
  <loadLimit/>
  <newConferenceLoadLimitBasisPoints>5000</newConferenceLoadLimitBasisPoints>
  <existingConferenceLoadLimitBasisPoints>8000</existingConferenceLoadLimitBasisPoints>
</cluster>
    ''',
    'GET recorders': '''
    <?xml version="1.0" ?>
<recorders total="1">
  <recorder id="11111111-c507-4111-ba94-206e52896ff5">
    <url>https://127.0.0.1:447</url>
  </recorder>
</recorders>
    ''',
    'GET streamers': '''
    <?xml version="1.0" ?>
<streamers total="1">
  <streamer id="11111111-c507-4111-ba94-206e52896ff5">
    <url>https://127.0.0.1:448</url>
  </streamer>
</streamers>
    ''',

    'GET tenants/05284483-deec-41d0-a470-08e562cd6b8f': '''
        <?xml version="1.0"?>
        <tenant id="90f72fe6-1077-462a-a1fa-d684b8876be0">
            <name>Test</name>
            <callBrandingProfile>132db9e0-a748-4c20-af02-7fad31d3dea9</callBrandingProfile>
            <ivrBrandingProfile>5a9e6c85-282f-4ac4-8d68-5be4e95ed048</ivrBrandingProfile>
        </tenant>
    ''',

    'GET users': '''
<users total="3">
    <user id="userguid111">
        <userJid>username@example.org</userJid>
    </user>
    <user id="userguid112">
        <userJid>username2@example.org</userJid>
    </user>
    <user id="userguid113">
        <userJid>username3@example.org</userJid>
        <tenant>tenantguid1</tenant>
    </user>
    </users>
    ''',

    'GET users/userguid111': '''
<user id="userguid111">
    <userJid>username@example.org</userJid>
    <name>Test testsson</name>
    <email>test@example.org</email>
    <cdrTag>ou=test&amp;username=username</cdrTag>
</user>
    ''',
    'GET users/userguid112': '''
<user id="userguid112">
    <userJid>username2@example.org</userJid>
    <name>Test testsson</name>
    <email></email>
    <cdrTag>ou=test&amp;username=username</cdrTag>
</user>
    ''',
    'GET users/userguid113': '''
<user id="userguid113">
    <userJid>username3@example.org</userJid>
    <name>Test testsson</name>
    <email>test3@example.org</email>
    <tenant>tenantguid1</tenant>
    <cdrTag>ou=test&amp;username=username</cdrTag>
</user>
    ''',

    'GET users/userguid111/userCoSpaces': '''
    <userCoSpaces total="1">
        <usercoSpace id="123">
            <coSpaceId>22f67f91-1948-47ec-ad4f-4793458cfe0c</coSpaceId>
        </usercoSpace>
        <usercoSpace id="234">
            <coSpaceId>fffffff-1948-47ec-ad4f-4793458cfe0c</coSpaceId>
            <autoGenerated>true</autoGenerated>
        </usercoSpace>
    </userCoSpaces>
    ''',
    'GET users/userguid113/userCoSpaces': '''
    <userCoSpaces total="1">
        <usercoSpace id="123">
            <coSpaceId>22f67f91-1948-47ec-ad4f-4793458cfe0c</coSpaceId>
        </usercoSpace>
        <usercoSpace id="234">
            <coSpaceId>fffffff-1948-47ec-ad4f-4793458cfe0c</coSpaceId>
            <autoGenerated>true</autoGenerated>
        </usercoSpace>
    </userCoSpaces>
    ''',
    'GET users/userguid112/usercoSpaces': '''
    <userCoSpaces total="1">
        <usercoSpace id="123">
            <coSpaceId>22f67f91-1948-47ec-ad4f-4793458cfe0c</coSpaceId>
        </usercoSpace>
        <usercoSpace id="234">
            <coSpaceId>fffffff-1948-47ec-ad4f-4793458cfe0c</coSpaceId>
            <autoGenerated>true</autoGenerated>
        </usercoSpace>
    </userCoSpaces>
    ''',
    'GET system/alarms': '''
        <?xml version="1.0"?>
        <alarms total="1">
                <alarm id="9c346d65-f698-4519-8949-8ec650888a5a">
                        <type>cdrConnectionFailure</type>
                        <activeTimeSeconds>264243</activeTimeSeconds>
                </alarm>
        </alarms>
        ''',
}


def acano_post(self, url, *args, **kwargs):
    from . import state
    method = kwargs.pop('method', '') or 'POST'

    url = url.replace('/api/v1/', '')

    def ret(response, url):
        if isinstance(response, State):
            response = response.get(state.url_state) or response.get('initial')
        if isinstance(response, tuple):
            return FakeResponse(response[1], status_code=response[0], url=url)
        else:
            return FakeResponse(response, url=url)

    url = re.sub(r'\?.*', '', url)  # try without query

    for call, response in sorted(iter(list(acano_requests.items())), key=lambda x: -len(x[0])):

        if call == '%s %s' % (method, url):
            return ret(response, url)

    if url.endswith('/userCoSpaces'):
        if method == "POST":
            return FakeResponse('', status_code=301, url=url + '/1')
        return FakeResponse('''<userCoSpaces total="0"></userCoSpaces>''')
    if url.endswith('/coSpaceUsers'):
        if method == "POST":
            return FakeResponse({'Location': url + '/1'}, status_code=301)
        return FakeResponse('''<coSpaceUsers total="0"></coSpaceUsers>''')

    return FakeResponse('''<?xml version="1.0"?><error></error>''', url=url)
