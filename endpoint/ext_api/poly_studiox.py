from __future__ import annotations
from distutils.command.config import config

import json
import os
import re
from datetime import timedelta, datetime
from typing import TYPE_CHECKING, Dict, Iterable, List, Literal, Optional, Sequence, Union, Mapping

from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.conf import settings
from django.utils.datastructures import MultiValueDict
from django.utils.encoding import force_text, force_bytes
from django.utils.timezone import now
from django.utils.translation import ngettext

from conferencecenter.tests.mock_data.response import FakeResponse
from endpoint_data.models import EndpointDataFileBase
from provider.exceptions import AuthenticationError, NotFound, ResponseError, ResponseTimeoutError

from .. import consts
from .parser import poly_x as parser
from .parser.cisco_ce import NestedConfigurationXMLResult, NestedStatusXMLResult
from .poly_base import PolyBaseProviderAPI
from .types.cisco_ce import BasicDataDict, DialInfoDict, StatusDict, CallHistoryDict, ConfigurationDict
from ..consts import CallControlAction

if TYPE_CHECKING:
    pass

DEFAULT_SESSION_ID = 'basic'


class PolyStudioXProviderAPI(PolyBaseProviderAPI):

    type: Literal['poly_studiox'] = 'poly_studiox'

    def login(self, force=False):

        if self.endpoint.session_id == 'basic':
            self.endpoint.session_id = ''

        if self.endpoint.session_id and self.endpoint.session_expires:
            if self.endpoint.session_expires > now() and not force:
                return True

        post = self.get_session().post

        override_function = getattr(self, 'override_post', None)
        if override_function:
            post = override_function

        response = post(
            self.get_url('session'),
            json={
                'user': self.endpoint.username,
                'password': self.endpoint.password,
                'action': 'Login',
            },
        )
        if response.status_code in (400, 412) and 'SessionAlreadyActive' in response.text:
            self.session_expires = now() + timedelta(minutes=30)
            self.endpoint.save(update_fields=['session_expires'])
            return True

        if response.status_code != 200 or 'success' not in response.text:
            raise AuthenticationError('Invalid response')

        data = response.json()

        if not data.get('success'):
            raise AuthenticationError('Invalid login')

        self.endpoint.session_id = data['session']['sessionId']
        self.endpoint.session_expires = now() + timedelta(minutes=30)  # TODO duration?
        if self.endpoint.pk:
            self.endpoint.save(update_fields=['session_id', 'session_expires'])

        self.session.cookies['session_id'] = self.endpoint.session_id

        return True

    def update_request_kwargs(self, kwargs):
        if 'data' in kwargs and 'json' not in kwargs:
            kwargs['json'] = kwargs.pop('data')
        return kwargs

    configuration_key_map = {
        # key: polycomConfig.xsd name, value: web interface value

        # call configuration
        'call.recentcalls.maxNumberToDisplay': 'uicontrol.apps.recentcalls.maxnumbertodisplay',
        'call.recentCalls.enable': 'uicontrol.apps.recentcalls.enabled',
        'call.maxTimeInCall': 'comm.callsetting.callfeatures.maxtimeincall',
        'call.autoAnswer.answerP2PCall': 'comm.callsetting.callfeatures.autoanswer.answersinglecall',
        'call.autoAnswer.micMute': 'comm.callsetting.callfeatures.autoanswer.muteautoanswer',
        'call.encryption.requireAES': 'comm.callsetting.callfeatures.encryptionenable',
        'call.h239.enable': 'comm.callpreference.h239enable',
        'call.preferredspeed.outgoing': 'comm.callpreference.preferredspeed.ipoutgoing',
        'call.preferredspeed.maxIncoming': 'comm.callpreference.preferredspeed.ipmaxincoming',
        'call.videoDialPreference.1': 'comm.callpreference.networkdialing.videodialpreference',
        'call.videoDialPreference.2': 'comm.callpreference.networkdialing.videodialpreference1',
        'call.voiceDialPreference.1': 'comm.callpreference.networkdialing.voicedialpreference',
        'call.voiceDialPreference.2': 'comm.callpreference.networkdialing.voicedialpreference1',


        # audio configuration
        'voice.ringTone': 'audio.audiotone.alertvideotone',
        'voice.acousticFence.enable': 'audio.qualityprocess.enableacousticfence',
        'voice.acousticFence.radius': 'audio.qualityprocess.acousticfenceradius',
        'voice.volume.soundEffects': 'audio.volume.soundeffectsvolume',
        'voice.volume.speaker': 'audio.volume.speakervolume',
        'voice.in.hdmi.level': 'audio.in13.level',
        "voice.volume.speaker": "audio.volume.speakervolume",

        # device configuration
        'device.local.deviceName': 'system.info.systemname',
        'device.local.roomName': 'room.name',
        'device.screensaver.mode': 'system.screensavermode',
        'device.local.language': 'location.language',
        
        # home screen configuration 
        'homescreen.addressbar.primary': 'uicontrol.apps.home.statusbar.addressprimary',
        'homescreen.addressbar.secondary': 'uicontrol.apps.home.statusbar.addresssecondary',
        'homescreen.display.showtaskbuttons': 'uicontrol.display.showtaskbuttons',
        'homescreen.display.showpip': 'uicontrol.display.showpip',

        # log configuration
        'log.feature.h323Trace.enable': 'comm.callsetting.debug.h323debug',
        'log.feature.sipTrace.enable': 'comm.callsetting.debug.sipdebug'
    }

    def set_configuration(self, config: List[DialInfoDict], task=None):
        result = {
            'vars': [
                {
                    'name': self.configuration_key_map.get('.'.join(c['key']))
                    or '.'.join(c['key']),
                    'value': c['value'],
                }
                for c in config
            ]
        }

        response = self.post('config', result)

        if task and response.status_code == 200: 
            task.complete() 
        elif task: 
            task.add_error('error')

        return response.text

    @classmethod
    def get_update_dial_info_configuration(cls, data, customer=None, versions=None):

        result = []

        if 'name' in data:
            result.append({'key': ['device', 'local', 'deviceName'], 'value': data['name']})

        if 'sip_uri' in data and 'sip' not in data:
            data['sip'] = data.pop('sip_uri')

        if 'sip' in data:
            result.append({'key': ['voIpProt', 'SIP', 'enable'], 'value': 'True'})
            result.append({'key': ['voIpProt', 'SIP', 'userName'], 'value': data['sip']})

        if 'sip_display_name' in data:
            result.append({'key': 'device.local.roomName', 'value': data['sip_display_name']})

        if 'h323' in data:
            result.append({'key': ['voIpProt', 'H323', 'enable'], 'value': 'True'})
            result.append({'key': ['voIpProt', 'H323', 'name'], 'value': data['h323']})

        if 'h323_e164' in data:
            result.append({'key': ['voIpProt', 'H323', 'e164'], 'value': data['h323_e164']})

        if 'sip_proxy' in data:
            result.append({'key': ['voIpProt', 'SIP', 'proxyServer'], 'value': data['sip_proxy']})
            result.append({'key': ['voIpProt', 'SIP', 'registrarServer'], 'value': data['sip_proxy']})
            result.append({'key': ['voIpProt', 'SIP', 'registrarServerType'], 'value': 'Standard SIP'})

        if 'sip_proxy_username' in data:
            result.append(
                {
                    'key': ['voIpProt', 'SIP', 'auth', 'userId'],
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
            result.append({'key': ['voIpProt', 'H323', 'gk', 'ipAddress'], 'value': data['h323_gatekeeper']})

        return result

    def _fetch_valuespace_data_file(self):

        with open(
            os.path.join(settings.BASE_DIR, 'endpoint_data', 'temp', 'x30polycomConfig.xsd')
        ) as fd:
            return FakeResponse(fd.read())

    def get_configuration_data(
        self, force=False, fd: Optional[EndpointDataFileBase] = None, require_valuespace=False
    ) -> NestedConfigurationXMLResult:
        fd = fd or self.get_configuration_data_file(force=force)
        
        # TODO get secure settings?
        # self.post('config', {'names': [k for k,v  in attrib.items() if v == 'REMOVED_SECURE_CONTENT']})
        values = parser.PolyXConfigurationValueParser(safe_xml_fromstring(fd.content)).parse()
        config = self.get_configuration_settings(values)
        return config

    def merge_xml_json(self, xml_response, json_response):
        # xml response content form : b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<PHONE_CONFIG>\n  <ALL\n     ...   voice.volume.transmitLevel="0"\n  ></ALL>\n</PHONE_CONFIG>'
        spliter = '></ALL>\n</PHONE_CONFIG>'
        xml_content = force_text(xml_response.content).split(spliter)[0]
        json2xml_string = ''

        for key, value in json_response.items():
            json2xml_string += '{}="{}"\n     '.format(key, value)

        xml_content += json2xml_string + spliter

        return xml_content

    def _fetch_configuration_data_file(self):
        extra_config_names = [
            'management.provisioning.server',
            'management.provisioning.domain',
            'management.provisioning.enabled',
            'management.provisioning.authtype',
            'management.provisioning.user',
            'management.provisioning.password',
        ]

        config = self.get('provisioning/config')
        extra_config = self.fetch_configuration_values(extra_config_names)
        merged_config = self.merge_xml_json(config, extra_config)
        return FakeResponse(merged_config)
        # return config

    def get_configuration_settings(self, include_values=None):
        """
        List all available settings, optionally populating with values
        """
        valuespace = self.get_valuespace_data()

        return parser.PolyXConfigurationParser(
            safe_xml_fromstring(self.get_valuespace_data_file().content),
            valuespace,
            include_values,
        ).parse()

    def remove_redundant_settings(self, keys: Iterable[str]) -> List[str]:

        ignore = (
            'dns.cache.',
            'attendant.resourceList.',
            'se.pat.ringer',
            'tone.chord.ringer',
            'se.pat.misc.',
            'msg.mwi.',
        )
        ignore_re = (re.compile(r'\.([5-9]|\d\d|\d\d\d)(\.|$)'),)

        result = keys
        result = (k for k in result if not any(k.startswith(ign) for ign in ignore))
        result = (k for k in result if not any(ign.match(k) for ign in ignore_re))

        return list(result)

    def _fetch_status_data_file(self):
        config_names = [
                "system.network.wired.ipv4nic.address",
                "system.network.wireless.ipv4nic.address",
                "system.network.wired.ipv6nic.linklocal",
                "system.network.wired.ipv6nic.sitelocal",
                "system.network.wired.ipv6nic.globaladdress",
                "system.network.hostname",
                "comm.nics.h323nic.h323name",
                "comm.nics.h323nic.h323extension",
                "comm.nics.sipnic.sipusername",
                "comm.callpreference.sipdialplannormalizationstatus",
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


        activeConferences = self.get('conferences')
        connections = []
        if activeConferences.status_code == 200:
            for conference in activeConferences.json():
                enhancedConnections = ({'isMuted': conference.get('isMuted', False), **connection} for connection in conference['connections']) # Add isMuted to all the connections in one conference
                connections += list(enhancedConnections)
    
        s1 = self.fetch_configuration_values(config_names)
        s2 = self.get('system')
        s3 = self.get_device_status()
        # pwd = self.post('config', { 'names': ['sec.auth.admin.room.password'] })
        # print('===========config values===========\n', pwd.content)
        connections_dict = {}
        for index, connection in enumerate(connections):
            connections_dict['connection{}'.format(index)] = connection

        result = {
            'system': {
                **s3['CODEC'],
                **s2.json(),
            },
            'devices': s3,
            **s1,
            'connections': connections_dict
        }
        return FakeResponse(result)

    def get_device_status(self):
        response = self.post('devicemanagement/devices', {'deviceState': 'PAIRED'})
        if response.status_code != 200:
            raise self.error('Invalid status', response)

        result = {}
        dev: Dict[str, str]
        for dev in response.json():
            result.setdefault(dev['deviceType'], []).append(dev)

        return MultiValueDict(result)

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

        
        sourceman_signaltype_keys = [key for key in keys if 'sourceman' in key and 'signaltype' in key]
        # TODO get volume levels
        muted = data.get('connections.connection0.isMuted', False)
        volume = data.get('voice.volume.speaker', 100)
        inputs = []
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
        if system_status_res.status_code == 200:
            for individual_status in system_status_res.json():
                if individual_status['stateList'][0] in warning_states:
                    warnings.append('{} is {}'.format(individual_status['langtag'], individual_status['stateList'][0]))

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

    def get_status_data(
        self, force=False, fd: Optional[EndpointDataFileBase] = None
    ) -> parser.NestedXMLResult:

        fd = fd or self.get_status_data_file(force=force)

        return self.endpoint.get_parser('status', fd.content).parse()

    @staticmethod
    def load_status_xml(content: bytes):
        return json.loads(force_text(content))

    def get_basic_data(self, status_data: NestedStatusXMLResult = None) -> BasicDataDict:
        data = status_data or self.get_status_data()

        return {
            'serial_number': data['system.serialNumber'],
            'product_name': data['system.model'],
            'mac_address': self.format_mac_address(
                data.get('system.macAddress')
                or data.get('system.network.wired.ethernet.macaddress', '')
            ),
            'ip': data.get('system.ip'),
            'software_version': data['system.softwareVersion'],
            'software_release': None,
            'has_head_count': False,
            'webex_registration': self.endpoint.webex_registration,  # TODO
            'pexip_registration': self.endpoint.pexip_registration,  # TODO
            'sip_registration': data['system.state'] in ('READY', 'IN_CALL'),  
            'sip': data.get('comm.nics.sipnic.sipusername') or '',
            'sip_display_name': data.get('system.systemName', ''),
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
            'name': _get('device.local.deviceName'),
            'sip': _get(
                'voIpProt.SIP.userName',
            ),
            'sip_display_name': _get(
                'device.local.roomName',
            ),
            'h323': _get(
                'voIpProt.H323.name',
            ),
            'h323_e164': _get(
                'voIpProt.H323.e164',
            ),
            'sip_proxy': _get(
                'voIpProt.SIP.proxyServer',
            ),
            'sip_proxy_username': _get(
                'voIpProt.SIP.userName',
            ),
            'h323_gatekeeper': _get(
                'voIpProt.H323.gk.ipAddress',
            ),
        }

    def check_events_status(self, status_data: NestedStatusXMLResult = None, delay_fix=False):
        return True  # TODO

    def get_add_ca_certificates_config(self, certificate_content: str):
        result = []
        
        result.append({ 'key': ['sec', 'TLS', 'cert', 'validatePeer', 'enable'], 'value': 'True' })
        result.append({ 'key': ['sec', 'TLS', 'customCaCert', '1'], 'value': certificate_content })
        
        return result
    

    def add_ca_certificates(self, certificate_content: str):
        certificates = self.validate_ca_certificates(certificate_content)

        response = self.put('system/certificates', files={'files': force_bytes(''.join([certificate.content for certificate in certificates]))})
        if str(response.status_code).startswith('2'):
            self.save_provisioned_certificates(certificates)
            return True
        else:
            return False

    def get_set_password_config(self, password):
        result = []

        result.append({ 'key': ['sec', 'auth', 'admin', 'useRoomPassword'], 'value': '0' })
        result.append({ 'key': ['sec', 'auth', 'admin', 'password'], 'value': password })

        return result

    def set_password(self, username, password, validate_current_password: Union[bool, str] = True):
        if validate_current_password is True:
            validate_current_password = self.endpoint.password

        response = self.post('security/password/ADMIN', json={'oldPassword': validate_current_password, 'newPassword': password})
        
        content = response.json()
        if content['success']:
            self.endpoint.password = password
            if self.endpoint.pk:
                self.endpoint.save(update_fields=['password'])
            return True

        raise self.error('Password not set: {}'.format(response.decode('utf-8')))

    # def logout(self):
    #     last_session_id = self.endpoint.session_id
    #     if self.endpoint.session_id not in ('', 'basic'):
    #         self.post('/xmlapi/session/end', '')
    #     self.endpoint.session_id = DEFAULT_SESSION_ID
    #     if self.endpoint.pk and last_session_id != self.endpoint.session_id:
    #         self.endpoint.save(update_fields=['session_id'])

    def call_control(self, action: CallControlAction, argument=None):
        "abstraction for basic call control"

        if action == 'dial':
            if 'https://teams.microsoft.com' in argument:
                if self.endpoint.supports_teams:
                    # return self.adhoc_msteams_meeting(argument)
                    raise ResponseError('Teams calls are only availible for Webex registered systems')
                else:
                    raise ResponseError('Teams calls are only availible for Webex registered systems')
            return self.post('conferences', json={'address': argument, 'rate': 0, 'dialType': 'VOICE'}).text
        elif action == 'answer':
            call_type = argument or 3 # '1': Video Call, '3': Audio Call
            return self.post('conferences/callaction', json={'callActionType': 'ANSWER', 'id': call_type}).text
        elif action == 'reject':
            call_type = argument or 3 # '1': Video Call, '3': Audio Call
            return self.post('conferences/callaction', json={'callActionType': 'IGNORE', 'id': call_type}).text
        elif action == 'disconnect':
            call_reference = '0'
            call_type = argument or 3 # '1': Video Call, '3': Audio Call
            return self.post('conferences/{}/connections/{}'.format(call_reference, call_type), json={'action': 'hangup'}).text # maybe return self.post('collaboration', json={'action': 'End'})
        elif action == 'mute':
            # TODO how to identify video and audio call. To do this need another argument.
            if not argument:
                status_data = self.get_status()
                if status_data['muted']:
                    return self.post('audio/muted', data=False).text
                else:
                    return self.post('audio/muted', data=True).text
            elif argument in ('true', 'on'):
                return self.post('audio/muted', data=False).text
            else:
                return self.post('audio/muted', data=True).text
        elif action == 'volume':
            return self.post('config', json={'vars': [{'name': 'audio.volume.speakervolume', 'value': argument}]}).text
        elif action == 'reboot':
            return self.post('system/reboot', json={'action': 'reboot'}).text
        # elif action == 'presentation':
        #     source = {'PresentationSource': argument} if argument else {} # TODO
        #     return self.run_command(['Presentation', 'Start'], source)
        # elif action == 'presentation_stop':
        #     source = {'PresentationSource': argument} if argument else {} # TODO
        #     return self.run_command(['Presentation', 'Stop'], source)

        raise ValueError('Invalid action {}'.format(action))

    def get_passive_status(self, configuration_data: NestedConfigurationXMLResult = None):

        if not configuration_data:
            configuration_data = self.get_cached_configuration_data(age=10 * 60)[0]
        if not configuration_data:
            configuration_data = self.get_configuration_data()

        this_installation = False
        is_set = False

        c_settings = self.get_customer_settings()

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

        if (settings.EPM_HOSTNAME in hosts or settings.HOSTNAME in hosts) and (
            c_settings.provision_path in hosts[0] or c_settings.provision_path in hosts[1]
        ):
            this_installation = True
            is_set = True

        return {
            'is_set': is_set,
            'this_installation': this_installation,
            'url': url,
        }

    def get_call_history(self, limit=5) -> List[CallHistoryDict]:
        if not self.endpoint.has_direct_connection or not self.endpoint.check_online():
            return self.get_local_call_statistics(limit=limit)

        response = self.get('calllog/entries?limit={}'.format(limit))
        print(response.json())
        result: List[CallHistoryDict] = []

        entries = response.json()
        for entry in entries:
            cur: CallHistoryDict = {
                'number': entry['address'],
                'name': entry['name'],
                'ts_start': datetime.fromtimestamp(entry['startTime']/1000),
                'type': entry['type'],
                'protocol': entry['callType'],
                'count': entry['rowId'],  # TODO how many times are there the same calls?
                'history_id': entry['rowId'],
                'id': entry['rowId'],  # keep? same as
            }
            result.append(cur)

        return result

    def install_firmware(self, url: str = '', forced=False) -> bytes:
        response = self.post(
            'config', {'vars': [{'name': 'prov.softupdate.https.enable', 'value': True}]}
        )
        print('====1====\n', response.content)
        if str(response.status_code).startswith('2'):
            response = self.post('devicemanagement/update/available')  # TODO how to config param
            print('====2====\n', response.content)
            if str(response.status_code).startswith('2'):
                # TODO update software
                self.post('')
            else:
                raise ResponseError(response.content)
        else:
            raise ResponseError(response.content)

    def get_passive_provisioning_configuration(self) -> List[ConfigurationDict]:
        return [
            {
                'key': ['management', 'provisioning', 'enabled'],
                'value': True,
            },
            {
                'key': ['management', 'provisioining', 'authtype'],
                'value': 'Basic',
            },
            {
                'key': ['management', 'provisioining', 'server'],
                'value': 'https://poly-test.dev.mividas.com/tms/k8zk539/ffd7b2f3f2ff4b35a21a89ab5d4b6267/',
            },            
            {
                'key': ['management', 'provisioining', 'domain'],
                'value': 'k8zk5397',
            },
            {
                'key': ['management', 'provisioning', 'user'],
                'value': 'mividas'
            }
        ]
        
    def set_passive_provisioning(self, chain=False, task=None):
        if chain:
            self.set_chained_passive_provisioning()
        return self.set_configuration(self.get_passive_provisioning_configuration(), task=task)


    def run_command(
        self,
        command: List[str],
        arguments: Mapping[str, Union[str, List[str]]] = None,
        body=None,
        timeout: int = 30,
    ):
        method = arguments.get('_method', 'POST')

        if method == 'DELETE':
            request_fn = self.delete
        elif method == 'PUT':
            request_fn = self.put
        elif method == 'PATCH':
            request_fn = self.patch
        elif method == 'GET':
            request_fn = self.get
        else:
            request_fn = self.post

        response = request_fn('/'.join(command), json=body)

        if not str(response.status_code).startswith('2'):
            raise self.error('Invalid status code: {}'.format(response.status_code), response)

        return response.content


    def get_statistics_parser(self):

        from statistics.models import Server
        from statistics.parser.poly import StudioXStatisticsParser
        server = Server.objects.get_for_customer(self.endpoint.customer, type=Server.ENDPOINTS,
                                                 create=dict(name=ngettext('System', 'System', 2),
                                                             type=Server.ENDPOINTS))

        server = Server.objects.get_endpoint_server(self.customer)
        return StudioXStatisticsParser(server, self.endpoint)

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
