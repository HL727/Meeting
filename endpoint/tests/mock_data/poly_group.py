from conferencecenter.tests.mock_data import state
from conferencecenter.tests.mock_data.response import FakeResponse

true, false = True, False
null = None

poly_group_requests = {
    'POST config': {},  # overridden in function
    'POST session': {
        "verified": true
    },
    "POST security/profile/low/verify": 
    {
      "idResults": [],
      "passwordResults": [
        {
          "error": "NOERROR",
          "failedRequirement": {
            "args": [],
            "requirement": ""
          },
          "passwRequirements": [],
          "passwordType": "Admin"
        }
      ]
    },
    'GET system': {
      'build': '670021', 
      'buildType': 'Release', 
      'hardwareVersion': '18', 
      'lanStatus': {'duplex': 'FULL', 'state': 'LAN_UP', 'speedMbps': 1000}, 
      'model': 'RealPresence Group 500', 
      'rcBatteryCondition': 'BATTERY_GOOD', 
      'timeServerState': 'TIMESERVER_UP', 
      'serialNumber': '8215274422C5CV', 
      'softwareVersion': 'Release - 6.2.2.8-670021', 
      'state': 'ASLEEP', 
      'systemName': 'Mividas Poly Group 500', 
      'systemTime': 1664532053000, 
      'uptime': 324967.72, 
      'rebootNeeded': False, 
      'timeOffset': 7200000
    },
    'GET conferences': state.State(
        initial= [{'capabilities': None, 'connections': [], 'terminals': [], 'holdStartTime': None, 'holdState': 'NOTHELD', 'id': 'PENDING', 'startTime': None, 'mediaServerType': None, 'mediaServerControlEvent': None, 'isLargeConfMode': False, 'isMute': False, 'isPendingConference': True, 'isSvcConference': False, 'isWaitingInLobby': False, 'isHolding': False, 'isActive': False, 'isAVMCUConfernce': False, 'duration': 0, 'totalParticipants': 0}],
        in_call=[
            {
                "capabilities": {
                    "canAcquireChair": false,
                    "canAcquireFloor": false,
                    "canAddTerminal": false,
                    "canAddVideo": false,
                    "canBlastDial": false,
                    "canEscalateCall": false,
                    "canGetRoster": false,
                    "canHangupConference": true,
                    "canHoldConference": true,
                    "canLeaveConference": true,
                    "canMuteConference": false,
                    "canMuteTerminal": false,
                    "canPresent": true,
                    "canRemoveTerminal": true,
                    "canSetFloor": false,
                    "canShowCloseWide": false,
                },
                "connections": [
                    {
                        "address": "testcall@video.mividas.com",
                        "videoEscalationState": "NONE",
                        "authState": "NONE",
                        "callInfo": "SIP",
                        "callType": "SIP",
                        "type": "MCU",
                        "terms": [
                            {
                                "address": "testcall@video.mividas.com",
                                "callerID": "testcall",
                                "termType": "REAL",
                                "systemID": "Pexip Infinity Conferencing Platform/28 (67306.0.0)",
                                "holdState": "NOTHELD",
                                "id": "1",
                                "streamsState": "AVC",
                                "mediaServerType": null,
                                "parentConnectionId": "6",
                                "parentConfId": "0",
                                "name": "testcall",
                                "muted": false,
                                "muteLocked": false,
                                "fullDescription": false,
                                "canSupportMediaStatus": true,
                                "organizer": false,
                            }
                        ],
                        "terminals": [{"href": "/rest/conferences/0/terminals/1", "rel": "item"}],
                        "state": "CONNECTED",
                        "groupname": "",
                        "grouptype": "NONE",
                        "id": "6",
                        "startTime": 1664247879000,
                        "referredBy": "",
                        "mediaType": "AUDIOONLY",
                        "parentConfId": "0",
                        "percentConnected": 100,
                        "rate": 64,
                        "mediaCount": 0,
                        "incoming": false,
                        "encrypted": false,
                        "duration": 8,
                        "causeCode": 0,
                        "canAddVideo": false,
                        "answerable": false,
                        "wakeSubsystems": true,
                    }
                ],
                "terminals": [
                    {
                        "address": "testcall@video.mividas.com",
                        "callerID": "testcall",
                        "termType": "REAL",
                        "systemID": "Pexip Infinity Conferencing Platform/28 (67306.0.0)",
                        "holdState": "NOTHELD",
                        "id": "1",
                        "streamsState": "AVC",
                        "mediaServerType": null,
                        "parentConnectionId": "6",
                        "parentConfId": "0",
                        "name": "testcall",
                        "muted": false,
                        "muteLocked": false,
                        "fullDescription": false,
                        "canSupportMediaStatus": true,
                        "organizer": false,
                    }
                ],
                "holdStartTime": 0,
                "holdState": "NOTHELD",
                "id": "0",
                "startTime": 1664247879000,
                "mediaServerType": null,
                "mediaServerControlEvent": null,
                "isLargeConfMode": false,
                "isMute": false,
                "isPendingConference": false,
                "isSvcConference": false,
                "isWaitingInLobby": false,
                "isHolding": false,
                "isActive": true,
                "isAVMCUConfernce": false,
                "duration": 8,
                "totalParticipants": 0,
            },
            {
                "capabilities": null,
                "connections": [],
                "terminals": [],
                "holdStartTime": null,
                "holdState": "NOTHELD",
                "id": "PENDING",
                "startTime": null,
                "mediaServerType": null,
                "mediaServerControlEvent": null,
                "isLargeConfMode": false,
                "isMute": false,
                "isPendingConference": true,
                "isSvcConference": false,
                "isWaitingInLobby": false,
                "isHolding": false,
                "isActive": false,
                "isAVMCUConfernce": false,
                "duration": 0,
                "totalParticipants": 0,
            },
        ],
        incoming_call=[
          {
            "capabilities": null,
            "connections": [
              {
                "address": "hdx9000@video.mividas.com",
                "answerable": true,
                "authState": "NONE",
                "callInfo": "SIP",
                "callType": "SIP",
                "canAddVideo": false,
                "causeCode": 0,
                "duration": 37,
                "encrypted": false,
                "groupname": "",
                "grouptype": "NONE",
                "id": "2",
                "incoming": true,
                "mediaCount": 0,
                "mediaType": "AUDIOVIDEO",
                "parentConfId": "PENDING",
                "percentConnected": 25,
                "rate": 3796,
                "referredBy": "",
                "startTime": 1664979098000,
                "state": "RINGING",
                "terminals": [],
                "type": "ENDPOINT",
                "videoEscalationState": "NONE"
              }
            ],
            "duration": 0,
            "holdStartTime": null,
            "holdState": "NOTHELD",
            "id": "PENDING",
            "isActive": false,
            "isHolding": false,
            "isMute": false,
            "isSvcConference": false,
            "isWaitingInLobby": false,
            "mediaServerControlEvent": null,
            "mediaServerType": null,
            "startTime": null,
            "terminals": []
          }
        ]
    ),
    'GET system/status': [
      {
        'name': 'system.status.inacall', 
        'languageTag': 'IN_A_CALL', 
        'state': ['off']
      }, 
      {
        'name': 'system.status.autoanswerp2p', 
        'languageTag': 'AUTO_ANSWER_P2P', 
        'state': ['off']
      }, 
      {
        'name': 'system.status.remotecontrol', 
        'languageTag': 'REMOTE_CONTROL', 
        'state': ['up']
      }, 
      {
        'name': 'system.status.microphones', 
        'languageTag': 'MICROPHONES', 
        'state': ['up']
      }, 
      {
        'name': 'system.status.visualboard', 
        'languageTag': 'VISUALBOARD', 
        'state': ['up']
      }, 
      {
        'name': 'system.status.globaldirectory', 
        'languageTag': 'GLOBALDIRECTORY_SERVER', 
        'state': ['off']
      }, 
      {
        'name': 'system.status.ipnetwork', 
        'languageTag': 'IP_NETWORK', 
        'state': ['up']
      }, 
      {
        'name': 'system.status.gatekeeper', 
        'languageTag': 'GATEKEEPER', 
        'state': ['unknown']
      }, 
      {
        'name': 'system.status.sipserver', 
        'languageTag': 'SIP_SERVER', 
        'state': ['up']
      }, 
      {
        'name': 'system.status.logthreshold', 
        'languageTag': 'LOG_THRESHOLD', 
        'state': ['off']
      }, 
      {
        'name': 'system.status.meetingpassword', 
        'languageTag': 'MEETING_PASSWORD', 
        'state': ['off']
      }, 
      {
        'name': 'system.status.provisioning', 
        'languageTag': 'PROVISIONING', 
        'state': ['down']
      }, 
      {
        'name': 'system.status.rpms', 
        'languageTag': 'RPMS', 
        'state': ['off']
      }, 
      {
        'name': 'system.status.modularroom', 
        'languageTag': 'MODULAR_ROOM', 
        'state': ['off']
      }
    ],
    'GET calllog/entries?limit=1000': [
      {
        'causeCode': 0, 
        'precedenceLevel': 'none', 
        'address': 'testcall@video.mividas.com', 
        'callType': 'VOICE_SIP', 
        'callerId': 'testcall', 
        'duration': 29, 
        'endTime': 1664470183000, 
        'name': 'testcall', 
        'rate': 64, 
        'rowId': 108, 
        'startTime': 1664470154000, 
        'type': 'PLACED', 
        'connected': True, 
        'outgoingCall': True
      }, 
      {
        'causeCode': 0, 
        'precedenceLevel': 'none', 
        'address': 'testcall@video.mividas.com', 
        'callType': 'VOICE_SIP', 
        'callerId': 'testcall', 
        'duration': 28, 
        'endTime': 1664470042000, 
        'name': 'testcall', 
        'rate': 64, 
        'rowId': 107, 
        'startTime': 1664470014000, 
        'type': 'PLACED', 
        'connected': True, 
        'outgoingCall': True
      }, 
      {
        'causeCode': 0, 
        'precedenceLevel': 'none', 
        'address': 'testcall@video.mividas.com', 
        'callType': 'VOICE_SIP', 
        'callerId': 'testcall', 
        'duration': 28, 
        'endTime': 1664469832000, 
        'name': 'testcall', 
        'rate': 64, 
        'rowId': 106, 
        'startTime': 1664469804000, 
        'type': 'PLACED', 
        'connected': True, 
        'outgoingCall': True
      }, 
      {
        'causeCode': 16, 
        'precedenceLevel': 'none', 
        'address': 'hdx9000@video.mividas.com', 
        'callType': 'SIP', 
        'callerId': 'hdx9000 ', 
        'duration': 60, 
        'endTime': 1664249091000, 
        'name': 'hdx9000 ', 
        'rate': 0, 
        'rowId': 105, 
        'startTime': 1664249031000, 
        'type': 'MISSED', 
        'connected': False, 
        'outgoingCall': False
      }, 
      {
        'causeCode': 16, 
        'precedenceLevel': 'none', 
        'address': 'hdx9000@video.mividas.com', 
        'callType': 'SIP', 
        'callerId': 'hdx9000', 
        'duration': 60, 
        'endTime': 1664249026000, 
        'name': 'hdx9000', 
        'rate': 0, 
        'rowId': 104, 
        'startTime': 1664248966000, 
        'type': 'MISSED', 
        'connected': False, 
        'outgoingCall': False
      }
    ],
    'GET calllog/entries?limit=5': [
      {
        'causeCode': 0, 
        'precedenceLevel': 'none', 
        'address': 'testcall@video.mividas.com', 
        'callType': 'VOICE_SIP', 
        'callerId': 'testcall', 
        'duration': 29, 
        'endTime': 1664470183000, 
        'name': 'testcall', 
        'rate': 64, 
        'rowId': 108, 
        'startTime': 1664470154000, 
        'type': 'PLACED', 
        'connected': True, 
        'outgoingCall': True
      }, 
      {
        'causeCode': 0, 
        'precedenceLevel': 'none', 
        'address': 'testcall@video.mividas.com', 
        'callType': 'VOICE_SIP', 
        'callerId': 'testcall', 
        'duration': 28, 
        'endTime': 1664470042000, 
        'name': 'testcall', 
        'rate': 64, 
        'rowId': 107, 
        'startTime': 1664470014000, 
        'type': 'PLACED', 
        'connected': True, 
        'outgoingCall': True
      }, 
      {
        'causeCode': 0, 
        'precedenceLevel': 'none', 
        'address': 'testcall@video.mividas.com', 
        'callType': 'VOICE_SIP', 
        'callerId': 'testcall', 
        'duration': 28, 
        'endTime': 1664469832000, 
        'name': 'testcall', 
        'rate': 64, 
        'rowId': 106, 
        'startTime': 1664469804000, 
        'type': 'PLACED', 
        'connected': True, 
        'outgoingCall': True
      }, 
      {
        'causeCode': 16, 
        'precedenceLevel': 'none', 
        'address': 'hdx9000@video.mividas.com', 
        'callType': 'SIP', 
        'callerId': 'hdx9000 ', 
        'duration': 60, 
        'endTime': 1664249091000, 
        'name': 'hdx9000 ', 
        'rate': 0, 
        'rowId': 105, 
        'startTime': 1664249031000, 
        'type': 'MISSED', 
        'connected': False, 
        'outgoingCall': False
      }, 
      {
        'causeCode': 16, 
        'precedenceLevel': 'none', 
        'address': 'hdx9000@video.mividas.com', 
        'callType': 'SIP', 
        'callerId': 'hdx9000', 
        'duration': 60, 
        'endTime': 1664249026000, 
        'name': 'hdx9000', 
        'rate': 0, 
        'rowId': 104, 
        'startTime': 1664248966000, 
        'type': 'MISSED', 
        'connected': False, 
        'outgoingCall': False
      }
    ],
    'GET cameras/near/all':  [
      {'cameraIndex': 1, 'iconName': None, 'model': '', 'name': 'Main', 'sessionID': 0, 'sourceType': 'SRC_PEOPLE', 'stateAutoFocus': 'off', 'stateFreeze': 'off', 'stateMarker': 'off', 'status': None, 'connected': False, 'hasAutoFocus': False, 'hasFocus': False, 'hasFreeze': False, 'hasMarker': False, 'hasPan': False, 'hasTilt': False, 'hasZoom': False, 'nearCamera': True, 'ptzcapable': False, 'selected': True, 'trackable': False}, 
      {'cameraIndex': 2, 'iconName': None, 'model': '', 'name': 'Input_2', 'sessionID': 0, 'sourceType': 'SRC_CONTENT', 'stateAutoFocus': 'off', 'stateFreeze': 'off', 'stateMarker': 'off', 'status': None, 'connected': False, 'hasAutoFocus': False, 'hasFocus': False, 'hasFreeze': False, 'hasMarker': False, 'hasPan': False, 'hasTilt': False, 'hasZoom': False, 'nearCamera': True, 'ptzcapable': False, 'selected': False, 'trackable': False}, 
      {'cameraIndex': 6, 'iconName': None, 'model': '', 'name': 'PPCIP', 'sessionID': 0, 'sourceType': 'SRC_CONTENT', 'stateAutoFocus': 'off', 'stateFreeze': 'off', 'stateMarker': 'off', 'status': None, 'connected': False, 'hasAutoFocus': False, 'hasFocus': False, 'hasFreeze': False, 'hasMarker': False, 'hasPan': False, 'hasTilt': False, 'hasZoom': False, 'nearCamera': True, 'ptzcapable': False, 'selected': False, 'trackable': False}, 
      {'cameraIndex': 7, 'iconName': None, 'model': '', 'name': 'UILAYER1', 'sessionID': 0, 'sourceType': 'SRC_CONTENT', 'stateAutoFocus': 'off', 'stateFreeze': 'off', 'stateMarker': 'off', 'status': None, 'connected': True, 'hasAutoFocus': False, 'hasFocus': False, 'hasFreeze': False, 'hasMarker': False, 'hasPan': False, 'hasTilt': False, 'hasZoom': False, 'nearCamera': True, 'ptzcapable': False, 'selected': False, 'trackable': False}, 
      {'cameraIndex': 9, 'iconName': None, 'model': '', 'name': 'rdpLP', 'sessionID': 0, 'sourceType': 'SRC_CONTENT', 'stateAutoFocus': 'off', 'stateFreeze': 'off', 'stateMarker': 'off', 'status': None, 'connected': False, 'hasAutoFocus': False, 'hasFocus': False, 'hasFreeze': False, 'hasMarker': False, 'hasPan': False, 'hasTilt': False, 'hasZoom': False, 'nearCamera': True, 'ptzcapable': False, 'selected': False, 'trackable': False}
    ]
}

poly_group_configs = {
    "system.info.systemname": 'Mividas Poly Group 500',
    "system.info.humanreadablemodel": 'RealPresence Group 500',
    "system.info.hardwareversion": '18',
    "system.info.humanreadableversion": 'Release - 6.2.2.8-670021',
    "system.info.humanreadableversioncamera": '',
    "system.info.serialnumber": '8215274422C5CV',
    "system.network.wired.ethernet.macaddress": '11:22:33:44:55:66',
    "comm.firewall.nat.usenataddress": 'Off',
    "system.network.wired.ipv4nic.address": '172.21.16.30',
    "system.network.hostname": '1234',
    "comm.nics.h323nic.h323name": 'poly500@video.mividas.com',
    "comm.nics.h323nic.h323extension": '272069088',
    "comm.nics.sipnic.sipusername": 'sip@example.org',
    "comm.firewall.nat.natoutside": '0.0.0.0',
    "system.network.wired.ipv6nic.linklocal": '::/128',
    "system.network.wired.ipv6nic.sitelocal": '::/128',
    "system.network.wired.ipv6nic.globaladdress": '::/128',
    "comm.statistics.timeinlastcall": '0:00:00:27',
    "comm.statistics.totaltimeincalls": '365:04:53:32',
    "comm.statistics.totalnumberofcalls": '97',
    "system.network.wired.ipv6nic.enabled": 'False',
    "system.modularroom.secondary.pairing.state": 'UnPaired',
    "system.modularroom.secondary.pairing.address": '',
    "system.modularroom.secondary.pairing.device": '',
    "comm.nics.h323nic.gatekeeper.gkipaddress": 'video.mividas.com',
    "comm.nics.sipnic.sipproxyserver": 'video.mividas.com'
}

poly_group_provision_headers = {
    'HTTP_CONNECTION': 'keep-alive',
    'HTTP_AUTHORIZATION': 'NTLM TlRMTVNTUAABAAAAFZIIYAsACwAgAAAAAAAAAAAAAABNSVZJREFTLkNPTQ==',
    'HTTP_USER_AGENT': 'Dalvik/1.6.0 (Linux; U; Android 4.0.3; mars Build/IML74K)',
    'HTTP_HOST': 'localhost',
    'HTTP_ACCEPT_ENCODING': 'gzip',
}

poly_group_provision_request = '''
<?xml version="1.0" encoding="UTF-8"?>
<ProvisionRequestMessage xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xs:noNamespaceSchemaLocation="PolarisDeviceAPI.xsd">
<protocolVersion>1.0</protocolVersion>
<deviceType>GROUPSERIES</deviceType>
<serialNumber>8215274422C5CV</serialNumber>
<model>RealPresence Group 500</model>
<pureVc2Device>TRUE</pureVc2Device>
</ProvisionRequestMessage>
'''

poly_group_provision_response = '''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>

<ProvisionResponseMessage xmlns:ns2="http://polycom.com/polaris">
  <protocolVersion>1.0</protocolVersion>
  <status>OK</status>
  <provItems>
    <provItemsVersion>1.0</provItemsVersion>
    <XMPP>
      <enableXMPPDirectory>FALSE</enableXMPPDirectory>
      <allowIM>FALSE</allowIM>
      <verifyCert>FALSE</verifyCert>
    </XMPP>
    <H323>
      <enableH323>False</enableH323>
      <inboundCallRate>2048</inboundCallRate>
      <outboundCallRate>2048</outboundCallRate>
    </H323>
    <SIP>
      <enableSIP>TRUE</enableSIP>
      <uri>sip@example.org</uri>
      <sipProxyServer>proxy.example.org</sipProxyServer>
      <sipRegistrarServer>fra-edge3.mid.vp.vc</sipRegistrarServer>
      <transport>TLS</transport>
      <inboundCallRate>2048</inboundCallRate>
      <outboundCallRate>2048</outboundCallRate>
      <verifyCert>FALSE</verifyCert>
      <LCSDirectoryName></LCSDirectoryName>
      <useADLoginCredentials>FALSE</useADLoginCredentials>
      <backupSipProxyServer></backupSipProxyServer>
      <backupSipRegistrarServer></backupSipRegistrarServer>
      <sipServerType>STANDARD</sipServerType>
      <enableLCSDirectory>FALSE</enableLCSDirectory>
      <sipPassword>Base64value=</sipPassword>
      <sipUserName>Base64value=</sipUserName>
    </SIP>
    <LDAP>
      <enableLDAPDirectory>TRUE</enableLDAPDirectory>
      <serverAddressDirectory>api.exampe.org:389</serverAddressDirectory>
      <serverAddressH350>api.exampe.org:389</serverAddressH350>
      <baseDNPerson>ou=tags,dc=domain</baseDNPerson>
      <baseDNGroup>ou=folders,dc=domain</baseDNGroup>
      <baseDNH350>ou=devices,dc=domain</baseDNH350>
      <queryGroupsList>ldap://{2}/{5}??sub?(objectCategory=group)</queryGroupsList>
      <queryAllMembersOfGroup>ldap://{2}/{4}??sub?(&amp;(memberOf={7})(objectCategory=person))</queryAllMembersOfGroup>
      <querySearchMembersOfGroup>ldap://{2}/{4}??sub?(&amp;(memberOf={7})(objectCategory=person)(cn={0}))</querySearchMembersOfGroup>
      <querySearchAllUsers>ldap://{2}/{4}??sub?(cn={0})</querySearchAllUsers>
      <queryAllMembersOfGroupWH350>ldap://{2}/{4}??sub?(&amp;(memberOf={7})(objectCategory=person)(commURI=*))</queryAllMembersOfGroupWH350>
      <querySearchMembersOfGroupWH350>ldap://{2}/{4}??sub?(&amp;(memberOf={7})(objectCategory=person)(cn={0})(commURI=*))</querySearchMembersOfGroupWH350>
      <querySearchAllUsersWH350>ldap://{2}/{4}??sub?(&amp;(cn={0})(commURI=*))</querySearchAllUsersWH350>
      <attributeGroupName>cn</attributeGroupName>
      <attributeDisplayName>cn</attributeDisplayName>
      <attributeCommonName>cn</attributeCommonName>
      <attributeFirstName>cn</attributeFirstName>
      <attributeLastName>cn</attributeLastName>
      <defaultGroup>groupid=tags,ou=folders,dc=domain</defaultGroup>
      <maxResultSetSize>100</maxResultSetSize>
      <verifyCert>FALSE</verifyCert>
      <usersOnly>(objectCategory=person)</usersOnly>
      <usersOrGroups>(|(objectCategory=person)(objectCategory=group))</usersOrGroups>
      <withDevices>(commURI=*)</withDevices>
      <optQueryAllMembersOfGroup>ldap://{2}/{4}??sub?(&amp;(memberOf={7}){8}{9}{10}{11})</optQueryAllMembersOfGroup>
      <optQuerySearchMembersOfGroup>ldap://{2}/{4}??sub?(&amp;(memberOf={7}){8}{9}{10}{11}(cn={0}))</optQuerySearchMembersOfGroup>
      <optQuerySearchAllUsers>ldap://{2}/{4}??sub?(&amp;(cn={0}){9}{10}{11})</optQuerySearchAllUsers>
      <adminGroup></adminGroup>
      <userGroup></userGroup>
    </LDAP>
    <Phonebook>
      <ServerURL>https://api.exampe.org/dir/plcm/realpresence/1/55555555-b4d4-498b-be90-888888888888/xml</ServerURL>
      <Version>1</Version>
    </Phonebook>
    <CONFIG>
      <generalConfig>
        <softwareUpdateCheckInterval>PT86400S</softwareUpdateCheckInterval>
        <profileUpdateCheckInterval>PT900S</profileUpdateCheckInterval>
        <heartbeatPostInterval>PT3600S</heartbeatPostInterval>
        <inCallStatsPostInterval>PT600S</inCallStatsPostInterval>
        <maintWindow>
          <maintWindowEnabled>FALSE</maintWindowEnabled>
        </maintWindow>
        <maxWebSessions>25</maxWebSessions>
      </generalConfig>
      <dateTime>
        <timeServer>MANUAL</timeServer>
        <timeServerURL>time.videxio.net</timeServerURL>
        <backupTimeServerURL></backupTimeServerURL>
      </dateTime>
      <systemIdentity>
        <systemDisplayName>Dorian LAB-GS 310</systemDisplayName>
      </systemIdentity>
      <systemUtility>
        <directorySearch>AUTO</directorySearch>
      </systemUtility>
      <security>
        <enableEncryption>TRUE</enableEncryption>
      </security>
      <QoS>
        <dynamicBandwidth>TRUE</dynamicBandwidth>
        <maxTxBandwidth>2048</maxTxBandwidth>
        <maxRxBandwidth>2048</maxRxBandwidth>
      </QoS>
    </CONFIG>
  </provItems>
</ProvisionResponseMessage>
'''


def poly_group_post(self, url, data=None, **kwargs):
    method = kwargs.pop('method', '') or 'POST'

    url = url.replace('/rest/', '')

    from provider.exceptions import AuthenticationError, ResponseError

    if 'auth_error' in self.endpoint.hostname:
        raise AuthenticationError('')

    if 'response_error' in self.endpoint.hostname:
        raise ResponseError('')

    if 'invalid_xml' in self.endpoint.hostname:
        return FakeResponse('''<?xml version="1.0"?><Status></Invalid>''')

    def ret(response, url):

        if isinstance(response, state.State):
            response = response.get(state.url_state) or response.get('initial')

        if hasattr(response, 'read'):
            response.seek(0)
            response = response.read()

        if isinstance(response, tuple):
            return FakeResponse(response[1], status_code=response[0], url=url)
        else:
            return FakeResponse(response, url=url)

    if url == 'config':
        return ret(_mock_config(data.get('names', []), state.url_state) if data else [], url)

    for call, response in sorted(iter(list(poly_group_requests.items())), key=lambda x: -len(x[0])):

        if call in '%s %s' % (method, url):
            return ret(response, url)

    print("Missing poly_group mock for {}".format(url))

    return FakeResponse({"error": "Missing mock for {}".format(url)}, url=url, status_code=404)


def _mock_config(names, url_state: str = 'initial'):
    # TODO real structure
    return {
        'vars': [
            {
                "result": "NOERROR",
                'name': name,
                'requestedValue': poly_group_configs.get(name),
                'value': poly_group_configs.get(name),
            }
            for name in names
        ]
    }
