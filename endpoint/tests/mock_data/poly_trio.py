from conferencecenter.tests.mock_data import state
from conferencecenter.tests.mock_data.response import FakeResponse

poly_trio_requests = {
    'POST config': {},  # overridden in function
    'GET v1/mgmt/device/runningConfig': {
        'data': {
            "Network": {
                "IPAddress": "172.21.16.100",
                "VLANFiltering": "Disabled",
                "SubnetMask": "255.255.255.0",
                "IPv6ULAAddress": "::",
                "IPv6AddressDiscovery": "DHCP",
                "IPGateway": "172.21.16.1",
                "StormFilterPPS": "38",
                "StormFiltering": "Enabled",
                "IPv6Gateway": "::",
                "IPv6Address": "::",
                "IPv6LinkAddress": "::",
                "VLAN": "",
                "IPStack": "IPv4 Only",
                "PreferredNetwork": "IPv6",
                "CDP": "Enabled",
                "LLDP": "Enabled"
            },
            "DHCP": {
                "Option60Format": "ASCII String",
                "Feature": "Enabled",
                "OfferTimeout": "1",
                "BootServerOption": "161",
                "BootServerUseOption": "Custom then Default",
                "BootServerOptionType": "String",
                "VLANDiscovery": "Default",
                "VLANDiscoveryOption": "129"
            },
            "Provisioning": {
                "FileTxTries": "3",
                "ServerType": "FTP",
                "MaxServers": "8",
                "RetryWait": "1",
                "Server": "",
                "User": "PlcmSpIp",
                "NetworkEnv": "Cable/DSL",
                "TagSerialNo": "Disabled"
            },
            "DNS": {
                "Domain": "infra.mividas.com",
                "PrimaryServer": "172.21.16.1",
                "Feature": "Enabled",
                "SecondaryServer": ""
            },
            "SNTP": {
                "GMTOffsetHours": "0",
                "Server": "172.21.16.1",
                "GMTOffsetSeconds": "0"
            },
            "Syslog": {
                "RenderLevel": "4",
                "Server": "",
                "PrependMAC": "Disabled",
                "Facility": "16",
                "Transport": "UDP"
            }
        },
        'Status': '2000'
    },
    "GET v2/mgmt/device/info": {
        'data': {
            "DeviceType": "HardwareEndpoint",
            "PreferredNetwork": "IPv6",
            "Firmware": {
                "BootBlock": "3.0.6.0002 (65290-001)",
                "Application": "7.2.2.1094 28-Feb-22 15:29",
                "Updater": "7.2.2.1094"
            },
            "DeviceVendor": "Polycom",
            "UpTime": {
                "Seconds": "28",
                "Minutes": "41",
                "Days": "1",
                "Hours": "1"
            },
            "ModelNumber": "Trio 8800",
            "IPAddress": "172.21.16.100",
            "IPStack": "IPv4 Only",
            "IPv6LinkAddress": "::",
            "IPv6Address": "::",
            "IPv6ULAAddress": "::",
            "AppState": "AppStateMenu",
            "MACAddress": "112233445566",
            "AttachedHardware": {},
            "CanApplyShutdownRequest": "True",
            "ReadyToUse": "True",
            "IntendToShutdown": "False"
        },
        'Status': '2000'
    },
    "GET v1/mgmt/lineinfo": {
        "data": [
            {
            "LineNumber": "1",
            "RegistrationStatus": "registered",
            "LineType": "private",
            "SIPAddress": "sip@example.org",
            "Protocol": "Auto",
            "Label": "Poly Trio8800",
            "UserID": "Poly Trio8800",
            "ProxyAddress": "video.mividas.com",
            "Port": "0"
            }
        ],
        "Status": "2000"
    },
    "GET v1/mgmt/network/info": {
        'data': {
            "SubnetMask": "255.255.255.0",
            "DHCP": "enabled",
            "IPV4Address": "172.21.16.100",
            "DHCPServer": "172.21.16.1",
            "ProvServerAddress": "",
            "VLANIDOption": "129",
            "DHCPBootServerUseOption": "Custom+Option66",
            "DHCPBootServerOptionType": "String",
            "DHCPBootServerOption": "161",
            "DHCPOption60Format": "ASCII String",
            "SNTPAddress": "172.21.16.1",
            "IPV6Address": "::",
            "LANSpeed": "100Mbps",
            "VLANDiscoveryMode": "Fixed",
            "LANPortStatus": "active",
            "DefaultGateway": "172.21.16.1",
            "DNSServer": "172.21.16.1",
            "AlternateDNSServer": "",
            "ProvServerType": "FTP",
            "DNSDomain": "infra.mividas.com",
            "ProvServerUser": "PlcmSpIp",
            "LLDP": "enabled",
            "CDPCompatibility": "enabled",
            "VLANID": "",
            "UpgradeServer": "",
            "ZTPStatus": "disabled"
        },
        'Status': '2000'
    },
    "GET v1/mgmt/network/stats": {
        'data': {
            "RxPackets": "1617177",
            "UpTime": "1 day 1:41:50",
            "TxPackets": "1279022"
        },
        'Status': '2000'
    },
    "GET v1/webCallControl/sipStatus": {
        'data': {
            "TotalUser": "1",
            "User": [
                {
                    "Events": [
                    {
                        "Type": "Register",
                        "RegistrationState": "Registering",
                        "CallID": "",
                        "Expires": "6"
                    }
                    ],
                    "Name": "trio8800",
                    "LineNumber": "1",
                    "TotalCalls": "0",
                    "TotalEvents": "1"
                }
            ]
        },
        'Status': '2000'
    },
    "GET v1/mgmt/device/stats": {
        'data': {
            "CPU": {
                "Current": "35.5",
                "Average": "32.9"
            },
            "Memory": {
                "Used": "274051072",
                "Cached": "240484352",
                "Free": "245944320",
                "Total": "519995392",
                "polyapp": {
                    "fordblks": "455568",
                    "hblkhd": "22568960",
                    "uordblks": "34790512",
                    "arena": "12677120"
                },
                "ComAS": "0",
                "SReclaim": "0",
                "pgui": {
                    "fordblks": "162784",
                    "hblkhd": "61412192",
                    "uordblks": "80315424",
                    "arena": "19066016"
                }
            },
            "RAMDiskSize": "67108864",
        },
        'Status': '2000'
    },
    'GET v2/webCallControl/callStatus': state.State(
        initial={
            'data': [],
            'Status': '2000'
        },
        in_call={
            "data": [{
                "Ringing": "0", 
                "Media Direction": "sendrecv", 
                "Protocol": "SIP", 
                "Muted": "1", 
                "RTCPPort": "2227", 
                "Remote Connection IP": "135.181.112.5", 
                "CallState": "Connected", 
                "RemotePartyNumber": "hdx9000", 
                "CallHandle": "41c2c008", 
                "Type": "Incoming", 
                "RemotePartyName": "hdx9000@video.mividas.com", 
                "UIAppearanceIndex": "1*", 
                "StartTime": "2022-10-11T17:28:46", 
                "RTPPort": "2226", 
                "LineID": "1", 
                "CallSequence": "1", 
                "DurationSeconds": "812"
                }], 
            "Status": "2000"
        },
        incoming_call={
            'data': [{
                'Ringing': '1', 
                'Media Direction': 'sendonly', 
                'Protocol': 'SIP', 
                'Muted': '0', 
                'RTCPPort': '1', 
                'Remote Connection IP': '', 
                'CallState': 'Offering', 
                'RemotePartyNumber': 'polyx30', 
                'CallHandle': '41c2c008', 
                'Type': 'Incoming', 
                'RemotePartyName': 'polyx30', 
                'UIAppearanceIndex': '1*', 
                'StartTime': '2022-09-19T09:29:13', 
                'RTPPort': '0', 
                'LineID': '1', 
                'CallSequence': '1', 
                'DurationSeconds': '0'
            }],
            'Status': '2000'
        }
    ),
    'GET v1/mgmt/transferType/get': {
        "data": {"Type": "Consultative"}, 
        "Status": "2000"
    },
    'POST v1/mgmt/config/get': {
        "data": {"device.local.deviceName": {"Value": "", "Source": "device"}, 
        "ptt.volume": {"Value": "-20", "Source": "default"}, 
        "reg.1.server.H323.1.address": {"Value": "video.mividas.com", "Source": "web"}}, "Status": "2000"
    },
    'GET v1/mgmt/callLogs': {
        "data": {
            "Received": [], 
            "Missed": [
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-09-26T08:05:33", 
                    "RemotePartyName": "polyx30", 
                    "RemotePartyNumber": "polyx30"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-09-26T08:06:33", 
                    "RemotePartyName": "StudioX30-5D98DAFC", 
                    "RemotePartyNumber": "polyx30"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-09-26T08:17:46", 
                    "RemotePartyName": "polyx30", 
                    "RemotePartyNumber": "polyx30"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-09-26T08:18:46", 
                    "RemotePartyName": "StudioX30-5D98DAFC", 
                    "RemotePartyNumber": "polyx30"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-09-26T08:19:55", 
                    "RemotePartyName": "polyx30", 
                    "RemotePartyNumber": "polyx30"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-09-26T15:39:03", 
                    "RemotePartyName": "StudioX30-5D98DAFC", 
                    "RemotePartyNumber": "polyx30"}
                ], 
            "Placed": [
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-06-28T16:06:54", 
                    "RemotePartyName": "sip:1234@mindspacecloud.com", 
                    "RemotePartyNumber": "sip:1234@mindspacecloud.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-06-28T16:18:10", 
                    "RemotePartyName": "sip:meetup@video.mividas.com", 
                    "RemotePartyNumber": "sip:meetup@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-06-28T16:18:56", 
                    "RemotePartyName": "0702275815", 
                    "RemotePartyNumber": "0702275815"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-06-29T12:51:38", 
                    "RemotePartyName": "sip:1234@mindspacecloud.com", 
                    "RemotePartyNumber": "sip:1234@mindspacecloud.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "4 mins 49 secs", 
                    "StartTime": "2022-06-29T12:51:46", 
                    "RemotePartyName": "Mividas", 
                    "RemotePartyNumber": "sip:meetup@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-07-13T13:09:07", 
                    "RemotePartyName": "sip:1234@mindspacecloud.com", 
                    "RemotePartyNumber": "sip:1234@mindspacecloud.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "4 secs", 
                    "StartTime": "2022-07-13T13:09:26", 
                    "RemotePartyName": "Mividas", 
                    "RemotePartyNumber": "sip:meetup@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "3 secs", 
                    "StartTime": "2022-08-02T09:56:23", 
                    "RemotePartyName": "Mividas", 
                    "RemotePartyNumber": "sip:meetup@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-08-06T16:47:40", 
                    "RemotePartyName": "sip:1234@mindspacecloud.com", 
                    "RemotePartyNumber": "sip:1234@mindspacecloud.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-08-15T17:48:45", 
                    "RemotePartyName": "Mividas", 
                    "RemotePartyNumber": "meetup**67564@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "", 
                    "StartTime": "2022-09-11T12:12:48", 
                    "RemotePartyName": "sip:polyx30@video.mividas.com", 
                    "RemotePartyNumber": "polyx30@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "26 secs", 
                    "StartTime": "2022-09-26T16:57:29", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "26 secs", 
                    "StartTime": "2022-09-26T17:02:32", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "26 secs", 
                    "StartTime": "2022-09-26T17:04:04", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "25 secs", 
                    "StartTime": "2022-09-26T17:06:32", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "26 secs", 
                    "StartTime": "2022-09-26T17:16:55", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "26 secs", 
                    "StartTime": "2022-09-26T18:19:18", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "27 secs", 
                    "StartTime": "2022-09-26T18:21:51", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "27 secs", 
                    "StartTime": "2022-09-26T18:33:48", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "27 secs", 
                    "StartTime": "2022-09-27T03:06:34", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }, 
                {
                    "LineNumber": "1", 
                    "Duration": "28 secs", 
                    "StartTime": "2022-09-27T05:04:40", 
                    "RemotePartyName": "Test Call Service", 
                    "RemotePartyNumber": "testcall@video.mividas.com"
                }
            ]
        }, 
        "Status": "2000"
    },
    'POST v1/callctrl/dial': {
        'Status': '2000'
    },
    'POST v1/callctrl/mute': {
        'Status': '2000'
    },
    'POST v1/mgmt/safeRestart': {
        'Status': '2000'
    },
    'POST v1/mgmt/config/set': {
        'Status': '2000'
    },
    'POST https://192.168.1.117:443/form-submit/Settings/ChangePassword': {
        'Status': '2000' # TODO don't confirm the content of response yet
    },
    'GET https://172.21.16.100:443/Diagnostics/log?value=app&dummyParam=1665504096942': '''
    1015152006|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152037|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152107|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152138|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152209|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152216|copy |4|00|Could not set the custom header Content-Range for HTTP/s request. Head request failed to get content-length of server file.
    1015152239|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152310|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152341|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152411|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152442|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152457|log  |4|00|UtilLogServerC::uploadFifoLog: upload error. protocol 0 result = 17
    1015152513|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152543|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152614|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152645|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152715|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152738|copy |4|00|Could not set the custom header Content-Range for HTTP/s request. Head request failed to get content-length of server file.
    1015152746|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152817|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152847|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152918|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152949|lldp |4|00|Ignoring corrupt LLDP packet.
    1015153019|lldp |4|00|Ignoring corrupt LLDP packet.
    1015153019|log  |4|00|UtilLogServerC::uploadFifoLog: upload error. protocol 0 result = -1
    ''',
    'GET https://192.168.1.117:443/Diagnostics/log?value=app&dummyParam=1665504096942': '''
    1015152006|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152037|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152107|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152138|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152209|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152216|copy |4|00|Could not set the custom header Content-Range for HTTP/s request. Head request failed to get content-length of server file.
    1015152239|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152310|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152341|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152411|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152442|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152457|log  |4|00|UtilLogServerC::uploadFifoLog: upload error. protocol 0 result = 17
    1015152513|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152543|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152614|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152645|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152715|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152738|copy |4|00|Could not set the custom header Content-Range for HTTP/s request. Head request failed to get content-length of server file.
    1015152746|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152817|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152847|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152918|lldp |4|00|Ignoring corrupt LLDP packet.
    1015152949|lldp |4|00|Ignoring corrupt LLDP packet.
    1015153019|lldp |4|00|Ignoring corrupt LLDP packet.
    1015153019|log  |4|00|UtilLogServerC::uploadFifoLog: upload error. protocol 0 result = -1
    '''
}

poly_trio_configs = {
    "system.info.systemname": '',
}

poly_trio_provision_headers = {
    'HTTP_CONNECTION': 'keep-alive',
    'HTTP_AUTHORIZATION': 'NTLM TlRMTVNTUAABAAAAFZIIYAsACwAgAAAAAAAAAAAAAABNSVZJREFTLkNPTQ==',
    'HTTP_USER_AGENT': 'Dalvik/1.6.0 (Linux; U; Android 4.0.3; mars Build/IML74K)',
    'HTTP_HOST': 'localhost',
    'HTTP_ACCEPT_ENCODING': 'gzip',
}

poly_trio_provision_request = '''
'''

poly_trio_provision_response = '''
'''


def poly_trio_post(self, url, data=None, **kwargs):
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

    if url == 'POST config':
        return ret(_mock_config(data.get('names', []), state.url_state) if data else [], url)

    for call, response in sorted(iter(list(poly_trio_requests.items())), key=lambda x: -len(x[0])):

        if call in '%s %s' % (method, url):
            return ret(response, url)

    print("Missing poly_trio mock for {}".format(url))
    return FakeResponse({"error": "Missing mock for {}".format(url)}, url=url, status_code=404)


def _mock_config(names, url_state: str = 'initial'):
    # TODO real structure
    return {
        'vars': [
            {
                "result": "NOERROR",
                'name': name,
                'requestedValue': poly_trio_configs.get(name),
                'value': poly_trio_configs.get(name),
            }
            for name in names
        ]
    }
