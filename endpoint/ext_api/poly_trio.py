from __future__ import annotations
from cgi import test
from numbers import Number

import os
import json
from textwrap import indent
import time
from typing import Dict, Any, TYPE_CHECKING, Optional, Union, Sequence, List, Mapping
from datetime import timedelta
from base64 import b64encode

from django.conf import settings
from django.utils.encoding import force_text, force_bytes
from django.utils.timezone import now
from django.utils.translation import ngettext

from provider.exceptions import AuthenticationError, NotFound, ResponseError, ResponseTimeoutError

from endpoint_data.models import EndpointDataFileBase
from conferencecenter.tests.mock_data.response import FakeResponse
from endpoint.ext_api.poly_studiox import PolyStudioXProviderAPI
from .parser.cisco_ce import NestedConfigurationXMLResult, NestedStatusXMLResult
from .types.cisco_ce import BasicDataDict, StatusDict, DialInfoDict, CallHistoryDict, ConfigurationDict
from .. import consts
from .parser import poly_trio as parser
from ..consts import STATUS, CallControlAction

if TYPE_CHECKING:
    from requests import Response


class PolyTrioProviderAPI(PolyStudioXProviderAPI):  # TODO correct base api?
    def login(self, force=False):

        if self.endpoint.session_id == 'basic':
            self.endpoint.session_id = ''

        if self.endpoint.session_id and self.endpoint.session_expires:
            if self.endpoint.session_expires > now() and not force:
                return True

        session = self.get_session(trio_login = True)
        post = session.post

        override_function = getattr(self, 'override_post', None)
        if override_function:
            post = override_function

        userAndPass = b64encode(force_bytes("Polycom:{}".format(self.endpoint.password))).decode("ascii")
        headers = { 'Authorization' : 'Basic %s' %  userAndPass }

        response = post(
            '{}/form-submit/auth.htm'.format(self.get_base_url()),
            headers = headers
        )

        if response.status_code in (400, 412) and 'SessionAlreadyActive' in response.text:
            self.session_expires = now() + timedelta(minutes=30)
            self.endpoint.save(update_fields=['session_expires'])
            return True

        if response.status_code == 200 and 'lockparams' not in response.text:
            raise AuthenticationError('Invalid response')

        if response.status_code == 200 and 'SUCCESS' not in response.text:
            raise AuthenticationError('Invalid login')

        self.endpoint.session_id = session.cookies.get_dict()['session']
        self.endpoint.session_expires = now() + timedelta(minutes=30)  # TODO duration?
        if self.endpoint.pk:
            self.endpoint.save(update_fields=['session_id', 'session_expires'])

        self.session.cookies['session'] = self.endpoint.session_id
        index_res = session.get('{}/index.htm'.format(self.get_base_url()))
        self.session.headers['anti-csrf-token'] = str(force_text(index_res.content)).split('meta name="csrf-token" content="')[1].split('"/>')[0]

        return True

    def update_request_kwargs(self, kwargs):
        kwargs['auth'] = ('Polycom', self.endpoint.password)

    def get_url(self, path: str):
        return '%s/api/%s' % (self.get_base_url(), path.lstrip('/'))

    def get_data(self, response: Response) -> Dict[str, Any]:
        """
        Extract json "data" object from response if Status is success (2000)
        """
        if not response.content.startswith(b'{'):
            raise self.error('Invalid response', response)

        content = response.json()
        if content.get('Status') == '2000':
            try:
                return content['data']
            except KeyError:
                pass
        return response.json()

    def _fetch_valuespace_data_file(self):

        with open(
            os.path.join(settings.BASE_DIR, 'endpoint_data', 'temp', 'trio8300polycomConfig.xsd')
        ) as fd:
            return FakeResponse(fd.read())

    def _fetch_status_data_file(self):
        # TODO more values?
        device_status_response = self.get('v2/mgmt/device/info')
        line_status_response = self.get('v1/mgmt/lineinfo')
        network_info_response = self.get('v1/mgmt/network/info')
        network_statistics_response = self.get('v1/mgmt/network/stats')
        user_sip_response = self.get('v1/webCallControl/sipStatus')
        device_stats_response = self.get('v1/mgmt/device/stats')
        call_status_response = self.get('v2/webCallControl/callStatus')
        
        print(call_status_response.content)
        line_dict = {}

        for index, value in enumerate(self.get_data(line_status_response)):
            line_dict["line{}".format(index)] = value

        sip_dict = {}
        for index, value in enumerate(self.get_data(user_sip_response)['User']):
            sip_dict["user{}".format(index)] = value
        call_status = {}
        for index, each_status in enumerate(self.get_data(call_status_response)):
            call_status['callstatus{}'.format(index)] = each_status

        status_data = parser.PolyTrioStatusValueParser(
            json.dumps(
                {
                    "device": {
                        "info": self.get_data(device_status_response),
                        "statistics": self.get_data(device_stats_response),
                    },
                    "line": line_dict,
                    "network": {
                        "info": self.get_data(network_info_response),
                        "statistics": self.get_data(network_statistics_response),
                    },
                    "sipstatus": sip_dict,
                    "callstatus": call_status
                }
            )
        ).parse()
        print('status data', status_data)
        return FakeResponse(status_data)

    def _fetch_configuration_data_file(self):
        # TODO more values?

        running_config_response = self.get('v1/mgmt/device/runningConfig')
        transferType_config_response = self.get('v1/mgmt/transferType/get')
        line_config_response = self.get('v1/mgmt/lineinfo')
        print(line_config_response.content)
        # To Get Local DeviceName for get_basic_data.
        # It is possible to expand on the whole config parameters.
        config_response = self.post('v1/mgmt/config/get', json={'data': ['device.local.deviceName', 'ptt.volume', 'reg.1.server.H323.1.address']})
        print(config_response.content)
        # print(self.post('v1/mgmt/config/get', json={'data': ['device.prov.serverName.set']}).content)
        # provisioning_response = self.post('v1/mgmt/config/set', json={'data': {'ptt.volume': '-30'}})
        # print(provisioning_response.content)
        # res = self.set_configuration([{ 'key': ['ptt', 'volume'], 'value': '-20' }])
        # print(res.content)
        line_dict = {}
        for index, value in enumerate(self.get_data(line_config_response)):
            line_dict["{}".format(index + 1)] = value
        # print(json.dumps(self.get_data(running_config_response), indent=1))
        # print(line_dict)
        mapped_content = self.key_value_map(
            {
                'device': json.loads(force_text(json.dumps(self.get_data(running_config_response)))),
                'call': {
                    'defaultTransferType': self.get_data(transferType_config_response)['Type']
                },
                'reg': line_dict,
                'reg.1.server.H323.1.address': self.get_data(config_response)['reg.1.server.H323.1.address']['Value'],
                'device.local.deviceName': self.get_data(config_response)['device.local.deviceName']['Value']
            }
        )
        # print(json.dumps(mapped_content, indent=1))
        return FakeResponse(json.dumps(mapped_content, indent=1))

    def _ask_for_configuration(self):
        # TODO this only posts to a separate url. Any way to get it right now?
        response = self.post(
            'v1/mgmt/config/export',
            data={'ConfigType': 'ALL', 'URL': self.endpoint.get_provision_url()},
        ).json()
        assert response

        time.sleep(2)  # TODO wait for request in other way?
        return self.get_cached_configuration_data_file(10)

    def get_basic_data(self, status_data: NestedStatusXMLResult = None) -> BasicDataDict:
        data = status_data or self.get_status_data()
        
        return {
            'serial_number': data['device.info.MACAddress'],#data['serialNumber'],
            'product_name': data['device.info.ModelNumber'],
            'mac_address': self.format_mac_address(
                data.get('device.info.MACAddress')
                or data.get('system.network.wired.ethernet.macaddress', '')
            ),
            'ip': data.get('device.info.IPAddress'),
            'software_version': data['device.info.Firmware.Application'],# data['softwareVersion'],
            'software_release': None,
            'has_head_count': False,
            'webex_registration': self.endpoint.webex_registration,  # TODO
            'pexip_registration': self.endpoint.pexip_registration,  # TODO
            'sip_registration': data.get('sipstatus.user0.Events.RegistrationState', '') == 'Registered',# data['state'] in ('READY', 'IN_CALL'),  # TODO
            'sip': data.get('line.line0.SIPAddress'), # data.get('comm.nics.sipnic.sipusername') or '',
            'sip_display_name': data.get('line.line0.Label', ''),
        }

    def get_status(self, data=None) -> StatusDict:
        data = data or self.get_status_data()

        if data.get('callstatus.callstatus0.Type', '') != '':  # TODO fetch calls
            status = consts.STATUS.IN_CALL
        else:
            status = consts.STATUS.ONLINE

        keys = list(data.all_keys.keys()) 
        signaltype_keys = [key for key in keys if 'line' in key and 'Label' in key]
        call_participant = data.get('callstatus.callstatus0.RemotePartyNumber', '')  # TODO fetch active call
        direction = data.get('callstatus.callstatus0.Type', '')
        answer_state = data.get('callstatus.callstatus0.CallState', '')
        call_duration = data.get('callstatus.callstatus0.DurationSeconds', 0)

        # TODO get volume levels
        muted = data.get('callstatus.callstatus0.Muted', '0') == '1'
        volume = 100
        inputs = []
        for signaltype_key in signaltype_keys:
            inputs.append({
                'label': data.get('.'.join(signaltype_key), ''),
                'id': signaltype_key[1].split('line')[1],
            })
        # for index, value in enumerate((line_status_response)):
        #     line_dict["line{}".format(index)] = value
        presentation = ''

        # TODO get upgrade status (applicable?)
        upgrade = ''

        # TODO get warnings + diagnostics
        warnings = []
        diagnostics = []

        log_response = self.get(
            'https://{}:{}/Diagnostics/log?value=app&dummyParam=1665504096942'.format(
                self.endpoint.ip, self.endpoint.api_port
            ),
            raw_url=True,
        )
        warnings = str(force_text(log_response.content)).split('\n')
        diagnostics = [*warnings]
        
        return {
            'has_direct_connection': self.endpoint.has_direct_connection,
            'uptime': int(data['device.info.UpTime.Days'])*3600*24 + int(data['device.info.UpTime.Hours'])*3600 \
            + int(data['device.info.UpTime.Minutes'])*60 + int(data['device.info.UpTime.Seconds']),
            'status': status,
            'incoming': call_participant
            if answer_state == 'Offering' and direction == 'Incoming'
            else '',
            'in_call': call_participant
            if answer_state == 'Connected' or direction == 'Outgoing'
            else '',
            'muted': muted,
            'volume': volume,
            'inputs': inputs,
            'presentation': presentation,
            'call_duration': call_duration,
            'upgrade': upgrade,
            'warnings': warnings,
            'diagnostics': diagnostics,
        }

    configuration_key_map = {
        # device key mapping
        "Option60Format": "option60Type",
        "ASCII String": "ASCII",
        "DHCP": "dhcp",
        "Network": "net",
        "IPStack": "ipStack",
        "BootServerOption": "bootSrvOpt",
        "BootServerOptionType": "bootSrvOptType",
        "BootServerUseOption": "bootSrvUseOpt",
        "VLANDiscoveryOption": "dhcpVlanDiscOpt",
        "SubnetMask": "subnetMask",
        "IPAddress": "ipAddress",
        "VLANFiltering": "etherVlanFilter.set",
        "IPv6ULAAddress": "ipv6ULAAddress",
        "IPv6AddressDiscovery": "ipv6AddrDisc",
        "CDP": "cdpEnabled.set",
        "LLDP": "lldpEnabled.set",
        "IPGateway": "IPgateway",
        "StormFilterPPS": "etherStormFilterPpsValue",
        "StormFiltering": "etherStormFilter.set",
        "Feature": "enabled.set",
        "IPv6Gateway": "ipv6Gateway",
        "IPv6Address": "ipv6Address",
        "IPv6LinkAddress": "ipv6LinkAddress",
        "VLAN": "vlanId",
        "PreferredNetwork": "preferredNetwork",
        "Provisioning": "prov",
        "ServerType": "serverType",
        "MaxServers": "maxRedunServers",
        "Server": "serverName",
        "User": "user",
        "NetworkEnv": "",
        "TagSerialNo": "tagSerialNo",
        "DNS": "dns",
        "Domain": "domain",
        "PrimaryServer": "serverAddress",
        "SecondaryServer": "altSrvAddress",
        "SNTP": "sntp",
        "GMTOffsetHours": "gmtOffset",
        "Server": "serverName",
        "Syslog": "syslog",
        "RenderLevel": "renderLevel",
        "Server": "serverName",
        "PrependMAC": "prependMac",
        "Facility": "facility",
        "Transport": "transport",
        "ProxyAddress": "outboundProxy.address",
        "UserID": "auth.userId",
        "SIPAddress": "address",
        "Label": 'label',
        # "VLANDiscovery": "",
        # "FileTxtries": "",
        # "RetryWait": "",
        # "NetworkEnv": "",

        # device value mapping
        "IPv4 Only": "V4Only",
        "Custom then Default": "CustomAndDefault",
        "Disabled": 0,
        "Enabled": 1,
        "dhcp": "DHCP",
        "IPv6": "V6",
        "IPv4": "V4"
    }

    def key_value_map(self, parent: Dict[str, Union[str, dict]]):
        result = {}

        for k, v in parent.items():

            key = self.configuration_key_map.get(k, k)

            if isinstance(v, dict):
                result[key] = self.key_value_map(v)
            else:
                result[key] = self.configuration_key_map.get(v, v)

        return result

    def get_configuration_data(
        self, force=True, fd: Optional[EndpointDataFileBase] = None, require_valuespace=False
    ) -> NestedConfigurationXMLResult:
        fd = self.get_configuration_data_file(force=force)

        # # TODO get secure settings?
        # # self.post('config', {'names': [k for k,v  in attrib.items() if v == 'REMOVED_SECURE_CONTENT']})

        values = parser.PolyTrioRunningConfigurationValueParser(fd.content).parse()
        return self.get_configuration_settings(values)

    def get_dial_info(
        self, configuration_data: NestedConfigurationXMLResult = None
    ) -> DialInfoDict:

        configuration = configuration_data or self.get_configuration_data()
        def _get(*paths: Sequence[str]):
            for path in paths:
                try:
                    result = configuration.findtext(path)
                    if result:
                        return result
                except AttributeError:
                    pass
            return ''
        return {
            'name': _get('reg.1.label'),
            'sip': _get('reg.1.address'), # if _get('reg.1.protocol.SIP') else '',
            'sip_display_name': _get('reg.1.label'), # if _get('reg.1.protocol.SIP') else '',
            'h323': _get('reg.1.address'), # if _get('reg.1.protocol.H323') else '',
            'h323_e164': _get(
                'voIpProt.H323.e164',  # TODO
            ),
            'sip_proxy': _get(
                'reg.1.outboundProxy.address',
            ),
            'sip_proxy_username': _get(
                'reg.1.auth.userId',
            ),
            'h323_gatekeeper': _get(
                'reg.1.server.H323.1.address',  # TODO
            ),
        }

    @classmethod
    def get_update_dial_info_configuration(cls, data, customer=None, versions=None):

        result = []

        if 'name' in data:
            result.append({'key': ['device', 'local', 'deviceName'], 'value': data['name']})

        if 'sip_uri' in data and 'sip' not in data:
            data['sip'] = data.pop('sip_uri')

        if 'sip' in data:
            result.append({'key': ['reg', '1', 'protocol', 'SIP'], 'value': 'True'})
            result.append({'key': ['reg', '1', 'address'], 'value': data['sip']})

        if 'sip_display_name' in data:
            result.append({'key': ['reg', '1', 'label'], 'value': data['sip_display_name']})

        if 'h323' in data:
            result.append({'key': ['reg', '1', 'protocol', 'H323'], 'value': 'True'})
            result.append({'key': ['reg', '1', 'address'], 'value': data['h323']})

        if 'h323_e164' in data:
            result.append({'key': ['voIpProt', 'H323', 'e164'], 'value': data['h323_e164']}) # TODO

        if 'sip_proxy' in data:
            result.append({'key': ['reg', '1', 'outbounProxy', 'address'], 'value': data['sip_proxy']})
            result.append({'key': ['voIpProt', 'SIP', 'registrarServer'], 'value': data['sip_proxy']})
            result.append({'key': ['voIpProt', 'SIP', 'registrarServerType'], 'value': 'Standard SIP'})

        if 'sip_proxy_username' in data:
            result.append(
                {
                    'key': ['reg', '1', 'auth', 'userId'],
                    'value': data['sip_proxy_username'],
                }
            )

        sip_proxy_password = cls._get_sip_proxy_password(
            data.get('sip_proxy_password'), customer, data
        )

        if sip_proxy_password is not None:
            result.append(
                {
                    'key': ['voIpProt', 'SIP', 'auth', 'password'],
                    'value': sip_proxy_password,
                }
            )

        if 'h323_gatekeeper' in data:
            result.append({'key': ['reg', '1', 'server', 'H323', '1', 'address'], 'value': data['h323_gatekeeper']})

        return result
    def get_add_ca_certificates_config(self, certificate_content: str):
        result = []

        result.append({ 'key': ['sec', 'TLS', 'customCaCert', '1'], 'value': certificate_content })
        result.append({ 'key': ['sec', 'TLS', 'profileSelection', 'SIP'], 'value': 'ApplicationProfile1' })

        return result

    def add_ca_certificates(self, certificate_content: str):
        certificates = self.validate_ca_certificates(certificate_content)
        # response = self.put('system/certificates', files={'files': force_bytes(certificates[0].content)})
        response = self.post(
            'v1/mgmt/config/set',
            json={'data': {'device.sec.TLS.customCaCert1': certificates[0].content}},
        )
        # response = self.post('v1/mgmt/config/get', json={'data': ['device.sec.TLS.customCaCert1']})
        # self.save_provisioned_certificates(certificates)
        return force_text(response.content)

    def get_set_password_config(self, password):
        result = []

        result.append({ 'key': ['device', 'auth', 'localAdminPassword', 'set'], 'value': '1' })
        result.append({ 'key': ['sec', 'auth', 'localAdminPassword'], 'value': password })

        return result
        
    def set_password(self, username, password, validate_current_password: Union[bool, str] = True):
        if validate_current_password is True:
            validate_current_password = self.endpoint.password

        response = self.post(
            'https://{}:{}/form-submit/Settings/ChangePassword'.format(
                self.endpoint.ip, self.endpoint.api_port
            ),
            raw_url=True,
            data={
                'oldadminpwsd': validate_current_password,
                'newadminpswd': password,
                'cnfmadminpswd': password
            }
        )

        if response.status_code == 200:
            self.endpoint.password = password
            if self.endpoint.pk:
                self.endpoint.save(update_fields=['password'])
            return True

        raise self.error('Password not set: {}'.format(response.decode('utf-8')))

    def call_control(self, action: CallControlAction, argument=None):
        "abstraction for basic call control"

        if action == 'dial':
            if 'https://teams.microsoft.com' in argument:
                if self.endpoint.supports_teams:
                    # return self.adhoc_msteams_meeting(argument)
                    raise ResponseError('Teams calls are only availible for Webex registered systems')
                else:
                    raise ResponseError('Teams calls are only availible for Webex registered systems')
            return self.post('v1/callctrl/dial', json={'data': {'Dest': argument}}).text
        elif action == 'answer':
            call_reference = '1'
            return self.post('v1/callctrl/answerCall', json={'data': {'Ref': call_reference}}).text
        elif action == 'reject':
            call_reference = '0'
            return self.post('v1/callctrl/rejectCall', json={'data': {'Ref': call_reference}}).text
        elif action == 'disconnect':
            call_reference = '0'
            return self.post('v1/callctrl/endCall', json={'data': {'Ref': call_reference}}).text
        elif action == 'mute':
            if not argument:
                status_data = self.get_status()
                if status_data['muted']:
                    return self.post('v1/callctrl/mute', json={'data': {'state': 0}}).text
                else:
                    return self.post('v1/callctrl/mute', json={'data': {'state': 1}}).text
            elif argument in ('true', 'on'):
                return self.post('v1/callctrl/mute', json={'data': {'state': 1}}).text
            else:
                return self.post('v1/callctrl/mute', json={'data': {'state': 0}}).text
        elif action == 'volume':
            return self.set_configuration([{ 'key': ['ptt', 'volume'], 'value': '{}'.format(argument) }])
        elif action == 'reboot':
            return self.post('v1/mgmt/safeRestart').text
        # elif action == 'presentation': # TODO
        #     source = {'PresentationSource': argument} if argument else {}
        #     return self.run_command(['Presentation', 'Start'], source)
        # elif action == 'presentation_stop': # TODO
        #     source = {'PresentationSource': argument} if argument else {}
        #     return self.run_command(['Presentation', 'Stop'], source)

        raise ValueError('Invalid action {}'.format(action))

    def get_call_history(self, limit=5) -> List[CallHistoryDict]:

        if not self.endpoint.has_direct_connection or not self.endpoint.check_online():
            return self.get_local_call_statistics(limit=limit)

        response = self.get('v1/mgmt/callLogs')
        result: List[CallHistoryDict] = []

        for key, value in self.get_data(response).items():
            for entry in value:
                cur: CallHistoryDict = {
                    'number': entry.get('RemotePartyNumber', ''),
                    'name': entry.get('RemotePartyName', ''),
                    'ts_start': entry.get('StartTime', ''),
                    'type': key,
                    'protocol': entry.get('callType', ''), # TODO
                    'count': entry.get('rowId', ''), # TODO
                    'history_id': entry.get('rowId', ''), # TODO
                    'id': entry.get('rowId', ''),  # keep? same as # TODO
                }
                result.append(cur)

        return result

    def get_passive_status(self, configuration_data: NestedConfigurationXMLResult = None):

        if not configuration_data:
            configuration_data = self.get_cached_configuration_data(age=10 * 60)[0]
        if not configuration_data:
            configuration_data = self.get_configuration_data()

        this_installation = False
        is_set = False

        c_settings = self.get_customer_settings()

        host = configuration_data.findtext('prov.serverName')
        # protocol = configuration_data.findtext('management.provisioning.protocol') # TODO

        if host:
            url = 'https://{}'.format(host)
        else:
            url = None

        if (settings.EPM_HOSTNAME == host or settings.HOSTNAME == host) and (
            c_settings.provision_path in host
        ):
            this_installation = True
            is_set = True

        return {
            'is_set': is_set,
            'this_installation': this_installation,
            'url': url,
        }

    def set_configuration(self, config: List[dict], task=None):

        result = {}
        for item in config:
            mappedKey = '.'.join(self.configuration_key_map.get(key) or key for key in item['key'])
            result[mappedKey] = item['value']

        response = self.post('v1/mgmt/config/set', json={'data': result})
        content = response.json()

        if task and response.status_code == 200 and content.get('Status') == '2000': 
            task.complete() 
        elif task: 
            task.add_error('error')

        return response.text

    def get_passive_provisioning_configuration(self) -> List[ConfigurationDict]:
        return [
            {
                'key': ['device', 'prov', 'serverType'],
                'value': 'HTTPS',
            },
            {
                'key': ['device', 'prov', 'server'],
                'value': 'poly-test.dev.mividas.com/tms/k8zk539/',
            },            
            {
                'key': ['device', 'prov', 'redunAttemptLimit'],
                'value': 3,
            },
            {
                'key': ['device', 'prov', 'user'],
                'value': 'k8zk539'
            },
            {
                'key': ['device', 'prov', 'redunInterAttemptDelay'],
                'value': 1,
            }
        ]

    def get_statistics_parser(self):

        from statistics.models import Server
        from statistics.parser.poly import TrioStatisticsParser
        server = Server.objects.get_for_customer(self.endpoint.customer, type=Server.ENDPOINTS,
                                                 create=dict(name=ngettext('System', 'System', 2),
                                                             type=Server.ENDPOINTS))

        server = Server.objects.get_endpoint_server(self.customer)
        return TrioStatisticsParser(server, self.endpoint)

    def update_statistics(self, limit=1000):

        parser = self.get_statistics_parser()
        error = None
        entries = {}

        if not self.endpoint.has_direct_connection or not self.endpoint.check_online():
            entries = self.get_local_call_statistics(limit=limit)
        else:
            try:
                response = self.get('v1/mgmt/callLogs')

                entries = self.get_data(response)
            except (ResponseError) as e:
                error = e
       
        result = []
        print('=======UPDATE STATISTICS======\n', entries)
        for key, entry in entries.items(): # key: call type
            for call_data in entry:
                call = parser.parse_call(key, call_data)
                result.append(call)

        if error:
            raise error

        return result
