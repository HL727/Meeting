from conferencecenter.tests.mock_data import state
from conferencecenter.tests.mock_data.response import FakeResponse

true = True
false = False
null = None

poly_x30_requests = {
    'POST session': {
        "loginStatus": {
            "failedLogins": 0,
            "isPasswordAgeLimitReached": false,
            "lastLoginClient": "192.168.1.211",
            "lastLoginClientType": "WEB",
            "lastLoginTime": 1649695569000,
            "loginResult": "NOLOCKOUT",
        },
        "session": {
            "clientType": "WEB",
            "creationTime": -1299656,
            "isAuthenticated": true,
            "isConnected": false,
            "isNew": true,
            "isStale": false,
            "location": "192.168.1.211",
            "role": "ADMIN",
            "sessionId": "PS6UmUeGR666666666666666666666666/VDyCIuC/Ag6AYRCE",
            "userId": "admin",
        },
        "success": true,
    },
    'POST config': {
        "vars": [
            {
                "name": "management.provisioning.enabled",
                "requestedValue": "True",
                "result": "NOERROR",
            }
        ],
        "rebootNeeded": false,
    },
    'POST devicemanagement/devices': [
        {
            "connectionType": "Unknown",
            "deviceCategory": "SYSTEM",
            "deviceState": "CONNECTED",
            "deviceType": "CODEC",
            "ip": "192.168.1.48",
            "macAddress": "11:22:33:44:55:66",
            "networkInterface": "",
            "productName": "StudioX30",
            "serialNumber": "",
            "softwareVersion": "3.10.0",
            "systemName": "StudioX30-5D98DAFC",
            "uid": "local-system",
        },
        {
            "connectionType": "Corp",
            "deviceCategory": "MODULE",
            "deviceState": "CONNECTED",
            "deviceType": "TOUCHCONTROL",
            "ip": "192.168.1.173",
            "macAddress": "00e0db5f8890",
            "networkInterface": "eth0",
            "productName": "Poly TC8",
            "serialNumber": "8L21355F8890FD",
            "softwareVersion": "3.10.0-210644",
            "systemName": "Poly TC8",
            "uid": "3680471184",
        },
        {
            "connectionType": "HDCI",
            "deviceCategory": "CAMERA",
            "deviceState": "PAIRED",
            "deviceType": "CAMERA",
            "ip": "",
            "macAddress": "",
            "networkInterface": "",
            "productName": "",
            "serialNumber": "",
            "softwareVersion": "",
            "systemName": "",
            "uid": "local-camera",
        },
        {
            "connectionType": "Unknown",
            "deviceCategory": "REMOTE",
            "deviceState": "PAIRED",
            "deviceType": "UNKNOWN",
            "ip": "",
            "macAddress": "",
            "networkInterface": "",
            "productName": "",
            "serialNumber": "",
            "softwareVersion": "",
            "systemName": "",
            "uid": "local-remote",
        },
    ],
    'GET conferences': state.State(
        initial=[],
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
    'GET system': {
        "build": "362035",
        "buildType": "dev",
        "hardwareVersion": "1",
        "lanStatus": {"duplex": "FULL", "speedMbps": 1000, "state": "LAN_UP"},
        "model": "StudioX30",
        "rebootNeeded": false,
        "serialNumber": "8L21385D98DAFC",
        "softwareVersion": "3.10.0",
        "state": "READY",
        "systemName": "StudioX30-5D98DAFC",
        "systemTime": 1649768994000,
        "timeOffset": 7200000,
        "timeServerState": "TIMESERVER_UP",
        "uptime": 3068321.1,
    },
    'GET system/status': [
        {
          "langtag": "PROVISIONING_SERVICE_HEADING",
          "name": "system.status.provisioning",
          "stateList": [
            "down"
          ]
        },
        {
          "langtag": "LAN_NETWORK_HEADING",
          "name": "system.status.ipnetwork",
          "stateList": [
            "up"
          ]
        },
        {
          "langtag": "CAMERA_MODEL_BUILT_IN_1.0",
          "name": "system.status.trackablecamera",
          "stateList": [
            "up"
          ]
        },
        {
          "langtag": "SIP_SERVER_HEADING",
          "name": "system.status.sipserver",
          "stateList": [
            "up"
          ]
        },
        {
          "langtag": "CAMERAS_HEADING",
          "name": "system.status.mr.camera",
          "stateList": [
            "all_up"
          ]
        },
        {
          "langtag": "MICROPHONES_HEADING",
          "name": "system.status.mr.audio",
          "stateList": [
            "all_up"
          ]
        },
        {
          "langtag": "REMOTE_CONTROL_HEADING",
          "name": "system.status.remotecontrol",
          "stateList": [
            "off"
          ]
        },
        {
          "langtag": "LOG_THRESHOLD_HEADING",
          "name": "system.status.logthreshold",
          "stateList": [
            "full"
          ]
        },
        {
          "langtag": "AUTO_ANSWER_P2P_HEADING",
          "name": "system.status.autoanswerp2p",
          "stateList": [
            "off"
          ]
        },
        {
          "langtag": "GATEKEEPER_HEADING",
          "name": "system.status.gatekeeper",
          "stateList": [
            "unknown"
          ]
        },
        {
          "langtag": "SYSTEM_STATUS_GLOBALDIRECTORY_SERVER",
          "name": "system.status.globaldirectory",
          "stateList": [
            "off"
          ]
        },
        {
          "langtag": "CALENDAR_SERVICE_HEADING",
          "name": "system.status.calendar",
          "stateList": [
            "off"
          ]
        }
    ],
    'GET calllog/entries?limit=1000': [
        {
            "address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":7,
            "endTime":1664470157000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":100,
            "startTime":1664470150000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true
        },
        {
            "address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":7,
            "endTime":1664470017000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":99,
            "startTime":1664470010000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true
        },
        {
            "address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":7,
            "endTime":1664469810000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":98,
            "startTime":1664469803000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true
        },
        {
            "address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":9,
            "endTime":1664247884000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":97,
            "startTime":1664247875000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true},{"address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":10,
            "endTime":1664240800000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":96,
            "startTime":1664240790000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true
        }
    ],
    'GET calllog/entries?limit=5': [
        {
            "address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":7,
            "endTime":1664470157000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":100,
            "startTime":1664470150000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true
        },
        {
            "address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":7,
            "endTime":1664470017000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":99,
            "startTime":1664470010000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true
        },
        {
            "address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":7,
            "endTime":1664469810000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":98,
            "startTime":1664469803000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true
        },
        {
            "address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":9,
            "endTime":1664247884000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":97,
            "startTime":1664247875000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true},{"address":"testcall@video.mividas.com",
            "callType":"UNKNOWN",
            "callerId":"testcall",
            "causeCode":0,
            "connected":true,
            "duration":10,
            "endTime":1664240800000,
            "name":"testcall",
            "precedenceLevel":"none",
            "rate":64,
            "rowId":96,
            "startTime":1664240790000,
            "transportType":"voice_sip",
            "type":"PLACED",
            "outgoingCall":true
        }
    ],
    'POST security/password/ADMIN': {'reason': '', 'success': True},
    'GET cameras/near/all': [
      {
        "cameraIndex": 1,
        "iconName": null,
        "model": "BUILT_IN_1.0",
        "name": "Main",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": true,
        "hasAutoFocus": false,
        "hasFocus": true,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": true,
        "hasTilt": true,
        "hasZoom": true,
        "nearCamera": true,
        "ptzcapable": true,
        "selected": true,
        "trackable": true
      },
      {
        "cameraIndex": 2,
        "iconName": null,
        "model": "",
        "name": "HDMI Input",
        "sessionID": 0,
        "sourceType": "SRC_CONTENT",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 3,
        "iconName": null,
        "model": "",
        "name": "",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 4,
        "iconName": null,
        "model": "",
        "name": "",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 5,
        "iconName": null,
        "model": "",
        "name": "",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 6,
        "iconName": null,
        "model": "",
        "name": "PPCIP",
        "sessionID": 0,
        "sourceType": "SRC_CONTENT",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 7,
        "iconName": null,
        "model": "",
        "name": "UILAYER1",
        "sessionID": 0,
        "sourceType": "SRC_CONTENT",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 9,
        "iconName": null,
        "model": "",
        "name": "rdpLP",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 10,
        "iconName": null,
        "model": "",
        "name": "VIRTDEV1",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 11,
        "iconName": null,
        "model": "",
        "name": "VIRTDEV2",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 12,
        "iconName": null,
        "model": "",
        "name": "VIRTDEV3",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      },
      {
        "cameraIndex": 13,
        "iconName": null,
        "model": "",
        "name": "VIRTDEV4",
        "sessionID": 0,
        "sourceType": "SRC_PEOPLE",
        "stateAutoFocus": "off",
        "stateFreeze": "off",
        "stateMarker": "off",
        "connected": false,
        "hasAutoFocus": false,
        "hasFocus": false,
        "hasFreeze": false,
        "hasMarker": false,
        "hasPan": false,
        "hasTilt": false,
        "hasZoom": false,
        "nearCamera": true,
        "ptzcapable": false,
        "selected": false,
        "trackable": false
      }
    ],
    'PUT system/certificates': ''
}

poly_x30_configs = {
    "management.provisioning.enabled": 'true',
    "management.provisioning.server": "https://poly-test.dev.mividas.com/tms/k8zk539/ffd7b2f3f2ff4b35a21a89ab5d4b6267/",
    "management.provisioning.domain": "k8zk5397",
    "management.provisioning.authtype": "Basic",
    "management.provisioning.user": "mividas",
    "management.provisioning.password": "********",
    "comm.nics.sipnic.sipusername": "polyx30@video.mividas.com",
    "system.network.wired.ethernet.macaddress": "",
    "audio.volume.speakervolume": 100
}

poly_x30_provision_data = '''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<PHONE_CONFIG>
  <ALL
     bluetooth.enable="true"
     call.audioOnly.enable="true"
     call.autoAnswer.answerP2PCall="No"
     call.autoAnswer.micMute="true"
     call.cdr.enable="true"
     call.conference.joinLeaveTone.enable="true"
     call.displayIconsInCall="true"
     call.encryption.requireAES="When_Available"
     call.escalate2MCU.conferenceId=""
     call.escalate2MCU.enable="false"
     call.h239.enable="true"
     call.maxTimeInCall="8_hours"
     call.preferredPlaceACallNav="keypad"
     call.preferredSpeed.maxIncoming="6144"
     call.preferredSpeed.outgoing="6144"
     call.recentCalls.enable="true"
     call.recentcalls.maxNumberToDisplay="100"
     call.videoDialPreference.1="sip"
     call.videoDialPreference.2="h323"
     call.voiceDialPreference.1="sip"
     call.voiceDialPreference.2="h323"
     cloud.polycom.analytics.accountcode=""
     cloud.polycom.analytics.enable="false"
     cloud.polycom.analytics.url="https://api-lens.plcm.cloud"
     content.airplay.enable="false"
     content.conference.autoAdjustBandwidth="false"
     content.conference.qualityPreference="Both"
     content.miracast.enable="false"
     content.miracast.operatingchannel="1"
     device.digitalsignage.appspace.location="Public"
     device.digitalsignage.appspace.url=""
     device.digitalsignage.customurl=""
     device.digitalsignage.enabled="false"
     device.digitalsignage.provider="Custom"
     device.digitalsignage.raydiant.location="Public"
     device.digitalsignage.raydiant.url=""
     device.digitalsignage.timeout="1"
     device.local.autoDaylightSavings.enable="true"
     device.local.contact.city=""
     device.local.contact.country=""
     device.local.contact.email=""
     device.local.contact.fax=""
     device.local.contact.organization=""
     device.local.contact.person=""
     device.local.contact.phone=""
     device.local.contact.site=""
     device.local.contact.state=""
     device.local.contact.techSupport=""
     device.local.country="Sweden"
     device.local.datetime.date.format="yyyy_mm_dd"
     device.local.datetime.time.24HourClock="24_Hour"
     device.local.deviceName="StudioX30-5D98DAFC"
     device.local.devicemode.enable="true"
     device.local.devicemode.timeout="120"
     device.local.language="ENGLISHUS"
     device.local.ledbar.brightness="7"
     device.local.ntpServer.address.1=""
     device.local.ntpServer.address.2=""
     device.local.ntpServer.mode="Auto"
     device.local.outofoffice.enabled="false"
     device.local.outofoffice.endtime="08:00"
     device.local.outofoffice.starttime="18:00"
     device.local.roomName="StudioX30"
     device.local.timezone="Europe_Amsterdam"
     device.net.contentSave.enable="true"
     device.net.dns.server.1="192.168.1.1"
     device.net.dns.server.2=""
     device.net.dns.server.3=""
     device.net.dns.server.4=""
     device.net.domain=""
     device.net.dot1x.enable="false"
     device.net.dot1x.identity=""
     device.net.dot1x.password="REMOVED_SECURE_CONTENT"
     device.net.echo.enable="false"
     device.net.ethernet.autoNegotiation="true"
     device.net.ethernet.duplexMode="Full"
     device.net.ethernet.portSpeed="1000Mbps"
     device.net.hostName="StudioX30-5D98DAFC"
     device.net.icmp.txRateLimit="1000"
     device.net.ignoreRedirect="true"
     device.net.ipAddress="192.168.1.48"
     device.net.ipGateway="192.168.1.1"
     device.net.lldp.enable="false"
     device.net.mode="Automatically"
     device.net.secondaryNetwork.contentSave.enable="false"
     device.net.secondaryNetwork.dns.server.1="0.0.0.0"
     device.net.secondaryNetwork.dns.server.2="0.0.0.0"
     device.net.secondaryNetwork.ipAddress="0.0.0.0"
     device.net.secondaryNetwork.ipGateway="0.0.0.0"
     device.net.secondaryNetwork.mode="Automatically"
     device.net.secondaryNetwork.subnetMask="255.255.255.0"
     device.net.secondaryNetwork.type="None"
     device.net.secondaryNetwork.wifi.WEP.key="REMOVED_SECURE_CONTENT"
     device.net.secondaryNetwork.wifi.WPA.password="REMOVED_SECURE_CONTENT"
     device.net.secondaryNetwork.wifi.dot1xEAP.identity=""
     device.net.secondaryNetwork.wifi.dot1xEAP.method="PEAP"
     device.net.secondaryNetwork.wifi.dot1xEAP.password="REMOVED_SECURE_CONTENT"
     device.net.secondaryNetwork.wifi.dot1xEAP.phase2Auth="MSCHAPV2"
     device.net.secondaryNetwork.wifi.enableWebservice="false"
     device.net.secondaryNetwork.wifi.securityType="WPA_PSK"
     device.net.secondaryNetwork.wifi.ssid=""
     device.net.subnetMask="255.255.255.0"
     device.net.unreachableTx.enable="true"
     device.net.vlan.audioPriority="0"
     device.net.vlan.controlPriority="0"
     device.net.vlan.enable="false"
     device.net.vlan.videoPriority="0"
     device.net.vlanid="1"
     device.prov.password="REMOVED_SECURE_CONTENT"
     device.prov.serverName="http://192.168.1.211:8082/ep/poly/asdf"
     device.prov.user="mividas"
     device.remoteControl.audioConfirm="true"
     device.remoteControl.longPressHangup="Power_Off"
     device.remoteControl.numKeypadInCall="Presets"
     device.remoteControl.poundButtonFunction="pound_then_at"
     device.remoteControl.starButtonFunction="period_then_star"
     device.screenSaver.mode="Black"
     device.serial.baud="9600"
     device.serial.flowControl="none"
     device.serial.mode="Control"
     device.serial.parity="none"
     device.serial.stopBits="1"
     device.sleepTimeout="15"
     device.syslog.autoTransfer.customFolderName="Log_archive"
     device.syslog.autoTransfer.folderNameOption="SystemNameAndTimestamp"
     device.syslog.autoTransfer.frequency="Manual"
     device.syslog.autoTransfer.threshold="Off"
     device.syslog.enable="false"
     device.syslog.level="Debug"
     device.syslog.serverName=""
     device.syslog.transport="UDP"
     device.wifi.enable="true"
     diagnostics.remotemonitor.enable="true"
     dir.gds.auth.password="REMOVED_SECURE_CONTENT"
     dir.gds.server.address=""
     dir.ldap.auth.domain=""
     dir.ldap.auth.password="REMOVED_SECURE_CONTENT"
     dir.ldap.auth.useLoginCredentials="false"
     dir.ldap.auth.userId=""
     dir.ldap.authType="ntlm"
     dir.ldap.baseDN=""
     dir.ldap.bindDN=""
     dir.ldap.defaultGroupDN=""
     dir.ldap.server.address=""
     dir.ldap.server.port="389"
     dir.ldap.useSSL="true"
     dir.serverType="Off"
     exchange.auth.domain=""
     exchange.auth.email=""
     exchange.auth.password="REMOVED_SECURE_CONTENT"
     exchange.auth.useLoginCredentials="false"
     exchange.auth.userName=""
     exchange.enable="false"
     exchange.meeting.reminderInterval="5"
     exchange.meeting.reminderSound.enable="true"
     exchange.server.url=""
     exchange.showPrivateMeeting="false"
     homeScreen.addressBar.primary="None"
     homeScreen.addressBar.secondary="Guest Wi-Fi IP Address"
     homeScreen.backgroundImage=""
     homeScreen.display.showpip="true"
     homeScreen.display.showtaskbuttons="1"
     homeScreen.topWidgetType="calendar"
     license.optionKey=""
     license.softupdateKey=""
     log.feature.h323Trace.enable="false"
     log.feature.sipTrace.enable="false"
     mr.primary.autoPair.enable="true"
     net.firewall.fixedPorts.enable="false"
     net.firewall.fixedPorts.tcpStart="3230"
     net.firewall.fixedPorts.udpStart="3230"
     net.firewall.h460.enable="true"
     net.firewall.nat.gabAddressDisplayed="Public"
     net.firewall.nat.h323Compatible="false"
     net.firewall.nat.publicAddress="0.0.0.0"
     net.firewall.nat.useNatAddress="Off"
     net.proxy.address=""
     net.proxy.autoconf="true"
     net.proxy.pacfile.url=""
     net.proxy.port="8080"
     net.proxy.webproxy.auth.password="REMOVED_SECURE_CONTENT"
     net.proxy.webproxy.auth.userName=""
     net.proxy.webproxy.blockBasicAuth="true"
     net.proxy.webproxy.enable="false"
     net.proxy.wpad.enable="true"
     prov.heartbeat.interval="600"
     prov.polling.period="3600"
     prov.softupdate.https.enable="false"
     qos.LPR.enable="true"
     qos.diffServ.audio="0"
     qos.diffServ.fecc="40"
     qos.diffServ.oam="16"
     qos.diffServ.video="0"
     qos.dynamicBandwidth.enable="true"
     qos.intServ.audio="5"
     qos.intServ.fecc="3"
     qos.intServ.oam="0"
     qos.intServ.video="4"
     qos.maxRxBandwidth="6144"
     qos.maxTxBandwidth="6144"
     qos.mtuMode="Default"
     qos.mtuSize="1260"
     qos.rsvp.enable="true"
     qos.tosType="IP_Precedence"
     reports.enabled="false"
     reports.server.URL=""
     sec.TLS.FIPS.enable="false"
     sec.TLS.cert.sslVerificationDepth="3"
     sec.TLS.cert.validatePeer.enable="false"
     sec.TLS.customCaCert.1="REMOVED_SECURE_CONTENT"
     sec.TLS.customCaCert.2="REMOVED_SECURE_CONTENT"
     sec.TLS.customCaCert.3="REMOVED_SECURE_CONTENT"
     sec.TLS.minimumVersion="tlsv1_2"
     sec.TLS.revocation.crl.1="REMOVED_SECURE_CONTENT"
     sec.TLS.revocation.crl.2="REMOVED_SECURE_CONTENT"
     sec.TLS.revocation.crl.3="REMOVED_SECURE_CONTENT"
     sec.TLS.revocation.looseRevocation.enable="false"
     sec.access.maxSessions="50"
     sec.access.room.accessSettings.enable="false"
     sec.access.room.secCode.enable="true"
     sec.auth.accountLockout.admin.failedLoginWindow="Off"
     sec.auth.accountLockout.admin.lockoutAttempts="10"
     sec.auth.accountLockout.admin.lockoutTime="1"
     sec.auth.admin.id="admin"
     sec.auth.admin.password="REMOVED_SECURE_CONTENT"
     sec.auth.admin.room.password="REMOVED_SECURE_CONTENT"
     sec.auth.admin.room.password.canContainIdOrReverse="true"
     sec.auth.admin.room.password.expirationWarning="Off"
     sec.auth.admin.room.password.lowercaseCount="Off"
     sec.auth.admin.room.password.maxAge="Off"
     sec.auth.admin.room.password.maxRepeatedChars="Off"
     sec.auth.admin.room.password.minAge="Off"
     sec.auth.admin.room.password.minChangedChars="Off"
     sec.auth.admin.room.password.minLength="Off"
     sec.auth.admin.room.password.numCount="Off"
     sec.auth.admin.room.password.rejectPrevPassword="Off"
     sec.auth.admin.room.password.specialCharCount="Off"
     sec.auth.admin.room.password.uppercaseCount="Off"
     sec.auth.admin.useRoomPassword="true"
     sec.auth.external.AD.adminGroup=""
     sec.auth.external.AD.enable="false"
     sec.auth.external.AD.server.address=""
     sec.auth.external.AD.userGroup=""
     sec.auth.portLockout.failedLoginWindow="Off"
     sec.auth.portLockout.lockoutAttempts="10"
     sec.auth.portLockout.lockoutTime="1"
     sec.auth.portLockout.ssh.failedLoginWindow="1"
     sec.auth.portLockout.ssh.lockoutAttempts="Off"
     sec.auth.portLockout.ssh.lockoutTime="1"
     sec.auth.remote.password.canContainIdOrReverse="true"
     sec.auth.remote.password.expirationWarning="Off"
     sec.auth.remote.password.lowercaseCount="Off"
     sec.auth.remote.password.maxAge="Off"
     sec.auth.remote.password.maxRepeatedChars="Off"
     sec.auth.remote.password.minAge="Off"
     sec.auth.remote.password.minChangedChars="Off"
     sec.auth.remote.password.minLength="Off"
     sec.auth.remote.password.numCount="Off"
     sec.auth.remote.password.rejectPrevPassword="Off"
     sec.auth.remote.password.specialCharCount="Off"
     sec.auth.remote.password.uppercaseCount="Off"
     sec.auth.snmp.password.canContainIdOrReverse="false"
     sec.auth.snmp.password.lowercaseCount="Off"
     sec.auth.snmp.password.maxRepeatedChars="Off"
     sec.auth.snmp.password.minAge="Off"
     sec.auth.snmp.password.minLength="8"
     sec.auth.snmp.password.numCount="Off"
     sec.auth.snmp.password.rejectPrevPassword="Off"
     sec.auth.snmp.password.specialCharCount="Off"
     sec.auth.snmp.password.uppercaseCount="Off"
     sec.nids.enable="false"
     sec.serialPort.login.mode="adminpassword"
     sec.ssh.enable="true"
     sec.telnet.apiPort="24"
     sec.telnet.apiPortIdleTimeout.enable="false"
     sec.telnet.diagPortIdleTimeout.enable="false"
     sec.telnet.enable="false"
     sec.usb.disableAll="false"
     sec.web.enable="true"
     sec.web.httpsOnly="false"
     sec.web.idleSessionTimeout="10"
     sec.web.port="80"
     snmp.auth.algorithm="SHA"
     snmp.auth.password="REMOVED_SECURE_CONTENT"
     snmp.auth.userId=""
     snmp.community="public"
     snmp.contactName="IT Administrator"
     snmp.enable="false"
     snmp.engineID=""
     snmp.listeningPort="161"
     snmp.locationName=""
     snmp.notification.enabled="false"
     snmp.privacyAlgorithm="CFB-AES128"
     snmp.privacyPassword="REMOVED_SECURE_CONTENT"
     snmp.systemDesc="Videoconferencing Device"
     snmp.transport="UDP"
     snmp.trapTarget.1.address=""
     snmp.trapTarget.1.enable="true"
     snmp.trapTarget.1.messageType="Trap"
     snmp.trapTarget.1.port="162"
     snmp.trapTarget.1.protocolVersion="v3"
     snmp.trapTarget.2.address=""
     snmp.trapTarget.2.enable="true"
     snmp.trapTarget.2.messageType="Trap"
     snmp.trapTarget.2.port="162"
     snmp.trapTarget.2.protocolVersion="v3"
     snmp.trapTarget.3.address=""
     snmp.trapTarget.3.enable="true"
     snmp.trapTarget.3.messageType="Trap"
     snmp.trapTarget.3.port="162"
     snmp.trapTarget.3.protocolVersion="v3"
     snmp.version1.enable="false"
     snmp.version2.enable="false"
     snmp.version3.enable="true"
     upgrade.auto.backwardCompatible="false"
     upgrade.auto.enable="true"
     upgrade.auto.polling.interval="3600"
     upgrade.auto.server.address=""
     upgrade.auto.server.type="prov_server"
     upgrade.auto.timeFrame.enable="true"
     upgrade.auto.timeFrame.startTime="01:00"
     upgrade.auto.timeFrame.stopTime="05:00"
     video.camera.1.backlightCompensation="True"
     video.camera.1.brightness="11"
     video.camera.1.groupViewSize="Medium"
     video.camera.1.name=""
     video.camera.1.orientation="Normal"
     video.camera.1.roomViewPIP="True"
     video.camera.1.saturation="6"
     video.camera.1.sharpness="6"
     video.camera.1.skinEnhancement="True"
     video.camera.1.trackingMode="FrameGroup"
     video.camera.1.trackingSpeed="Normal"
     video.camera.1.type="BuiltInCamera"
     video.camera.1.videoQuality="Sharpness"
     video.camera.1.whiteBalanceMode="auto"
     video.camera.1.wideDynamicRange="True"
     video.camera.autoUpdate.enable="true"
     video.camera.digitalzoomfactor="2"
     video.camera.farControlNearCamera="false"
     video.camera.powerFrequency="60"
     video.camera.preset.snapshot.enable="true"
     video.camera.sleepMode="Save Energy"
     video.content.name="HDMI Input"
     video.layout.contentMirror="false"
     video.layout.selfviewPIP="false"
     video.monitor.1.display="auto"
     video.monitor.1.resolution="1920x1080p 50Hz"
     video.monitor.2.display="off"
     video.monitor.cec.enable="false"
     voIpProt.H323.e164="251645110"
     voIpProt.H323.enable="true"
     voIpProt.H323.gk.auth.enable="false"
     voIpProt.H323.gk.auth.password="REMOVED_SECURE_CONTENT"
     voIpProt.H323.gk.auth.userId="mividas"
     voIpProt.H323.gk.ipAddress="video.mividas.com"
     voIpProt.H323.gk.mode="Off"
     voIpProt.H323.name="polyx30@video.mividas.com"
     voIpProt.SIP.auth.domain=""
     voIpProt.SIP.auth.password="REMOVED_SECURE_CONTENT"
     voIpProt.SIP.auth.useLoginCredentials="false"
     voIpProt.SIP.auth.userId="john"
     voIpProt.SIP.bfcpTransportPreference="Prefer_UDP"
     voIpProt.SIP.enable="true"
     voIpProt.SIP.forceConnectionReuse="false"
     voIpProt.SIP.proxyServer="video.mividas.com"
     voIpProt.SIP.registrarServer="video.mividas.com"
     voIpProt.SIP.registrarServerType="Standard SIP"
     voIpProt.SIP.sbcKeepAlive.enable="true"
     voIpProt.SIP.serverType="Specify"
     voIpProt.SIP.transport="Auto"
     voIpProt.SIP.userName="sip@example.org"
     voice.acousticFence.enable="true"
     voice.acousticFence.radius="5"
     voice.alertTone="Tone_1"
     voice.debutmicautoswitch.enable="false"
     voice.in.hdmi.level="5"
     voice.liveMusicMode.enable="false"
     voice.muteInSleep="true"
     voice.muteReminder.enable="true"
     voice.noiseSuppression.enable="true"
     voice.out.line.mode="variable"
     voice.ringTone="Tone_1"
     voice.stereo.enable="false"
     voice.toneControl.bass="0"
     voice.toneControl.treble="0"
     voice.volume.soundEffects="3"
     voice.volume.speaker="37"
     voice.volume.transmitLevel="0"
  ></ALL>
</PHONE_CONFIG>
'''.strip()


def poly_x_post(self, url, data=None, **kwargs):
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
    if url == 'provisioning/config':
        return ret(poly_x30_provision_data, url)

    for call, response in sorted(iter(list(poly_x30_requests.items())), key=lambda x: -len(x[0])):

        if call in '%s %s' % (method, url):
            return ret(response, url)

    print("Missing poly_x mock for {}".format(url))
    return FakeResponse({"error": "Missing mock for {}".format(url)}, url=url, status_code=404)


def _mock_config(names, url_state: str = 'initial'):
    # TODO real structure
    return {
        'vars': [
            {
                "result": "NOERROR",
                'name': name,
                'value': poly_x30_configs.get(name),
            }
            for name in names
        ]
    }
