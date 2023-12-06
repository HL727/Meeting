from __future__ import annotations

import json
import os
import logging
from ssl import VerifyMode
from typing import List, Mapping, Union, Tuple, Dict, Optional, Sequence, Iterable
from endpoint.ext_api.parser.types import Command

import sentry_sdk
from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.conf import settings
from django.utils.encoding import force_text, force_bytes
from django.utils.translation import ngettext

from sentry_sdk import capture_message
from requests.auth import HTTPDigestAuth

from conferencecenter.tests.mock_data.response import FakeResponse
from endpoint_data.models import EndpointDataFileBase

from endpoint.ext_api.poly_studiox import PolyStudioXProviderAPI
from endpoint.ext_api.types.cisco_ce import CommandDict
from provider.exceptions import ResponseError

from .. import consts
from .parser import poly_hdx as parser
from .parser.cisco_ce import NestedConfigurationXMLResult, NestedStatusXMLResult
from .types.cisco_ce import BasicDataDict, DialInfoDict, StatusDict, CallHistoryDict
from ..consts import CallControlAction
from urllib3 import fields

logger = logging.getLogger(__name__)


class PolyHDXProviderAPI(PolyStudioXProviderAPI):  # TODO correct base api?

    def login(self, force=False):
        # TODO
        self.session = self.get_session()
        pass

    def update_request_kwargs(self, kwargs):
        kwargs['auth'] = HTTPDigestAuth(self.endpoint.username, self.endpoint.password)
        return kwargs

    def get_url(self, path: str):
        return '%s/%s' % (self.get_base_url(), path.lstrip('/'))

    def run_command(
        self,
        command: List[str],
        arguments: Mapping[str, Union[str, List[str]]] = None,
        body=None,
        timeout: int = 300,
    ):

        command = '{} {};'.format(' '.join(command), body or '')
        command = command.split(' ;')[0] + ';'
        response = self.post('a_apicommand.cgi', data={'apicommand': [command]}, timeout=timeout)
        
        if not str(response.status_code).startswith('2'):
            raise self.error('Invalid status code: {}'.format(response.status_code), response)

        try:
            return self._parse_command_result(
                response.content, [{'command': command, 'arguments': arguments, body: bool(body)}]
            )
        except Exception:
            sentry_sdk.capture_exception()
            if settings.TEST_MODE:
                raise
            return [(CommandDict(command, arguments, body), False, response.text)]

    def run_multiple_commands(self, command_dicts: Iterable[CommandDict], timeout=30):
        multiple_commands = ''
        fake_command_dicts = lambda lst=list(command_dicts)[:]: (command_dict for command_dict in lst)

        for command_dict in fake_command_dicts():
            command = command_dict.get('command', [])
            body = command_dict.get('body', '')

            multiple_commands += '{} {};'.format(' '.join(command), body or '')
        
        multiple_commands = multiple_commands.replace(' ;', ';')
        response = self.post('a_apicommand.cgi', data={'apicommand': [multiple_commands]}, timeout=timeout)
        
        if not str(response.status_code).startswith('2'):
            raise self.error('Invalid status code: {}'.format(response.status_code), response)

        try:
            return self._parse_command_result(
                response.content, list(fake_command_dicts())
            )
        except Exception:
            sentry_sdk.capture_exception()
            if settings.TEST_MODE:
                raise
            return [(command_dicts, False, response.text)]

    def _parse_command_result(
        self, content: bytes, commands: List[CommandDict]
    ) -> List[Tuple[CommandDict, bool, str]]:
        # TODO
        def _log_error(message: str, *args):
            from debuglog.models import ErrorLog

            ErrorLog.objects.store(
                title=message % args,
                type='endpoint',
                content=force_text(content),
                customer=self.customer,
                endpoint=self.endpoint,
            )
            with sentry_sdk.push_scope() as scope:
                scope.set_extra('commands', commands)
                scope.set_extra('result', force_text(content))
                capture_message(message % args)

        all_commands = ', '.join(' '.join(c['command']) for c in commands)

        try:
            root = safe_xml_fromstring(content)
        except Exception:
            _log_error('Invalid XML response when running commands')
            raise ResponseError('Empty result returned for {}'.format(all_commands))

        if root.tag != 'apicommands' and not settings.TEST_MODE:
            _log_error('Invalid response tag for run_command, should be Command')
            raise ResponseError('Empty result returned for {}'.format(all_commands))

        result = []
        
        if len(root) == 0 and len(root.keys()) == 0:  # empty result. probably unsupported arguments
            _log_error(
                'Empty run_command result for endpoint %s, software %s. Invalid args for firmware version? %s',
                self.endpoint.pk,
                self.endpoint.status.software_version,
                json.dumps(commands),
            )
            raise ResponseError('Empty result returned for {}'.format(all_commands))

        for command, cmd_result in zip(commands, list(root)):
            status = cmd_result.find('command').get('status')
            text = cmd_result.findtext('result') or ''

            result.append((command, status, text.strip().strip('"')))

            if status != 'success':
                _log_error(
                    'Command %s failed for endpoint %s, software %s',
                    ' '.join(command['command']),
                    self.endpoint.pk,
                    self.endpoint.status.software_version,
                )

        if b'"error"' not in content:
            logger.info(
                'Successfully executed commands for endpoint %s, software %s: %s',
                self.endpoint.pk,
                self.endpoint.status.software_version,
                all_commands,
            )

        return result

    def _fetch_valuespace_data_file(self):

        with open(
            os.path.join(settings.BASE_DIR, 'endpoint_data', 'temp', 'hdxpolycomConfig.xsd')
        ) as fd:
            return FakeResponse(fd.read())

    configuration_key_map = {
        # mapping command key to config key in valuespace file
        'serialNumber' : 'system.info.serialnumber',
        'model': 'system.info.model',
        'softwareVersion': 'system.info.version',
        'sipusername': 'comm.nics.sipnic.sipusername',
        'sipproxyserver': 'comm.nics.sipnic.sipproxyserver',
        'systemName': 'system.info.systemname',
        'h323name': 'comm.nics.h323nic.h323name',
        'e164ext': 'comm.nics.h323nic.h323_e164',
        'gatekeeperip': 'comm.nics.h323nic.gatekeeper.gkipaddress',
        'callinfo': '',
        'camera': ''
    }

    def _fetch_status_data_file(self):
        # TODO
        content = self.get('systemstatus.xml').content
        xmlElement = safe_xml_fromstring(force_text(content))
        values = parser.PolyHdxStatusValueParser(xmlElement).parse()
        
        commands = [
            'serialnum',
            # 'answer video',
            'systemsetting get model',
            'version',
            'systemsetting get sipusername',
            'systemname get',
            'callinfo all',
            'camerainput 1 get',
            'camerainput 2 get',
            'camerainput 3 get',
            'camerainput 4 get',
            'camerainput 5 get'
        ]
       
        command_dicts = ({'command': [command], 'arguments': None, 'body': None } for command in commands)
        results = self.run_multiple_commands(command_dicts=command_dicts)
        
        # # run commands to fetch status data
        # for command in commands:
        #     results.append(self.run_command([command])[0])

        def getFirstContent(command, desc):
            return next(
                (
                    ''.join(x[2].replace('{} '.format(desc), '').strip().strip('"').splitlines())
                    for x in results
                    if x[0]['command'][0] == '{}'.format(command)
                ),
                '',
            )
        cameras = {}

        for num in range(1, 6):
            cameras[num] = getFirstContent('camerainput {} get'.format(num), 'camerainput {}'.format(num))

        commandStatus = {
            'serialNumber': getFirstContent('serialnum', 'serialnum'),
            'model': getFirstContent('systemsetting get model', 'systemsetting model'),
            'softwareVersion': getFirstContent('version', 'version'),
            'sipusername': getFirstContent('systemsetting get sipusername', 'systemsetting sipusername'),
            'systemName': getFirstContent('systemname get', 'systemname'),
            'callinfo': getFirstContent('callinfo all', 'callinfo'),
            'camera': cameras
        }

        return FakeResponse({**values, **commandStatus})

    def _fetch_configuration_data_file(self):
        # TODO
        # profile_content = self.run_command(['language', 'get'])

        commands = [
            'serialnum',
            'systemsetting get model',
            'version',
            'systemsetting get sipusername',
            'systemsetting get sipproxyserver',
            'h323name get',
            'e164ext get',
            'gatekeeperip get',
            'systemname get',
        ]

        results = []
        # run commands to fetch configuration data
        command_dicts = ({'command': [command], 'arguments': None, 'body': None } for command in commands)
        results = self.run_multiple_commands(command_dicts=command_dicts)
        
        # print(results)
        # def getFirstContent(command, desc):
        #     return next(
        #         (
        #             ''.join(x[2].replace('{} '.format(desc), '').strip().strip('"').splitlines())
        #             for x in results
        #             if x[0]['command'] == '{};'.format(command)
        #         ),
        #         '',
        #     )
        def getFirstContent(command, desc):
            return next(
                (
                    ''.join(x[2].replace('{} '.format(desc), '').strip().strip('"').splitlines())
                    for x in results
                    if x[0]['command'][0] == '{}'.format(command)
                ),
                '',
            )

        commandConfig = {
            'serialNumber': getFirstContent('serialnum', 'serialnum'),
            'model': getFirstContent('systemsetting get model', 'systemsetting model'),
            'softwareVersion': getFirstContent('version', 'version'),
            'sipusername': getFirstContent('systemsetting get sipusername', 'systemsetting sipusername'),
            'sipproxyserver': getFirstContent('systemsetting get sipproxyserver', 'systemsetting sipproxyserver'),
            'h323name': getFirstContent('h323name get', 'h323name'),
            'e164ext': getFirstContent('e164ext get', 'e164ext'),
            'gatekeeperip': getFirstContent('gatekeeperip get', 'gatekeeperip'),
            'systemName': getFirstContent('systemname get', 'systemname'),
        }

        profileConfig = self.post('a_exportprofile.cgi').content

        config_data = {}

        for key, value in commandConfig.items():
            config_data[self.configuration_key_map.get(key, key)] = value        

        return FakeResponse({ **config_data, 'profile': force_text(profileConfig) })

    def get_configuration_data(
        self, force=False, fd: Optional[EndpointDataFileBase] = None, require_valuespace=False
    ) -> NestedConfigurationXMLResult:
        fd = fd or self.get_configuration_data_file(force=force)
        # TODO get secure settings?
        # self.post('config', {'names': [k for k,v  in attrib.items() if v == 'REMOVED_SECURE_CONTENT']})
        config_data = json.loads(force_text(fd.content))
        profileConfig = config_data.pop('profile', None)

        values = parser.PolyHdxProfileConfigurationValueParser(profileConfig).parse()
        values.update(config_data)
        config = self.get_configuration_settings(values)

        return config

    def get_basic_data(self, status_data: NestedStatusXMLResult = None) -> BasicDataDict:
        data = status_data or self.get_status_data(True)

        mac = ''
        serial = data.get('serialNumber', '')
        if serial:
            mac = '00E0DB' + serial[6:12]

        return {
            'serial_number': data['serialNumber'],
            'product_name': data['model'],
            'mac_address': self.format_mac_address(mac),
            'ip': data.get('IPNETWORK.IPV6_IPADDRV4'),
            'software_version': data.get('softwareVersion', ''),
            'software_release': None,
            'has_head_count': False,
            'webex_registration': self.endpoint.webex_registration,  # TODO
            'pexip_registration': self.endpoint.pexip_registration,  # TODO
            'sip_registration': '',# data('state', 'READY') in ('READY', 'IN_CALL'),  # TODO
            'sip': data.get('sipusername') or '',
            'sip_display_name': data.get('systemName', ''),
        }

    def get_status(self, data=None) -> StatusDict:
        data = data or self.get_status_data()
        parsedData = {}

        if data.get('callinfo') == 'system is not in a call' or data.get('callinfo') is None or data.get('callinfo') == 'None':
            parsedData['status'] = consts.STATUS.ONLINE
        else:
            parsedData['status'] = consts.STATUS.IN_CALL
            parsedData['infos'] = data.get('callinfo').replace('begin', '').replace('end', '').split('callinfo:')[1:]

        status = parsedData.get('status')
        infos = parsedData.get('infos', [''])[0].split(':')

        call_participant = infos[1] if status == consts.STATUS.IN_CALL else ''
        direction = infos[6] if status == consts.STATUS.IN_CALL else ''
        answer_state = infos[4] if status == consts.STATUS.IN_CALL else ''
        call_duration = 0

        # TODO get volume levels
        muted = infos[5] != 'notmuted' if status == consts.STATUS.IN_CALL else False
        volume = 100
        inputs = []
        
        for num in range(1, 6):
            if data.get('camera.{}'.format(num), '') != '' and not 'error' in data.get('camera.{}'.format(num), ''):
                inputs.append({
                    'label': 'camera {} - {}'.format(num, data.get('camera.{}'.format(num))),
                    'id': num 
                })

        presentation = ''

        # TODO get upgrade status (applicable?)
        upgrade = ''

        # TODO get warnings + diagnostics
        warnings = []
        diagnostics = []

        if data.get('REMOTE_BATTERY.enabled') == False:
            warnings.append('The remote control battery is bad.')

        if data.get('MICS_STR.enabled') == False:
            warnings.append('No microphones are connected.')

        if data.get('UC Board:.enabled') == False:
            warnings.append('The UC Board is not connected.')

        for index in range(0, 5):
            if data.get('GLOBAL_DIRS.{}.enabled'.format(index)) == False:
                warnings.append('The global directory {} is disabled.'.format(index))

        if data.get('IPNETWORK.enabled') == False:
            warnings.append('The system is not connected to an IP network.')

        if data.get('GATEKEEPERC.enabled') == False:
            warnings.append('The system has been unregistered from the gatekeeper. If this was not intentional, check the gatekeeper IP address and that the gatekeeper is configured.')

        if data.get('REGISTRAR_SERVER.enabled') == False:
            warnings.append('No registrar is connected.')

        if data.get('JITC_LOGTHRESC.enabled') == False:
            warnings.append('Percent Filled Threshold: 0 \n Current Percent Filled: 100')

        if data.get('MEETINGPSWD.enable') == False:
            warnings.append('The meeting password is not configured.')

        if data.get('LDAP_SERVER_C.enabled') == False:
            warnings.append('Your system cannot perform this operation. Please verify the LDAP configuration settings or contact your system administrator for assistance.')

        diagnostics = [*warnings]

        return {
            'has_direct_connection': self.endpoint.has_direct_connection,
            'uptime': int(data.get('uptime', '0')),
            'status': status,
            'incoming': call_participant
            if answer_state == 'ringing' and direction == 'incoming'
            else '',
            'in_call': call_participant
            if answer_state in ('connected', 'autoanswered') or direction == 'outgoing'
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

    def add_ca_certificates(self, certificate_content: str):
        certificates = self.validate_ca_certificates(certificate_content)

        data = {
            'removeid': '',
            'sslverificationdepth': 2,
            'certvalidationweb': False,
            'certvalidationclientapps': False,
            'addrootcertbutton': 'Add',
            'htmfile': 'a_certs.htm'
        }
        response = self.post('addcert.cgi', data=data, files={'file': ('test.pem', force_bytes(''.join([certificate.content for certificate in certificates])) , 'application/octet-stream')})

        self.save_provisioned_certificates(certificates)

        return force_text(response.content)

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
            'name': _get('system.info.model'),
            'sip': _get(
                'comm.nics.sipnic.sipusername',
            ),
            'sip_display_name': _get(
                'comm.nics.sipnic.sipusername', 
            ),
            'h323': _get(
                'comm.nics.h323nic.h323name', 
            ),
            'h323_e164': _get(
                'comm.nics.h323nic.h323_e164', 
            ),
            'sip_proxy': _get(
                'comm.nics.sipnic.sipproxyserver',
            ),
            'sip_proxy_username': _get(
                'comm.nics.sipnic.sipusername',  
            ),
            'h323_gatekeeper': _get(
                'comm.nics.h323nic.gatekeeper.gkipaddress',
            ),
        }

    def get_call_history(self, limit=5) -> List[CallHistoryDict]:

        if not self.endpoint.has_direct_connection or not self.endpoint.check_online():
            return self.get_local_call_statistics(limit=limit)

        response = self.get('a_getcdr.cgi')
        parserResult = parser.PolyHdxCallHistoryParser(safe_xml_fromstring(response.content)).parse()
        result: List[CallHistoryDict] = []

        for entry in parserResult[:limit]:
            cur: CallHistoryDict = {
                'number': entry.get('number', ''),
                'name': entry.get('name', ''),
                'ts_start': entry.get('ts_start', ''),
                'type': entry.get('type', ''),
                'protocol': entry.get('protocol', ''), # TODO
                'count': entry.get('count', ''), # TODO
                'history_id': entry.get('history_id', ''), # TODO
                'id': entry.get('id', ''),  # keep? same as # TODO
            }
            result.append(cur)

        return result


    def call_control(self, action: CallControlAction, argument=None):
        "abstraction for basic call control"

        if action == 'dial':
            if 'https://teams.microsoft.com' in argument:
                if self.endpoint.supports_teams:
                    # return self.adhoc_msteams_meeting(argument)
                    raise ResponseError('Teams calls are only availible for Webex registered systems')
                else:
                    raise ResponseError('Teams calls are only availible for Webex registered systems')
            return self.run_command(['dial', 'manual', 'auto', argument, 'h320'])
        elif action == 'answer':
            return self.run_command(['answer', argument]) # argument in (video, phone)
        elif action == 'reject':
            return self.run_command(['hangup', argument]) # argument in (phone, video, all)
        elif action == 'disconnect':
            return self.run_command(['hangup', argument])
        elif action == 'mute':
            if not argument:
                return self.run_command(['Audio', 'Microphones', 'ToggleMute'], {})
            elif argument in ('true', 'on'):
                return self.post('v1/callctrl/mute', json={'data': {'state': 1}}).text
            else:
                return self.post('v1/callctrl/mute', json={'data': {'state': 0}}).text
        elif action == 'volume':
            return self.run_command(['Audio', 'Volume', 'Set'], {'Level': argument})
        elif action == 'reboot':
            return self.run_command(['resetsystem', argument])
        # elif action == 'presentation': # TODO
        #     source = {'PresentationSource': argument} if argument else {}
        #     return self.run_command(['Presentation', 'Start'], source)
        # elif action == 'presentation_stop': # TODO
        #     source = {'PresentationSource': argument} if argument else {}
        #     return self.run_command(['Presentation', 'Stop'], source)

        raise ValueError('Invalid action {}'.format(action))

    def set_password(self, username, password, validate_current_password: Union[bool, str] = True):
        if validate_current_password is True:
            validate_current_password = self.endpoint.password

        response = self.run_command(['setpassword', 'admin', 'room', validate_current_password, password])
        content = response[0]
        if 'password changed' in force_text(content):
            self.endpoint.password = password
            if self.endpoint.pk:
                self.endpoint.save(update_fields=['password'])
            return True

        raise self.error('Password not set: {}'.format(response.decode('utf-8')))

    @classmethod
    def get_update_dial_info_configuration(cls, data, customer=None, versions=None):

        result = []

        if 'name' in data:
            result.append({'key': 'model', 'value': data['name']})

        if 'sip_uri' in data and 'sip' not in data:
            data['sip'] = data.pop('sip_uri')

        if 'sip' in data:
            result.append({'key': 'reg.1.protocol.SIP', 'value': 'True'})
            result.append({'key': 'sipusername', 'value': data['sip']})

        if 'sip_display_name' in data:
            result.append({'key': 'reg.1.label', 'value': data['sip_display_name']})

        if 'h323' in data:
            result.append({'key': 'h323name', 'value': 'True'})
            result.append({'key': 'h323name', 'value': data['h323']})

        if 'h323_e164' in data:
            result.append({'key': 'voIpProt.H323.e164', 'value': data['h323_e164']}) # TODO

        if 'sip_proxy' in data:
            result.append({'key': 'sipproxyserver', 'value': data['sip_proxy']})
            result.append({'key': 'voIpProt.SIP.registrarServer', 'value': data['sip_proxy']})
            result.append({'key': 'voIpProt.SIP.registrarServerType', 'value': 'Standard SIP'})

        if 'sip_proxy_username' in data:
            result.append(
                {
                    'key': 'sipusername',
                    'value': data['sip_proxy_username'],
                }
            )

        sip_proxy_password = cls._get_sip_proxy_password(
            data.get('sip_proxy_password'), customer, data
        )

        if sip_proxy_password is not None:
            result.append(
                {
                    'key': 'voIpProt.SIP.auth.password',
                    'value': sip_proxy_password,
                }
            )

        if 'h323_gatekeeper' in data:
            result.append({'key': 'voIpProt.H323.gk.ipAddress', 'value': data['h323_gatekeeper']})

        return result

    def get_passive_status(self, configuration_data: NestedConfigurationXMLResult = None):

        if not configuration_data:
            configuration_data = self.get_cached_configuration_data(age=10 * 60)[0]
        if not configuration_data:
            configuration_data = self.get_configuration_data()

        this_installation = False
        is_set = False

        host = configuration_data.findtext('provisionserveraddress')

        # protocol = configuration_data.findtext('management.provisioning.protocol') # TODO

        if host:
            url = 'https://{}'.format(host)
        else:
            url = None

        if settings.EPM_HOSTNAME in host or settings.HOSTNAME in host:
            this_installation = True
            is_set = True

        return {
            'is_set': is_set,
            'this_installation': this_installation,
            'url': url,
        }

    def set_configuration(self, config: List[dict], task=None):
        # Command info list needed to implement config set
        # ..........mpautoanswer <get|yes|no|donotdisturb>.........
        # In above command, the keyword is mpautoanswer.

        command_infos = [
                {
                    'name': self.configuration_key_map_reversed.get('.'.join(c['key']))
                    or '.'.join(c['key']),
                    'value': c['value'],
                }
                for c in config
            ]

        commands = [] # TODO derived from command infos to compose up set command
        results = []

        try:
            results = self.run_command(commands)
            task.complete()
        except Exception as e:
            task.add_error('error')

        return results
    
    def get_statistics_parser(self):

        from statistics.models import Server
        from statistics.parser.poly import HdxStatisticsParser
        server = Server.objects.get_for_customer(self.endpoint.customer, type=Server.ENDPOINTS,
                                                 create=dict(name=ngettext('System', 'System', 2),
                                                             type=Server.ENDPOINTS))

        server = Server.objects.get_endpoint_server(self.customer)
        return HdxStatisticsParser(server, self.endpoint)
    
    def update_statistics(self, limit=1000):
        statistics_parser = self.get_statistics_parser()
        error = None
        entries = []

        if not self.endpoint.has_direct_connection or not self.endpoint.check_online():
            entries = self.get_local_call_statistics(limit=limit)
        else:
            try:
                response = self.get('a_getcdr.cgi')

                parserResult = parser.PolyHdxCallHistoryParser(safe_xml_fromstring(response.content)).parse()
                entries = parserResult[:limit]

            except (ResponseError) as e:
                error = e
       
        result = []

        for entry in entries:
            call = statistics_parser.parse_call(entry)
            result.append(call)

        if error:
            raise error

        return result

