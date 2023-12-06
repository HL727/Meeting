
from __future__ import annotations

import base64
import json
from logging import warning
import os
from typing import TYPE_CHECKING, Literal, Optional, Sequence, Union, Mapping, List

from django.conf import settings

from conferencecenter.tests.mock_data.response import FakeResponse
from endpoint_data.models import EndpointDataFileBase
from provider.exceptions import AuthenticationError, NotFound, ResponseError, ResponseTimeoutError
from django.utils.encoding import force_text, force_bytes
from django.utils.translation import ngettext

from .. import consts
from .parser import poly_group as parser
from .parser.cisco_ce import NestedConfigurationXMLResult, NestedStatusXMLResult
from .poly_studiox import PolyStudioXProviderAPI
from .types.cisco_ce import BasicDataDict, DialInfoDict, StatusDict, ConfigurationDict
from ..consts import STATUS, CallControlAction

if TYPE_CHECKING:
    pass

DEFAULT_SESSION_ID = 'basic'


class PolyGroupProviderAPI(PolyStudioXProviderAPI):

    type: Literal['poly_group'] = 'poly_group'

    configuration_key_map = {
        # key: polycomConfig.xsd name, value: web interface value
    }

    @classmethod
    def get_update_dial_info_configuration(cls, data, customer=None, versions=None):

        result = []

        # if 'name' in data:
            # result.append({'key': '', 'value': data['name']})

        if 'sip_uri' in data and 'sip' not in data:
            data['sip'] = data.pop('sip_uri')

        if 'sip' in data:
            result.append({'key': ['comm', 'nics', 'sipnic', 'sipusername'], 'value': data['sip']})
        result.append({'key': ['SIP', 'enableSIP'], 'value': 'TRUE' if data['sip'] else 'FALSE'})

        if 'sip_display_name' in data:
            result.append({'key': ['system', 'info', 'systemname'], 'value': data['sip_display_name']})

        if 'h323' in data:
            result.append({'key': ['comm', 'nics', 'h323nic', 'h323name'], 'value': data['h323']})

        if 'h323_e164' in data:
            result.append({'key': ['comm', 'nics', 'h323nic', 'extension'], 'value': data['h323_e164']})
        if 'sip_proxy' in data:
            result.append({'key': ['comm', 'nics', 'sipnic', 'sipproxyserver'], 'value': data['sip_proxy']})
            result.append({'key': ['comm', 'nics', 'sipnic', 'sipregistrarserver'], 'value': data['sip_proxy']})
            result.append({'key': ['comm', 'nics', 'sipnic', 'sipregistrarservertype'], 'value': 'STANDARD'})

        if 'sip_proxy_username' in data:
            result.append(
                {
                    'key': ['comm', 'nics', 'sipnic', 'sipusername'],
                    'value': base64.b64encode(data['sip_proxy_username'].encode('utf-8')),
                }
            )

        sip_proxy_password = cls._get_sip_proxy_password(
            data.get('sip_proxy_password'), customer, data
        )

        if sip_proxy_password is not None:
            result.append(
                {
                    'key': ['system', 'proxy', 'webproxy', 'password'],
                    'value': base64.b64encode(sip_proxy_password.encode('utf-8')),
                }
            )

        if 'h323_gatekeeper' in data:  ## TODO
            result.append({'key': ['comm', 'nics', 'h323nic', 'gatekeeper', 'gkipaddress'], 'value': data['h323_gatekeeper']})

        return result

    def get_device_status(self):
        # TODO relevant keys
        config_names = [
                    "system.info.systemname",
                    "system.info.humanreadablemodel",
                    "system.info.hardwareversion",
                    "system.info.humanreadableversion",
                    "system.info.humanreadableversioncamera",
                    "system.info.serialnumber",
                    "system.network.wired.ethernet.macaddress",
                    "comm.firewall.nat.usenataddress",
                    "system.network.wired.ipv4nic.address",
                    "system.network.wireless.ipv4nic.address",
                    "system.network.hostname",
                    "comm.nics.h323nic.h323name",
                    "comm.nics.h323nic.h323extension",
                    "comm.nics.sipnic.sipusername",
                    "comm.firewall.nat.natoutside",
                    "system.network.wired.ipv6nic.linklocal",
                    "system.network.wired.ipv6nic.sitelocal",
                    "system.network.wired.ipv6nic.globaladdress",
                    "comm.statistics.timeinlastcall",
                    "comm.statistics.totaltimeincalls",
                    "comm.statistics.totalnumberofcalls",
                    "comm.callpreference.sipdialplannormalizationstatus",
                    "system.network.wired.ipv6nic.enabled",
                    "system.modularroom.secondary.pairing.state",
                    "system.modularroom.secondary.pairing.address",
                    "system.modularroom.secondary.pairing.device",
                    "comm.callpreference.sipenable",
                    'audio.volume.speakervolume',
                    'device.auth.localAdminPassword'
                ]
        cameras_res = self.get('cameras/near/all')
        if cameras_res.status_code == 200:
            cameras = cameras_res.json()
            for camera in cameras:
                if camera['connected']:
                    config_names.append("sourceman.camera{}.role".format(camera['cameraIndex']))
                    config_names.append("sourceman.camera{}.signaltype".format(camera['cameraIndex']))
                    config_names.append("sourceman.camera{}.name".format(camera['cameraIndex']))
                    config_names.append("sourceman.camera{}.model".format(camera['cameraIndex']))

        return {
            'CODEC': self.fetch_configuration_values(config_names)
        }

    def _fetch_valuespace_data_file(self):

        with open(
            os.path.join(settings.BASE_DIR, 'endpoint_data', 'temp', 'group500polycomConfig.xsd')
        ) as fd:
            return FakeResponse(fd.read())

    def _fetch_configuration_data_file(self):
        # Not same format :(
        # profile = self.get_session().get(self.get_base_url() + '/exportsystemprofile.cgi')

        # Ask for each individual setting:
        values = self.fetch_configuration_values(
            self.remove_redundant_settings(dict(self.get_configuration_settings()).keys())
        )

        return FakeResponse(json.dumps(values, indent=1))

    def _fetch_status_data_file(self):

        activeConferences = self.get('conferences')
        connections = []
        if activeConferences.status_code == 200:
            for conference in activeConferences.json():
                enhancedConnections = ({'isMuted': conference.get('isMuted', False), **connection} for connection in conference['connections']) # Add isMuted to all the connections in one conference
                connections += list(enhancedConnections)
    
        s2 = self.get('system')
        s3 = self.get_device_status()
        # pwd = self.post('config', { 'names': ['sec.auth.admin.room.password'] })
        # print('===========config values===========\n', pwd.content)
        connections_dict = {}
        for index, connection in enumerate(connections):
            connections_dict['connection{}'.format(index)] = connection

        result = {
            'system': {
                **s2.json(),
            },
            'devices': s3,
            **s3['CODEC'],
            'connections': connections_dict
        }
        return FakeResponse(result)

    def get_configuration_data(
        self, force=False, fd: Optional[EndpointDataFileBase] = None, require_valuespace=False
    ) -> NestedConfigurationXMLResult:
        fd = fd or self.get_configuration_data_file(force=force)

        # TODO get secure settings?
        # self.post('config', {'names': [k for k,v  in attrib.items() if v == 'REMOVED_SECURE_CONTENT']})

        values = parser.PolyGroupConfigurationValueParser(fd.content).parse()
        return self.get_configuration_settings(values)

    def get_basic_data(self, status_data: NestedStatusXMLResult = None) -> BasicDataDict:
        data = status_data or self.get_status_data()

        return {
            'serial_number': data['system.serialNumber'],
            'product_name': data['system.model'],
            'mac_address': self.format_mac_address(
                data.get('system.macAddress')
                or data.get('system.network.wired.ethernet.macaddress', '')
            ),
            'ip': data.get('system.network.wired.ipv4nic.address'),
            'software_version': data['system.softwareVersion'],
            'software_release': None,
            'has_head_count': False,
            'webex_registration': self.endpoint.webex_registration,  # TODO
            'pexip_registration': self.endpoint.pexip_registration,  # TODO
            'sip_registration': data['system.state'] in ('READY', 'IN_CALL'),  # TODO
            'sip': data.get('comm.nics.sipnic.sipusername') or '',
            'sip_display_name': data.get('system.systemName', ''),
        }

    def get_status(self, data=None) -> StatusDict:
        data = data or self.get_status_data(True)

        connection_address = data.get('connections.connection0.address', '')
        keys = list(data.all_keys.keys()) 
        if connection_address != '':
            status = consts.STATUS.IN_CALL
        else:
            status = consts.STATUS.ONLINE

        call_participant = connection_address
        direction = ('Incoming' if data.get('connections.connection0.incoming', False) else 'Outgoing') if status == consts.STATUS.IN_CALL else  ''
        answer_state = ('Answered' if data.get('connections.connection0.state') == 'CONNECTED' else 'Unanswered') if status == consts.STATUS.IN_CALL else  ''
        call_duration = data.get('connections.connection0.duration', '') if status == consts.STATUS.IN_CALL else  ''

        
        sourceman_signaltype_keys = [key for key in keys if 'sourceman' in key and 'signaltype' in key and 'CODEC' not in key]
        # TODO get volume levels
        muted = data.get('connections.connection0.isMuted', False)
        volume = data.get('voice.volume.speaker', 100)
        inputs = []

        print(sourceman_signaltype_keys)
        for signaltype_key in sourceman_signaltype_keys:
            inputs.append({
                'label': '{} {}'.format(data.get('.'.join(signaltype_key)), signaltype_key[1].split('camera')[1]),
                'id': signaltype_key[1].split('camera')[1],
            })
        presentation = ''

        # TODO get upgrade status (applicable?)
        upgrade = ''

        # TODO get warnings + diagnostics
        warnings = []
        diagnostics = []

        # if len(inputs) == 0:
        #     warnings.append('Camera is not connected')

        # if data.get('system.network.wireless.ipv4nic.address', '') == '' and data.get('system.network.wire.ipv4nic.address', '') == '':
        #     warnings.append('The system is not connected to an IP network')

        # if data.get('comm.callpreference.sipenable', False) == False:
        #     warnings.append('Sip Registrar server is not registered')
        warning_states = ['down', 'off', 'all_down', 'unknown']

        system_status_res = self.get('system/status')
        # print(system_status_res.json())
        if system_status_res.status_code == 200:
            for individual_status in system_status_res.json():
                if individual_status['state'][0] in warning_states:
                    warnings.append('{} is {}'.format(individual_status['languageTag'], individual_status['state'][0]))
        
        diagnostics = [*warnings]

        return {
            'has_direct_connection': self.endpoint.has_direct_connection,
            'uptime': data['system.uptime'],
            'status': status,
            'incoming': call_participant
            if answer_state == 'Unanswered' and direction == 'Incoming'
            else '',
            'in_call': call_participant
            if answer_state in ('Answered', 'Autoanswered') or direction == 'Outgoing'
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
                'name': _get('system.info.systemname'),
                'sip': _get(
                    'comm.nics.sipnic.sipusername',
                ),
                'sip_display_name': _get(
                    'system.info.systemname',  # TODO
                ),
                'h323': _get(
                    'comm.nics.h323nic.h323name',  # TODO
                ),
                'h323_e164': _get(
                    'comm.nics.h323nic.extension',  # TODO
                ),
                'sip_proxy': _get(
                    'comm.nics.sipnic.sipproxyserver',  # TODO
                ),
                'sip_proxy_username': _get(
                    'comm.nics.sipnic.sipusername',  # TODO
                ),
                'h323_gatekeeper': _get(
                    'comm.nics.h323nic.gatekeeper.gkipaddress',  # TODO
                ),
            }

    def set_password(self, username, password, validate_current_password: Union[bool, str] = True):
        if validate_current_password is True:
            validate_current_password = self.endpoint.password

        response = self.post('session', json={'action': 'VerifyIdentity', 'password': validate_current_password, 'passwordType': 'Admin'})
        session_content = response.json()
        if session_content['verified']:
            response = self.post('security/profile/low/verify', json={ 'ids': None, 'passwords': [{'password': password, 'passwordType': 'Admin'}], 'save': True })
            # print(response.content)
            verify_content = response.json()
            if verify_content['passwordResults'][0]['error'] == 'NOERROR':
                self.endpoint.password = password
                if self.endpoint.pk:
                    self.endpoint.save(update_fields=['password'])
                return True

        raise self.error('Password not set: {}'.format(response.decode('utf-8')))

    def add_ca_certificates(self, certificate_content: str):
        certificates = self.validate_ca_certificates(certificate_content)

        response = self.post('https://{}:{}/addcert.cgi'.format(self.endpoint.ip, self.endpoint.api_port), raw_url=True, files={'files': force_bytes(''.join([certificate.content for certificate in certificates]))})
        self.save_provisioned_certificates(certificates)

        return force_text(response.content)

    def call_control(self, action: CallControlAction, argument=None):
        "abstraction for basic call control"

        if action == 'dial':
            if 'https://teams.microsoft.com' in argument:
                if self.endpoint.supports_teams:
                    return self.adhoc_msteams_meeting(argument)
                else:
                    raise ResponseError(
                        'Teams calls are only availible for Webex registered systems'
                    )
            return self.post(
                'conferences', data={'address': argument, 'rate': 0, 'dialType': 'VOICE'}
            ).text
        elif action == 'answer':  # TODO
            call_type = argument  # '1':
            return self.post(
                'conferences/PENDING/connections/{}'.format(call_type), data={'action': 'answer'}
            ).text
        elif action == 'reject':  # TODO
            call_type = argument  # '1':
            return self.post(
                'conferences/PENDING/connections/{}'.format(call_type), data={'action': 'reject'}
            ).text
        elif action == 'disconnect':  # TODO
            call_reference = '0'
            call_type = argument  # '1': , '2': , '3': , '4':
            return self.post(
                'conferences/{}/connections/{}'.format(call_reference, call_type),
                data={'action': 'hangup'},
            ).text
        elif action == 'mute':
            if not argument:
                status_data = self.get_status()
                if status_data['muted']:
                    return self.put('audio/muted', data=True).text
                else:
                    return self.put('audio/muted', data=False).text 
            elif argument in ('true', 'on'):
                return self.put('audio/muted', data=True).text
            else:
                return self.put('audio/muted', data=False).text
        elif action == 'volume':
            return self.post(
                'config', json={'vars': [{'name': 'audio.volume.speakervolume', 'value': argument}]}
            ).text
        elif action == 'reboot':
            return self.post('system/reboot', json={'action': 'reboot'}).text
        # elif action == 'presentation': # TODO
        #     source = {'PresentationSource': argument} if argument else {}
        #     return self.run_command(['Presentation', 'Start'], source).text
        # elif action == 'presentation_stop': # TODO
        #     source = {'PresentationSource': argument} if argument else {}
        #     return self.run_command(['Presentation', 'Stop'], source).text

        raise ValueError('Invalid action {}'.format(action))

    def get_passive_status(self, configuration_data: NestedConfigurationXMLResult = None):

        if not configuration_data:
            configuration_data = self.get_cached_configuration_data(age=10 * 60)[0]
        if not configuration_data:
            configuration_data = self.get_configuration_data()

        this_installation = False
        is_set = False

        # c_settings = self.get_customer_settings()

        hosts = [
            configuration_data.findtext('management.provisioning.server'),
            configuration_data.findtext('management.provisioning.domain'),
        ]

        # protocol = configuration_data.findtext('management.provisioning.protocol') # TODO

        if any(hosts):
            host = [h for h in hosts if h][0]
            url = 'https://{}'.format(host)
        else:
            url = None

        if settings.EPM_HOSTNAME in hosts or settings.HOSTNAME in hosts:
            this_installation = True
            is_set = True

        return {
            'is_set': is_set,
            'this_installation': this_installation,
            'url': url,
        }

    def get_passive_provisioning_configuration(self) -> List[ConfigurationDict]:
        return [
            {
                'key': ['management', 'provisioning', 'enabled'],
                'value': True,
            },
            {
                'key': ['management', 'provisioining', 'servertype'],
                'value': 'RPRM',
            },
            {
                'key': ['management', 'provisioining', 'server'],
                'value': 'poly-test.dev.mividas.com',
            },            
            {
                'key': ['management', 'provisioining', 'domain'],
                'value': 'k8zk5397',
            },
            {
                'key': ['management', 'provisioning', 'user'],
                'value': 'k8zk65397'
            }
        ]

    def get_statistics_parser(self):

        from statistics.models import Server
        from statistics.parser.poly import GroupStatisticsParser
        server = Server.objects.get_for_customer(self.endpoint.customer, type=Server.ENDPOINTS,
                                                 create=dict(name=ngettext('System', 'System', 2),
                                                             type=Server.ENDPOINTS))

        server = Server.objects.get_endpoint_server(self.customer)
        return GroupStatisticsParser(server, self.endpoint)

    def update_statistics(self, limit=1000):

        parser = self.get_statistics_parser()
        error = None
        entries = []

        if not self.endpoint.has_direct_connection or not self.endpoint.check_online():
            entries = self.get_local_call_statistics(limit=limit)
        else:
            try:
                response = self.get('calllog/entries?limit={}'.format(limit))

                entries = response.json()
            except (ResponseError) as e:
                error = e
       
        result = []

        for entry in entries:
            call = parser.parse_call(entry)
            result.append(call)

        if error:
            raise error

        return result
