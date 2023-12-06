from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from threading import Thread
from time import sleep
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import ParseError

import requests
import sentry_sdk
from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.conf import settings
from django.core.cache import cache
from django.utils.encoding import force_text
from django.utils.timezone import now, utc
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from requests.exceptions import Timeout
from sentry_sdk import capture_exception, capture_message

from endpoint_provision.models import EndpointTargetState
from provider.exceptions import AuthenticationError, NotFound, ResponseError, ResponseTimeoutError
from provider.models.utils import date_format, parse_timestamp
from shared.exceptions import format_exception

from ..consts import STATUS, CallControlAction
from .base import EndpointProviderAPI
from .types.cisco_ce import (
    BasicDataDict,
    CaCertificate,
    CallHistoryDict,
    CommandDict,
    ConfigurationDict,
    DialInfoDict,
    StatusDict,
)

if TYPE_CHECKING:
    from customer.models import Customer
    from endpoint_backup.models import EndpointBackup
    from endpoint_branding.models import EndpointBrandingProfile
    from endpoint_provision.models import EndpointTask
    from roomcontrol.models import RoomControl, RoomControlTemplate

    from .parser.cisco_ce import NestedConfigurationXMLResult, NestedStatusXMLResult
    from address.models import AddressBook

DEFAULT_SESSION_ID = 'basic'

logger = logging.getLogger(__name__)


class CiscoCEProviderAPI(EndpointProviderAPI):

    _login = False

    def login(self, force=False):

        if self.endpoint.pk and self.endpoint.session_id != 'basic':
            self.endpoint.session_id = 'basic'
            self.endpoint.save(update_fields=['session_id'])

        if force:  # FIXME
            raise AuthenticationError()
        return  # FIXME

    def _real_login(self, force=False):
        if self._login or self.endpoint.session_id == 'basic':
            return

        if self.endpoint.session_id and not force:
            return

        self._login = True

        # Cookie is saved in session
        try:
            self.endpoint.session_id = ''
            response = self.get_session().post(
                self.get_url('/xmlapi/session/begin'),
                '',
                auth=(self.endpoint.username, self.endpoint.password),
            )
        except AuthenticationError:
            if self.endpoint.session_id:
                self.logout()
            self.endpoint.session_id = DEFAULT_SESSION_ID
            self.provider.set_status(status=STATUS.AUTH_ERROR)
        else:
            if response.status_code != 204:
                self.endpoint.session_id = ''
                try:
                    self.get_status()
                except AuthenticationError:
                    self.endpoint.session_id = ''
                    self.provider.set_status(status=STATUS.AUTH_ERROR)
            else:
                self.endpoint.session_id = 'basic'

                if response.cookies.get('SessionId'):
                    self.endpoint.session_id = response.cookies.get('SessionId')
                    self.session.cookies['SessionId'] = self.endpoint.session_id
                if response.cookies.get('SecureSessionId'):
                    self.endpoint.session_id = response.cookies.get('SecureSessionId')
                    self.session.cookies['SecureSessionId'] = self.endpoint.session_id

                self.endpoint.session_expires = now() + timedelta(hours=24)

        if self.endpoint.pk:
            self.endpoint.save(update_fields=['session_id', 'session_expires'])
        self._login = False
        return self.endpoint.session_id != ''

    def logout(self):
        last_session_id = self.endpoint.session_id
        if self.endpoint.session_id not in ('', 'basic'):
            self.post('/xmlapi/session/end', '')
        self.endpoint.session_id = DEFAULT_SESSION_ID
        if self.endpoint.pk and last_session_id != self.endpoint.session_id:
            self.endpoint.save(update_fields=['session_id'])

    def get_session(self, **kwargs):
        session = super().get_session(**kwargs)
        if self.endpoint.session_id not in ('', 'basic'):
            session.cookies['SessionId'] = session.cookies['SecureSessionId'] = self.endpoint.session_id
        return session

    def request(self, *args, **kwargs):

        if args and '/xmlapi/session/' not in args[0]:
            self.endpoint.maybe_try_password(do_raise=True)

        if self.endpoint.session_id == 'basic' or 1:  # TODO check models for session support?
            kwargs['auth'] = (self.provider.username, self.provider.password)

        headers = kwargs.pop('headers', {})
        headers.setdefault('Content-Type', 'application/xml')
        kwargs['headers'] = headers
        try:
            return super().request(*args, **kwargs, timeout=kwargs.pop('timeout', (3.07, 20)))
        except Timeout as e:
            raise ResponseTimeoutError(e)

    def check_login_status(self, response):

        if '/xmlapi/session/end' in response.request.url:
            return

        fail = False
        fail = fail or response.status_code == 401
        fail = fail or '/web/signin' in response.headers.get('location', '')
        fail = fail or (b'<html' in response.content[:10] and b'signin' in response.content)

        if fail:
            if self.endpoint.session_id != 'basic':
                self.endpoint.session_id = DEFAULT_SESSION_ID
                if self.endpoint.pk:
                    self.endpoint.save(update_fields=['session_id'])
            raise AuthenticationError()

    def adhoc_msteams_meeting(self, url):

        from provider.models.provider import Provider
        provider = Provider.objects.get_active('external')
        from meeting.book_handler import BookingEndpoint
        data = {
            'title': _('Adhoc Teams meeting'),
            'ts_start': date_format(now()),
            'ts_stop': date_format(now() + timedelta(minutes=2)),
            'room_info': json.dumps([{'endpoint': self.endpoint.email_key}]),
            'creator': 'test',
            'source': 'callcontrol',
            'internal_clients': 1,
            'external_clients': 1,
            'confirm': True,
            'settings': json.dumps({
                'external_uri': url,
            }),
        }
        handler = BookingEndpoint(data, self.customer, provider=provider)
        handler.book()

        response = self.run_command(['Bookings', 'List'])
        return response

    def call_control(self, action: CallControlAction, argument=None):
        "abstraction for basic call control"

        if action == 'dial':
            if 'https://teams.microsoft.com' in argument:
                if self.endpoint.supports_teams:
                    return self.adhoc_msteams_meeting(argument)
                else:
                    raise ResponseError('Teams calls are only availible for Webex registered systems')
            return self.run_command(['Dial'], {'Number': argument})
        elif action == 'answer':
            return self.run_command(['Call', 'Accept'], {})
        elif action == 'reject':
            return self.run_command(['Call', 'Reject'], {})
        elif action == 'disconnect':
            call_id = '0'
            return self.run_command(['Call', 'Disconnect'], {'CallId': call_id})
        elif action == 'mute':
            if not argument:
                return self.run_command(['Audio', 'Microphones', 'ToggleMute'], {})
            elif argument in ('true', 'on'):
                return self.run_command(['Audio', 'Microphones', 'Mute'], {})
            else:
                return self.run_command(['Audio', 'Microphones', 'Unmute'], {})
        elif action == 'volume':
            return self.run_command(['Audio', 'Volume', 'Set'], {'Level': argument})
        elif action == 'reboot':
            return self.run_command(['SystemUnit', 'Boot'], {'Action': 'Restart'})
        elif action == 'presentation':
            source = {'PresentationSource': argument} if argument else {}
            return self.run_command(['Presentation', 'Start'], source)
        elif action == 'presentation_stop':
            source = {'PresentationSource': argument} if argument else {}
            return self.run_command(['Presentation', 'Stop'], source)

        raise ValueError('Invalid action {}'.format(action))

    def _fetch_valuespace_data_file(self):
        return self.get('valuespace.xml')

    def _fetch_commands_data_file(self):
        return self.get('command.xml')

    def _fetch_status_data_file(self):
        return self.get('status.xml', timeout=45)

    def _fetch_configuration_data_file(self):
        return self.get('configuration.xml', timeout=45)

    def get_xml(self, path):
        "path example: /Status/Audio"
        response = self.get('getxml', params={'location': path})

        return response.content

    @staticmethod
    def load_status_xml(content: bytes) -> ET.Element:
        try:
            return safe_xml_fromstring(content)
        except Exception:  # defused messes with exception class
            new_content = CiscoCEProviderAPI.fix_status_xml(content)
            if content == new_content:
                raise
            return safe_xml_fromstring(new_content)

    @staticmethod
    def fix_status_xml(content: bytes):
        """
        Fix XML content. HDMI devices can send Names with invalid characters which
        makes XML invalid
        """
        new_content = content
        for name in re.findall(br'<Name>.+?</Name>', content):
            new_content = new_content.replace(name, re.sub(br'[\01\02\03\04\05]', b'?', name))
        return new_content

    def check_events_status(self, status_data: NestedStatusXMLResult = None, delay_fix=False):

        status_data = status_data or self.get_status_data()

        c_settings = self.get_customer_settings()

        paths = status_data.findtextall('./HttpFeedback/URL')
        is_set = paths and any(p for p in paths if self.endpoint.get_feedback_url() in p)

        feedback_path = './HttpFeedback[{}]'.format(c_settings.http_feedback_slot)
        if status_data.findtext(feedback_path + '/Status') == 'Failed':
            if settings.EPM_HOSTNAME in status_data.findtext(feedback_path + '/URL', ''):
                cache_key = 'endpoint.{}.enable_http_event'.format(self.endpoint.pk)
                if cache.get(cache_key):
                    return is_set
                if self.endpoint.has_direct_connection and not delay_fix:
                    self.run_command(['HttpFeedback', 'Enable'],
                                     {'FeedbackSlot': str(c_settings.http_feedback_slot)})
                else:
                    self.run_task(events=True, user='system', delay=True)
                cache.set(cache_key, True, 60 * 60)

        return is_set

    def _get_run_command_xml(
        self,
        command: Sequence[str],
        arguments: Mapping[str, Any] = None,
        body: Union[IO, str] = None,
    ):
        root = ET.Element('Command')

        command_node = root

        for path in command:
            command_node = ET.SubElement(command_node, path)

        command_node.set('command', 'True')

        if arguments is None:
            arguments = {}

        def _iter_add(kwargs, parent):
            def _iter_list(key, values, multiple=False):
                i = 0
                for v in values:
                    if v is None:  # Dont include element at all if null, <a /> == <a></a>
                        continue

                    i += 1
                    sub = ET.SubElement(parent, key)
                    if multiple:
                        sub.set('item', str(i))

                    if isinstance(v, dict):
                        _iter_add(v, sub)
                    else:
                        sub.text = str(v) if v is not None else None

            for k, v in kwargs.items():
                if isinstance(v, (list, tuple)):
                    _iter_list(k, v, multiple=True)
                else:
                    _iter_list(k, [v])

        _iter_add(arguments, command_node)

        if body:
            body_tag = ET.SubElement(command_node, 'body')
            if hasattr(body, 'read'):  # file  # type: ignore
                body_tag.text = base64.encodebytes(body.read()).decode('utf-8')
            else:
                body_tag.text = str(body)

        return root

    def run_command(
        self,
        command: List[str],
        arguments: Mapping[str, Union[str, List[str]]] = None,
        body=None,
        timeout: int = 30,
    ):

        root = self._get_run_command_xml(command, arguments or {}, body=body)

        response = self.post('/putxml', ET.tostring(root), timeout=timeout)
        if not str(response.status_code).startswith('2'):
            raise self.error('Invalid status code: {}'.format(response.status_code), response)

        try:
            self._parse_command_result(
                response.content, [{'command': command, 'arguments': arguments, body: bool(body)}]
            )
        except Exception:
            sentry_sdk.capture_exception()

        return response.content  # TODO parse?

    def run_multiple_commands(self, command_dicts: Iterable[CommandDict], timeout=30):

        root = ET.Element('Command')

        for command in command_dicts:
            cur = self._get_run_command_xml(**command)
            for node in cur:
                root.append(node)

        response = self.post('/putxml', ET.tostring(root), timeout=timeout)
        if not str(response.status_code).startswith('2'):
            raise self.error('Invalid status code: {}'.format(response.status_code), response)

        try:
            self._parse_command_result(response.content, command_dicts)
        except ResponseError:
            pass
        except Exception:
            capture_exception()

        return response.content  # TODO parse?

    def _parse_command_result(self, content: bytes, commands: List[dict]):
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

        if root.tag != 'Command' and not settings.TEST_MODE:
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
            status = cmd_result.get('status')

            if command['command'] == ['HttpFeedback', 'Deregister']:
                try:
                    status_value = {
                        'key': [
                            'HttpFeedback',
                            'HttpFeedback[{}]'.format(command['arguments']['FeedbackSlot']),
                            'URL',
                        ],
                        'value': None,
                    }
                    EndpointTargetState.apply(
                        self.endpoint,
                        'status',
                        [
                            status_value,
                        ],
                    )
                except Exception:
                    if settings.DEBUG or settings.TEST_MODE:
                        raise
                    capture_exception()

            result.append((command, status))

            try:
                ignore_error = cmd_result.find('./Reason').text == 'Certificate already exists'
            except (AttributeError, TypeError):
                ignore_error = False

            if 'Error' in status and not ignore_error:
                _log_error(
                    'Command %s failed for endpoint %s, software %s',
                    ' '.join(command['command']),
                    self.endpoint.pk,
                    self.endpoint.status.software_version,
                )

        if b'"Error"' not in content:
            logger.info(
                'Successfully executed commands for endpoint %s, software %s: %s',
                self.endpoint.pk,
                self.endpoint.status.software_version,
                all_commands,
            )

        return result

    def _get_configuration_xml(self, settings: Iterable[ConfigurationDict]):

        nodes = {}

        root = ET.Element("Configuration")

        for config in settings:

            if config.get('value') is None:  # Dont include element at all if null, <a /> == <a></a>
                continue

            parent = root

            for i, path in enumerate(config['key']):
                cur_key = tuple(config['key'][:i + 1])
                if cur_key not in nodes:
                    index = 1
                    if '[' in path:
                        path, index = path.split('[', 1)
                        index = index.replace('@item=', '').strip('[]"\'')

                    parent = ET.SubElement(parent, path, {'item': str(index)})

                    nodes[cur_key] = parent
                else:
                    parent = nodes[cur_key]

            if config.get('value') is not None:
                parent.text = str(config['value'])

        return root

    def set_configuration(self, config: List[ConfigurationDict], task=None):

        if getattr(self, '_configuration_buffer', None) is not None:
            self._configuration_buffer.extend(config)
            return

        root = self._get_configuration_xml(config)

        if not task:
            task, result = self.run_task('configuration', configuration=config)
            return result

        logger.debug(
            'Setting configuration on endpoint %s (%s): %s',
            self.endpoint.id,
            self.endpoint,
            json.dumps(config),
        )
        self.active_task = task
        try:
            response = self.post('/putxml', ET.tostring(root))
        except Exception as e:
            task.add_error(e)
            raise
        else:
            self._handle_configuration_response(config, response.text, task)
        finally:
            self.active_task = None

        return response.text  # TODO .content

    def _handle_configuration_response(
        self, config: List[ConfigurationDict], text: str, task: 'EndpointTask'
    ):
        def _warn(msg: str, *args):
            logger.warning(msg + ', request: "%s" response: "%s"', *args, json.dumps(config), text)
            from debuglog.models import ErrorLog

            ErrorLog.objects.store(
                'request: {}\nresponse:{}'.format(json.dumps(config), text),
                customer=self.customer,
                endpoint=self.endpoint,
                title=msg % args,
                type='endpoint',
            )

        if not text.startswith('<?xml'):
            _warn(
                'Invalid response for configuration for endpoint %s, software %s',
                self.endpoint.id,
                self.endpoint.status.software_version,
            )
            task.fail('Invalid response: {}'.format(text))
            return text

        root = safe_xml_fromstring(text.encode('utf-8'))
        errors = root.findall('./Error')
        error_content = [ET.tostring(e, encoding='unicode') for e in errors]

        if errors:
            _warn(
                'Errors when setting configuration for endpoint %s, software %s',
                self.endpoint.id,
                self.endpoint.status.software_version,
            )
        else:
            logger.info(
                'Configuration set for endpoint %s, software %s',
                self.endpoint.id,
                self.endpoint.status.software_version,
            )

            try:
                values = [{'key': c['key'], 'value': c['value']} for c in config]
                EndpointTargetState.apply(self.endpoint, 'configuration', values)
            except Exception:
                if settings.DEBUG or settings.TEST_MODE:
                    raise
                capture_exception()

        if errors and len(root) == len(errors):  # only errors
            return task.fail('\n'.join(error_content))
        elif errors:
            task.add_error('\n'.join(error_content))
        task.complete(text)

    def get_status(self, data: NestedStatusXMLResult = None) -> StatusDict:  # noqa: CCR001
        # TODO noqa: split into service class

        data = data or self.get_status_data()

        uptime = int(data.findtext('./SystemUnit/Uptime') or 0)

        status = STATUS.ONLINE

        if data.findtext('./Call/Status') == 'Connected':
            status = STATUS.IN_CALL

        call_participant = data.findtext('./Call/RemoteNumber') or data.findtext('./Call/CallbackNumber')
        answer_state = data.findtext('./Call/AnswerState')
        direction = data.findtext('./Call/Direction')

        upgrade_status = data.findtext('./Provisioning/Software/UpgradeStatus/Status')
        if upgrade_status and upgrade_status != 'None':
            upgrade = {
                'status': upgrade_status,
                'message': data.findtext('./Provisioning/Software/UpgradeStatus/Message')
            }
        else:
            upgrade = {}

        inputs = []
        for connector in data.textdictall('./Video/Input/Connector'):
            if connector.get('Type') in ('Camera', None):
                continue
            inputs.append({
                'label': '{} {}'.format(connector.get('Type'), connector.get('SourceId')),
                'id': connector.get('SourceId'),
            })

        presentation = []
        for inst in data.textdictall('./Conference/Presentation/LocalInstance'):
            if inst.get('SendingMode') in ('Off', None):
                continue
            presentation.append({
                'mode': inst.get('SendingMode'),
                'id': inst.get('Source'),
            })

        warnings = []
        diagnostics = []

        messages = data.textdictall('./Diagnostics/Message')
        if messages:
            try:
                warnings = [m['Description'] for m in messages if m.get('Description') and m.get('Level') != 'Info']
                diagnostics = [m for m in messages if m.get('Description')]
            except Exception:
                sentry_sdk.capture_exception()

        mac = data.findtext('./Network/Ethernet/MacAddress', '')
        if self.endpoint.mac_address and mac and self.endpoint.mac_address != mac.upper():
            warnings.append(
                _(
                    'MAC-adressen matchar inte värdet i Rooms. Redigera och nollställ MAC-adressfältet om systemet bytts ut'
                ),
            )

        if self.endpoint.status.software_version.lower().startswith('tc7'):
            diagnostics.append({'Description': _('Mividas Rooms har begränsat stöd för TC7. Vänligen uppgradera till en senare version'), 'Level': 'Info'})

        feedback_url = self.endpoint.get_feedback_url()
        if not any(url == feedback_url for url in data.findtextall('./HttpFeedback/URL')):
            cur = {
                'Description': _('Systemet har inte live-events registrerade'),
                'Level': 'Warning' if self.endpoint.ts_feedback_events_set else 'Info',
            }
            diagnostics.append(cur)
            warnings.append(cur['Description'])

        try:
            volume = int(data.findtext('./Audio/Volume') or 0)
        except ValueError:
            volume = None

        from room_analytics.parse import parse_cisco_ce

        sensor_data = parse_cisco_ce(data)

        return {
            'has_direct_connection': self.endpoint.has_direct_connection,
            'uptime': uptime,
            'status': status,
            **sensor_data,
            'incoming': call_participant
            if answer_state == 'Unanswered' and direction == 'Incoming'
            else '',
            'in_call': call_participant
            if answer_state in ('Answered', 'Autoanswered') or direction == 'Outgoing'
            else '',
            'muted': data.findtext('./Audio/Microphones/Mute', 'Off') == 'On',
            'volume': volume,
            'inputs': inputs,
            'presentation': presentation,
            'call_duration': int(data.findtext('./Call/Duration') or 0),
            'upgrade': upgrade,
            'warnings': warnings,
            'diagnostics': diagnostics,
        }

    def backup_extended_data(self, backup: EndpointBackup):

        try:
            response = self.run_command(["UserInterface", "Extensions", "List"], {})
            backup.set_data('panels', response)
        except ResponseError:
            pass

        try:
            response = self.run_command(["Macros", "Macro", "Get"], {'Content': 'True'})
            backup.set_data('macros', response)
        except ResponseError:
            pass

    def restore_backup(self, backup: EndpointBackup):

        parsed = self.endpoint.get_parser('configuration', backup.file.read()).parse()
        config = [{'key': k, 'value': c[0].item.value} for k, c in parsed.all_keys.items()]

        return self.set_configuration(config)

    def get_basic_data(self, status_data: NestedStatusXMLResult = None) -> BasicDataDict:
        from django.utils.dateparse import parse_date

        data = status_data or self.get_status_data()

        serial = data.findtext('./SystemUnit/Hardware/Module/SerialNumber', '')
        mac = data.findtext('./Network/Ethernet/MacAddress', '')
        ip = data.findtext('./Network/IPv4/Address', '') or data.findtext('./Network/IPv6/Address', '') or ''
        product_name = data.findtext('./SystemUnit/ProductId', '')
        software_version = data.findtext('./SystemUnit/Software/Version', '')
        software_release = data.findtext('./SystemUnit/Software/ReleaseDate', '')
        has_head_count = data.find('./RoomAnalytics/PeopleCount/Current') is not None
        webex_registration = data.findtext('./Webex/Status', '') == 'Registered'

        sip_registration = data.findtext('./SIP/Registration/Status') == 'Registered'
        if webex_registration:
            sip_registration = True

        sip = data.findtext('./UserInterface/ContactInfo/ContactMethod/Number', '')
        sip_display_name = data.findtext('./UserInterface/ContactInfo/Name', '')

        return {
            'serial_number': serial,
            'product_name': product_name,
            'mac_address': mac,
            'ip': ip,
            'software_version': software_version,
            'software_release': parse_date(software_release) if software_release else None,
            'has_head_count': has_head_count,
            'webex_registration': webex_registration,
            'pexip_registration': self.endpoint.pexip_registration,  # not readable in status_data
            'sip_registration': sip_registration,
            'sip': sip,
            'sip_display_name': sip_display_name,
        }

    def get_dial_info(
        self, configuration_data: NestedConfigurationXMLResult = None
    ) -> DialInfoDict:

        configuration = configuration_data or self.get_configuration_data(require_valuespace=False)

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
            'name': _get('./SystemUnit/Name'),
            'sip': _get(
                './SIP/URI',
                './SIP/Registration/URI',
                './SIP/Profile/URI',
                './UserInterface/ContactInfo/ContactMethod/Number',
            ),
            'sip_display_name': _get(
                './SIP/DisplayName',
                './UserInterface/ContactInfo/Name',
                './SystemUnit/ContactName',
                './SystemUnit/Name',
            ),
            'h323': _get('./H323/H323Alias/ID', './H323/Profile/H323Alias/ID'),
            'h323_e164': _get('./H323/H323Alias/E164', './H323/Profile/H323Alias/E164'),
            'sip_proxy': _get('./SIP/Proxy/Address', './SIP/Profile/Proxy/Address'),
            'sip_proxy_username': _get(
                './SIP/Authentication/UserName', './SIP/Authentication/LoginName'
            ),
            'h323_gatekeeper': _get(
                './H323/Gatekeeper/Address', './H323/Profile/Gatekeeper/Address'
            ),
        }

    @classmethod
    def get_update_dial_info_configuration(
        cls, data: DialInfoDict, customer: Customer = None, versions: Set[str] = None
    ) -> List[ConfigurationDict]:

        has_ce = not versions or any(v for v in versions if v.lower().startswith('ce'))
        has_tc = not versions or any(v for v in versions if v.lower().startswith('tc'))

        if not has_ce and not has_tc:
            has_ce = has_tc = True

        result = []

        def _add_ce(conf) -> None:
            has_ce and result.append(conf)

        def _add_tc(conf) -> None:
            has_tc and result.append(conf)

        if 'name' in data:
            result.append({'key': 'SystemUnit/Name'.split('/'), 'value': data['name']})

        if 'sip_uri' in data and 'sip' not in data:
            data['sip'] = data.pop('sip_uri')

        if 'sip' in data:
            _add_ce({'key': 'SIP/URI'.split('/'), 'value': data['sip']})
            _add_tc({'key': 'SIP/Profile/URI'.split('/'), 'value': data['sip']})

        if 'sip_display_name' in data:
            _add_ce({'key': 'SIP/DisplayName'.split('/'), 'value': data['sip_display_name']})
            _add_tc(
                {
                    'key': 'UserInterface/ContactInfo/Name'.split('/'),
                    'value': data['sip_display_name'],
                }
            )
            _add_tc({'key': 'SystemUnit/ContactName'.split('/'), 'value': data['sip_display_name']})

        if 'h323' in data:
            _add_ce({'key': 'H323/H323Alias/ID'.split('/'), 'value': data['h323']})
            _add_tc({'key': 'H323/Profile[1]/H323Alias/ID'.split('/'), 'value': data['h323']})

        if 'h323_e164' in data:
            _add_ce({'key': 'H323/H323Alias/E164'.split('/'), 'value': data['h323_e164']})
            _add_tc(
                {'key': 'H323/Profile[1]/H323Alias/E164'.split('/'), 'value': data['h323_e164']}
            )

        if 'sip_proxy' in data:
            _add_ce({'key': 'SIP/Proxy/Address'.split('/'), 'value': data['sip_proxy']})
            _add_tc({'key': 'SIP/Profile/Proxy[1]/Address'.split('/'), 'value': data['sip_proxy']})

        if 'sip_proxy_username' in data:
            _add_ce(
                {
                    'key': 'SIP/Authentication/UserName'.split('/'),
                    'value': data['sip_proxy_username'],
                }
            )
            _add_tc(
                {
                    'key': 'SIP/Profile/Authentication/LoginName'.split('/'),
                    'value': data['sip_proxy_username'],
                }
            )

        sip_proxy_password = cls._get_sip_proxy_password(
            data.get('sip_proxy_password'), customer, data
        )

        if sip_proxy_password is not None:
            _add_ce(
                {
                    'key': 'SIP/Authentication/Password'.split('/'),
                    'value': sip_proxy_password,
                }
            )
            _add_tc(
                {
                    'key': 'SIP/Profile/Authentication/Password'.split('/'),
                    'value': sip_proxy_password,
                }
            )

        if 'h323_gatekeeper' in data:
            _add_ce({'key': 'H323/Gatekeeper/Address'.split('/'), 'value': data['h323_gatekeeper']})
            _add_tc(
                {
                    'key': 'H323/Profile[1]/Gatekeeper/Address'.split('/'),
                    'value': data['h323_gatekeeper'],
                }
            )

        return result

    def get_addressbook_status(self, configuration_data: NestedConfigurationXMLResult = None):

        configuration_data = configuration_data or self.get_configuration_data()

        address_book = None

        cur_url = configuration_data.findtext('Phonebook/Server/URL')
        if cur_url:
            from address.models import AddressBook

            secret_key = cur_url.strip('/').rsplit('/', 1)[-1]
            address_book = AddressBook.objects.filter(
                customer=self.customer, secret_key=secret_key
            ).first()

        return {
            'is_set': bool(cur_url),
            'id': address_book.pk if address_book else None,
        }

    def get_macro_status(self, configuration_data: NestedConfigurationXMLResult = None) -> bool:

        configuration_data = configuration_data or self.get_configuration_data()

        return configuration_data.findtext('./Macros/Mode') == 'On'

    def get_support_macros(self) -> bool:
        return not self.endpoint.status.software_version.lower().startswith('tc')

    def get_passive_status(self, configuration_data: NestedConfigurationXMLResult = None):

        if not configuration_data:
            configuration_data = self.get_cached_configuration_data(age=10 * 60)[0]
        if not configuration_data:
            configuration_data = self.get_configuration_data()

        path = configuration_data.findtext('Provisioning/ExternalManager/Path')
        this_installation = False

        c_settings = self.get_customer_settings()

        hosts = [
            configuration_data.findtext('Provisioning/ExternalManager/Address'),
            configuration_data.findtext('Provisioning/ExternalManager/Domain'),
        ]

        protocol = configuration_data.findtext('Provisioning/ExternalManager/Protocol')

        if path and any(hosts):
            host = [h for h in hosts if h][0]
            url = '{}://{}{}'.format(protocol.lower(), host, path)
        else:
            url = None

        if (settings.EPM_HOSTNAME in hosts or settings.HOSTNAME in hosts) and path.startswith(
            c_settings.provision_path
        ):
            this_installation = True

        return {
            'is_set': bool(path),
            'this_installation': this_installation,
            'url': url,
        }

    def get_analytics_status(self, configuration_data: NestedConfigurationXMLResult = None):

        configuration_data = configuration_data or self.get_configuration_data()

        def _bool(s):
            if s is None:
                return None
            return s == 'True'

        return {
            'head_count': _bool(
                configuration_data.findtext('RoomAnalytics/PeopleCountOutOfCall', None)
            ),
            'presence': _bool(
                configuration_data.findtext('RoomAnalytics/PeoplePresenceDetector', None)
            ),
        }

    def get_room_analytics_configuration(
        self,
        head_count: Optional[bool] = True,
        presence: Optional[bool] = True,
        detect_support=True,
    ) -> List[ConfigurationDict]:
        if detect_support:
            configuration_data = self.get_cached_configuration_data_file(age=None)
            if configuration_data and b'PeopleCountOutOfCall' not in configuration_data.content:
                head_count = None
            if configuration_data and b'PeoplePresenceDetector' not in configuration_data.content:
                presence = None

        configuration = []
        if head_count is not None:
            configuration.append(
                {
                    "key": ["RoomAnalytics", "PeopleCountOutOfCall"],
                    "value": "On" if head_count else 'Off',
                }
            )
        if presence is not None:
            configuration.append(
                {
                    "key": ["RoomAnalytics", "PeoplePresenceDetector"],
                    "value": "On" if presence else 'Off',
                }
            )

        return configuration

    def get_call_history(self, limit=3) -> List[CallHistoryDict]:
        if not self.endpoint.has_direct_connection or not self.endpoint.check_online():
            return self.get_local_call_statistics(limit=limit)

        response = self.run_command(["CallHistory", "Recents"],
                                {"DetailLevel": "Basic", "Filter": "All", "Limit": str(limit), "Offset": "0",
                                 "Order": "OccurrenceTime", "SearchString": ''})

        root = safe_xml_fromstring(response)

        def _findtexts(node: ET.Element, *keys: str) -> str:
            for k in keys:
                result = node.findtext(k) or ''
                if result:
                    return result
            return ''

        result: List[CallHistoryDict] = []
        for entry in root.findall('.//Entry'):
            cur: CallHistoryDict = {
                'number': entry.findtext('./CallbackNumber', ''),
                'name': entry.findtext('./DisplayName', ''),
                'ts_start': _findtexts(
                    entry, './LastOccurrenceStartTime', './StartTime', 'LastOccurrenceStartTimeUTC'
                ),
                'type': entry.findtext('./OccurrenceType', ''),
                'protocol': entry.findtext('./Protocol', ''),
                'count': int(entry.findtext('./OccurrenceCount', '1')),
                'history_id': _findtexts(entry, './LastOccurrenceHistoryId', './HistoryId'),
                'id': _findtexts(
                    entry, './LastOccurrenceHistoryId', './HistoryId'
                ),  # keep? same as
            }
            result.append(cur)

        return result

    def get_call_history_data(self, call_history_id):
        entries = self.get_full_call_data(call_history_id=call_history_id)
        return entries[0]

    def get_full_call_data(self, call_history_id=None, limit=3, offset=0):

        arguments = {"DetailLevel": "Full", "Filter": "All", "Limit": str(limit), "Offset": str(offset),
                                     "SearchString": ''}
        if call_history_id is not None:
            arguments['CallHistoryId'] = str(call_history_id)

        response = self.run_command(["CallHistory", "Get"], arguments)

        root = safe_xml_fromstring(response)

        entries = root.findall('.//Entry')
        if call_history_id is not None and not entries:
            raise NotFound('History ID not found', response)
        return entries

    def update_statistics(self, limit=1000):
        # Is update_statistics_single ever needed? TC7.x?
        return self.update_statistics_paginated(limit=limit)

    def update_statistics_paginated(self, limit=1000):

        per_page = 100

        parser = self.get_statistics_parser()
        error = None

        entries = []
        for i in range(10):
            try:
                cur_entries = self.get_full_call_data(
                    limit=min(per_page, limit - len(entries)), offset=i * per_page
                )
            except (ResponseError, NotFound) as e:
                if not entries:
                    return self.update_statistics_single(limit=limit)
                else:
                    error = e
                    break
            else:
                entries.extend(cur_entries)
                if len(cur_entries) < per_page or len(entries) < limit:
                    break

        result = []
        for entry in entries:
            call = parser.parse_call(entry)
            result.append(call)

        if error:
            raise error

        return result

    def update_statistics_single(self, limit=3):
        parser = self.get_statistics_parser()

        result = []
        for call in self.get_call_history(limit=limit):
            if not call.get('history_id') or call['history_id'] == '0':
                continue
            full_data = self.get_call_history_data(call['history_id'])
            cur = parser.parse_call(full_data)
            result.append(cur)
        return result

    def get_statistics_parser(self):

        from statistics.models import Server
        from statistics.parser.cisco_ce import CiscoCEStatisticsParser
        server = Server.objects.get_for_customer(self.endpoint.customer, type=Server.ENDPOINTS,
                                                 create=dict(name=ngettext('System', 'System', 2),
                                                             type=Server.ENDPOINTS))

        server = Server.objects.get_endpoint_server(self.customer)
        return CiscoCEStatisticsParser(server, self.endpoint)

    def get_statistics_event_parser(self):

        from statistics.models import Server
        from statistics.parser.cisco_ce import CiscoCEStatisticsEventParser
        server = Server.objects.get_for_customer(self.endpoint.customer, type=Server.ENDPOINTS,
                                                 create=dict(name=ngettext('System', 'System', 2),
                                                             type=Server.ENDPOINTS))

        server = Server.objects.get_endpoint_server(self.customer)
        return CiscoCEStatisticsEventParser(server, self.endpoint)

    def get_update_branding_commands(self, branding_profile: EndpointBrandingProfile):
        result = [
            {
                'command': ['UserInterface', 'Branding', 'Clear'],
                'arguments': {},
            }
        ]

        for f in branding_profile.files.all():
            if not f.file:
                continue

            f_type = f.get_type_display()
            if f_type.startswith('CAMERA'):
                name = 'User{}'.format(f_type[-1])
                result.append({
                    'command': ['Cameras', 'Background', 'Upload'],
                    'arguments': {'Image': name},
                    'body': f.file.open(),
                })
                result.append({
                    'command': ['Cameras', 'Background', 'Set'],
                    'arguments': {'Image': name},
                })
            else:
                result.append({
                    'command': ['UserInterface', 'Branding', 'Upload'],
                    'arguments': {'Type': f.get_type_display()},
                    'body': f.file.open(),
                })

        return result

    def update_branding(self, branding_profile: EndpointBrandingProfile):

        result = [
            self.run_multiple_commands(
                self.get_update_branding_commands(branding_profile), timeout=180
            )
        ]
        self.save_provisioned_object(
            'branding', {'id': branding_profile.pk, 'title': str(branding_profile)}, replace=True
        )
        return result

    def set_bookings(self, bookings):

        c_settings = self.get_customer_settings()
        if not c_settings.enable_obtp or not settings.EPM_ENABLE_OBTP:
            return None  # TODO exception?
        if self.endpoint.software_version_tuple >= (9, 14) and self.endpoint.webex_registration:
            return self.set_bookings_json(bookings)
        return self.set_bookings_xml(bookings)

    def set_bookings_json(self, bookings):
        from debuglog.models import EndpointCiscoProvision

        if not self.endpoint.webex_registration:
            raise ValueError('Bookings Put is only available to Webex registrered devices')

        json_data = {'Bookings': self._get_bookings_json(bookings)}
        try:
            response = self.run_command(['Bookings', 'Put'], body=json.dumps(json_data))
            EndpointCiscoProvision.objects.store(
                json.dumps(json_data), endpoint=self.endpoint, event='bookings'
            )
            return response
        except ResponseError as e:
            EndpointCiscoProvision.objects.store(
                'Set bookings failed: {}'.format(format_exception(e)),
                endpoint=self.endpoint,
                event='bookings',
            )
            raise self.error('Invalid status for booknings', e)

    def set_bookings_xml(self, bookings):

        from debuglog.models import EndpointCiscoProvision

        xmldata = self._get_bookings_xml(bookings)
        response = self.post('bookingsputxml', xmldata.encode('utf-8'), headers={'Content-Type': 'text/plain'})
        if response.status_code != 200:
            EndpointCiscoProvision.objects.store('Set bookings failed: HTTP {}. {}'.format(response.status_code, response.content),
                                                 endpoint=self.endpoint, event='bookings')
            raise self.error('Invalid status for booknings', response)
        EndpointCiscoProvision.objects.store(xmldata, endpoint=self.endpoint, event='bookings')

        return response

    def _get_bookings_xml(self, bookings: Iterable[Mapping[str, Any]]):

        bookings = '\n'.join(
            self._get_booking_putxml_content(b, index=i)
            for i, b in enumerate(bookings)
            if b.get('sip_uri') and 'https://' not in b['sip_uri']
        )

        return '''
        <?xml version='1.0'?>
        <Bookings item="1" status="OK">
            {bookings}
        </Bookings>
        '''.strip().format(bookings=bookings)

    def _get_booking_putxml_content(self, booking: Mapping[str, Any], index=0) -> str:
        def _iter(parent: ET.Element, dct: Dict[str, str]):
            for k, v in dct.items():
                sub = ET.SubElement(parent, k, attrib={'item': '1'})
                if isinstance(v, dict):
                    _iter(sub, v)
                else:
                    sub.text = str(v)

        root = ET.Element('Booking', attrib={'item': str(index + 1)})
        _iter(root, self.serialize_booking(booking))
        return ET.tostring(root, 'unicode')

    def _get_bookings_json(self, bookings: Iterable[Mapping[str, Any]]):
        result = []
        for booking in bookings:
            if 'https://' in booking['sip_uri'] and not self.endpoint.supports_teams:
                continue

            cur = self.serialize_booking(booking)
            cur['Number'] = cur['DialInfo']['Calls']['Call']['Number']
            cur['Protocol'] = cur['DialInfo']['Calls']['Call']['Protocol']
            cur.pop('DialInfo')
            result.append(cur)
        return result

    StrDict = Union[str, Dict[str, Union[str, Dict[str, Dict[str, Union[str, Dict[str, str]]]]]]]

    def serialize_booking(self, data: Mapping[str, Any]) -> Dict[str, StrDict]:
        def _parse(s: Union[str, datetime]):
            return parse_timestamp(s) if isinstance(s, str) else s

        def _timestamp(s: Union[str, datetime]):
            return '%sZ' % _parse(s).astimezone(utc).strftime('%Y-%m-%dT%H:%M:%S')

        c_settings = self.get_customer_settings()
        protocol = self.endpoint.dial_protocol or c_settings.dial_protocol
        if 'https://' in data['sip_uri']:
            protocol = 'WebRTC'

        is_teams = 'https://teams.microsoft.com' in data['sip_uri']

        return {
            'Id': str(data['id']),
            'Title': data['title'],
            'Agenda': '',
            'Privacy': 'Private' if data.get('is_private') else 'Public',
            'Organizer': {
                'Name': '',  # json
                'FirstName': '',  # xml
                'LastName': '',
                'Email': '',
            },
            'Time': {
                'StartTime': _timestamp(data['ts_start']),
                'StartTimeBuffer': c_settings.booking_time_before * 60,
                'EndTime': _timestamp(data['ts_stop']),  # xml
                'EndTimeBuffer': 0,
                'Duration': (_parse(data['ts_stop']) - _parse(data['ts_start'])).total_seconds()
                // 60,  # json
            },
            'MaximumMeetingExtension': 5,
            'BookingStatus': 'OK',
            'BookingStatusMessage': '',
            **(
                {
                    'MeetingPlatform': 'MicrosoftTeams',
                }
                if is_teams
                else {}
            ),
            'Encryption': 'BestEffort',
            'Role': 'Master',
            'Recording': 'Disabled',
            'DialInfo': {
                'Calls': {
                    'Call': {
                        'Number': data['sip_uri'].replace('sip:', ''),
                        **(
                            {
                                'Protocol': protocol,
                                'CallRate': '6000',
                                'CallType': 'Video',
                            }
                            if protocol
                            else {}
                        ),
                    }
                },
                'ConnectMode': 'OBTP',
            },
            'Spark': {
                'MeetingType': 'Scheduled',
            },
            'Webex': {
                'Enabled': False,
            },
        }

    def get_external_passive_request(self):
        return '''
<?xml version="1.0" encoding="utf-8"?>
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"
              xmlns="http://www.tandberg.net/2004/11/SystemManagementService/">
  <env:Body xmlns="http://www.tandberg.net/2004/11/SystemManagementService/">
    <PostEvent>
      <Identification>
        <SystemName>{name}</SystemName>
        <MACAddress>{mac}</MACAddress>
        <IPAddress>{ip}</IPAddress>
        <ProductType>TANDBERG Codec</ProductType>
        <ProductID>Cisco Codec</ProductID>
        <SWVersion>{software}</SWVersion>
        <HWBoard></HWBoard>
        <SerialNumber>{serial}</SerialNumber>
      </Identification>
    <Event>Beat</Event>
  </PostEvent></env:Body>
</env:Envelope>
        '''.strip().format(
            name=self.endpoint.title,
            mac=self.endpoint.mac_address.upper(),
            ip=self.endpoint.ip,
            software=self.endpoint.status.software_version or '',
            serial=self.endpoint.serial_number or '',
        )

    def get_external_passive_response(
        self, force=False, remote_ip: str = None
    ) -> Optional[ET.Element]:
        if self.endpoint.mac_address:
            cache_key = 'external_provision.mac.{}'.format(self.endpoint.mac_address)
        else:
            cache_key = 'external_provision.id.{}'.format(self.endpoint.id)

        cached = cache.get(cache_key)
        if cached is not None and not force:
            return safe_xml_fromstring(cached)

        if not self.endpoint.get_external_manager_url():
            return

        if 'CE' in self.endpoint.status.software_version.upper():
            user_agent = 'Cisco/CE'
        else:
            user_agent = ''

        response = requests.post(
            self.endpoint.get_external_manager_url(),
            self.get_external_passive_request().encode('utf-8'),
            headers={
                'Content-Type': 'text/xml; charset=utf-8',
                'User-Agent': user_agent,
                'X-Chained-ExternalManager': settings.EPM_HOSTNAME,
                'X-Chained-ExternalManager-Type': 'Mividas Rooms {}'.format(settings.VERSION),
                'X-Forwarded-For': remote_ip or self.endpoint.ip,
            },
            timeout=5,
        )

        if response.status_code != 200:
            cache.set(cache_key, [], 2)
            raise self.error(
                'Invalid response status from chained external manager: {}'.format(
                    response.status_code
                ),
                response,
            )

        content = response.content.replace(b'http://www.tandberg.no/XML/CUIL/1.0', b'')
        content = content.replace(b'http://www.tandberg.com/XML/CUIL/2.0', b'')

        try:
            root = safe_xml_fromstring(content)
        except ParseError:
            cache.set(cache_key, [], 2)
            raise self.error('Invalid response status from chained external manager', response)

        cache.set(cache_key, content, 10)
        return root

    def get_external_calendar_items(
        self, passive_response_root: Optional[ET.Element] = None, force=False
    ) -> List[ET.Element]:

        # TODO parse calendar items to be able to use in active mode as well

        if passive_response_root is None:
            passive_response_root = self.get_external_passive_response(force=force)

        if not passive_response_root:
            return []

        return passive_response_root.findall(
            './/ns:Bookings/ns:Booking',
            namespaces={
                'ns': 'http://www.cisco.com/TelePresence/Bookings/1.0',
            },
        )

    def get_external_configuration(
        self, passive_response_root: Optional[ET.Element] = None, force=False, filter=True
    ) -> List[ET.Element]:
        # TODO filter out e.g. ExternalManger settings etc so that this server is not removed

        if passive_response_root is None:
            passive_response_root = self.get_external_passive_response(force=force)

        # ns:Configuration/x:Configuration can be of different namespaces
        configurations = passive_response_root.findall(
            './/ns:Management/ns:Configuration/*',
            namespaces={
                'ns': 'http://www.tandberg.net/2004/11/SystemManagementService/',
            },
        )

        nodes = []
        for container in configurations:

            for node in list(container):
                if node.tag.split('}', 1)[-1] == 'Provisioning':
                    continue
                nodes.append(node)

        return nodes

    def get_external_commands(
        self, passive_response_root: Optional[ET.Element] = None, force=False
    ) -> List[ET.Element]:
        # TODO filter out e.g. HttpFeedback if the same slot is used as this server

        if passive_response_root is None:
            passive_response_root = self.get_external_passive_response(force=force)

        containers = passive_response_root.findall(
            './/ns:Management/ns:Command/*',
            namespaces={
                'ns': 'http://www.tandberg.net/2004/11/SystemManagementService/',
            },
        )

        nodes = []
        # nested loops to allow different namespaces
        for container in containers:
            nodes.extend(list(container))

        return nodes

    def get_feedback_events(self):

        return [
            '/Status/Call/Status',
            '/Status/Network/IPv4/Address',
            '/Status/SystemUnit/Software/Version',
            '/Status/RoomAnalytics/PeopleCount/Current',
            '/Status/RoomAnalytics/PeoplePresence',
            '/Status/Peripherals/ConnectedDevice/RoomAnalytics',
            '/Conference/Presentation/LocalInstance/SendingMode',
            '/Event/SoftwareUpgrade',
            '/Event/BootEvent',
            '/Event/Standby/Reset',
            '/Event/CallSuccessful',
            '/Event/CallDisconnect',
            '/Event/OutgoingCallIndication',
            '/Event/IncomingCallIndication',
        ]

    def get_update_events_command(self, mutate_state=True):

        c_settings = self.get_customer_settings()
        if mutate_state:
            try:
                status_data = {
                    'key': [
                        'HttpFeedback',
                        'HttpFeedback[{}]'.format(c_settings.http_feedback_slot),
                        'URL',
                    ],
                    'value': self.endpoint.get_feedback_url(),
                }
                EndpointTargetState.apply(self.endpoint, 'status', [status_data])
            except Exception:
                if settings.DEBUG or settings.TEST_MODE:
                    raise
                capture_exception()

        return {
            'command': ['HttpFeedback', 'Register'],
            'arguments': {
                'Expression': self.get_feedback_events(),
                'FeedbackSlot': str(c_settings.http_feedback_slot),
                'ServerUrl': self.endpoint.get_feedback_url(),
                **(
                    {'Format': 'XML'}
                    if not self.endpoint.status.software_version.lower().startswith('tc7')
                    else {}
                ),
            },
        }

    def set_events(self):
        try:
            result = self.run_command(**self.get_update_events_command())
        except Exception:
            raise
        else:
            self.endpoint.ts_feedback_events_set = now()
            self.endpoint.save(update_fields=['ts_feedback_events_set'])
        return result

    def get_passive_provisioning_configuration(self) -> List[ConfigurationDict]:
        return [
            {
                'key': ['Provisioning', 'Mode'],
                'value': 'TMS',
            },
            {
                'key': ['Provisioning', 'ExternalManager', 'Address'],
                'value': settings.EPM_HOSTNAME,
            },
            {
                'key': ['Provisioning', 'ExternalManager', 'Path'],
                'value': self.endpoint.get_provision_path(),
            },            {
                'key': ['Provisioning', 'ExternalManager', 'Protocol'],
                'value': 'HTTPS',
            },
        ]

    def set_passive_provisioning(self, chain=False, task=None):
        if chain:
            self.set_chained_passive_provisioning()
        return self.set_configuration(self.get_passive_provisioning_configuration(), task=task)

    def get_room_controls_feature_configuration(
        self,
        controls: Iterable[RoomControl] = None,
        templates: Iterable[RoomControlTemplate] = None,
        clear=False,
    ) -> List[ConfigurationDict]:

        controls = list(controls)[:] if controls else []
        if templates:
            from roomcontrol.models import RoomControl
            controls.extend(c for c in RoomControl.objects.filter(templates__in=templates))

        return [config for control in controls for config in control.get_feature_configuration(clear=clear)]

    def set_room_controls_features(
        self,
        controls: Iterable[RoomControl] = None,
        templates: Iterable[RoomControlTemplate] = None,
        clear=False,
        task: EndpointTask = None,
    ):
        config = self.get_room_controls_feature_configuration(
            controls=controls, templates=templates, clear=clear
        )
        if not config:
            return ''
        return self.set_configuration(config, task=task)

    def get_room_controls_commands(
        self,
        controls: Iterable[RoomControl] = None,
        templates: Iterable[RoomControlTemplate] = None,
    ):
        from roomcontrol.export import generate_roomcontrol_commands

        macros, panels, activate = generate_roomcontrol_commands(
            controls=controls, templates=templates
        )
        return macros + panels + activate

    def get_room_controls_command_zip(
        self,
        controls: Iterable[RoomControl] = None,
        templates: Iterable[RoomControlTemplate] = None,
    ) -> CommandDict:
        from roomcontrol.export import generate_roomcontrol_zip

        filename, data = generate_roomcontrol_zip('provision', controls=controls, templates=templates)
        checksum = hashlib.sha512(data).hexdigest()

        from django.urls import reverse

        from roomcontrol.models import RoomControlZipExport
        zipfile = RoomControlZipExport.objects.filter(checksum=checksum).first()
        if not zipfile:
            zipfile = RoomControlZipExport.objects.store(content=data,
                                                         control=controls[0] if controls else None,
                                                         template=templates[0] if templates else None,
                                                         checksum=checksum)

        export_url = '{}{}'.format(settings.EPM_BASE_URL,
                                   reverse('roomcontrol-zip', args=[zipfile.secret_key]),
                                   )

        return {
            'command': ['Provisioning', 'Service', 'Fetch'],
            'arguments': {
                'URL': export_url,
                'Checksum': checksum,
                'ChecksumType': 'SHA512',
            },
            'body': None,
        }

    def set_room_controls(
        self,
        controls: Iterable[RoomControl] = None,
        templates: Iterable[RoomControlTemplate] = None,
    ):

        from roomcontrol.export import generate_roomcontrol_commands

        macros, panels, activate = generate_roomcontrol_commands(
            controls=controls, templates=templates
        )

        result = []

        result.append(self.run_multiple_commands(macros + panels))
        if activate:
            if not settings.TEST_MODE:
                sleep(3)  # allow macro runtime to update
            result.append(self.run_multiple_commands(activate))

        return b'\n'.join(result)

    def get_clear_room_controls_commands(
        self,
        all=False,
        controls: Iterable[RoomControl] = None,
        templates: Iterable[RoomControlTemplate] = None,
    ) -> List[CommandDict]:

        from roomcontrol.models import RoomControl, RoomControlFile
        if all:
            return [
                {
                    'command': ['Macros', 'Macro', 'RemoveAll'],
                },
                {
                    'command': ['UserInterface', 'Extensions', 'Clear'],
                },
            ]

        all_controls = []
        if controls:
            all_controls.extend(controls)
        if templates:
            all_controls.extend(RoomControl.objects.distinct().filter(templates__in=templates))

        result = []

        for control_file in RoomControlFile.objects.filter(control__in=all_controls):
            if control_file.extension == 'js':
                result.append(
                    {
                        'command': ['Macros', 'Macro', 'Remove'],
                        'arguments': {'Name': control_file.label},
                    }
                )
            elif control_file.extension == 'xml':
                result.append(
                    {
                        'command': ['UserInterface', 'Extensions', 'Panel', 'Remove'],
                        'arguments': {'PanelId': control_file.label},
                    }
                )

        return result

    def clear_room_controls(
        self,
        all=False,
        controls: Iterable[RoomControl] = None,
        templates: Iterable[RoomControlTemplate] = None,
    ):
        commands = self.get_clear_room_controls_commands(
            all=all, controls=controls, templates=templates
        )
        result = self.run_multiple_commands(commands)

        # clear state
        if all:
            self.endpoint.room_controls.clear()
            self.endpoint.room_control_templates.clear()
        else:
            if controls:
                self.endpoint.room_controls.remove(*list(controls))
            if templates:
                self.endpoint.room_control_templates.remove(*list(templates))

        return result

    def get_add_ca_certificates_command(
        self, certificates_content: str
    ) -> Tuple[CommandDict, List[CaCertificate]]:

        certificates = self.validate_ca_certificates(certificates_content)
        body = '\r\n'.join(c[0] for c in certificates)

        return {
            'command': ['Security', 'Certificates', 'CA', 'Add'],
            'body': body,
        }, certificates

    def add_ca_certificates(self, certificate_content: str):

        command, certificates = self.get_add_ca_certificates_command(certificate_content)
        result = self.run_command(**command)

        self.save_provisioned_certificates(certificates)

        return force_text(result)

    @staticmethod
    def get_update_address_book_configuration(address_book: AddressBook):
        url = address_book.get_soap_url()
        return [
            {"key": ["Phonebook", "Server[1]", "Type"], "value": "TMS"},
            {"key": ["Phonebook", "Server[1]", "URL"], "value": url},
        ]

    def set_address_book(self, address_book: AddressBook, task: EndpointTask = None):
        return self.set_configuration(
            self.get_update_address_book_configuration(address_book), task=task
        )

    def install_firmware(self, url: str, forced=False) -> bytes:

        forced_kwargs = {
            'Forced': 'True' if forced else 'False',
        }
        if self.endpoint.status.software_version.lower().startswith('tc7'):
            forced_kwargs = {}

        result = b''
        error = None

        def _background():
            nonlocal result, error
            try:
                result = self.run_command(
                    ['SystemUnit', 'SoftwareUpgrade'],
                    {
                        'URL': url,
                        **forced_kwargs,
                    },
                    timeout=10 * 60,
                )
            except ResponseTimeoutError:
                pass
            except Exception as e:
                error = e

        def _run():
            if settings.TEST_MODE:
                return _background()

            thread = Thread(target=_background)
            thread.start()
            thread.join(timeout=180)
            if thread.is_alive():
                raise ResponseTimeoutError()

        try:
            _run()
        except ResponseTimeoutError:
            return b'No response within time limit, endpoint will probably continue in background'
        else:
            return result
        finally:
            if error:
                raise error

    def get_users(self):

        response = self.run_command(['UserManagement', 'User', 'List'], {'Limit': '10', 'Offset': '0'})
        return response

    def get_set_password_command(
        self, username: str, password: str, validate_current_password: Union[bool, str] = True
    ):
        if self.endpoint.status.software_version.lower().startswith('tc7'):
            return {
                'command': ['SystemUnit', 'AdminPassword', 'Set'],
                'arguments': {'Password': password},
            }

        passphrase = {}
        if validate_current_password is True:
            validate_current_password = self.endpoint.password
        if validate_current_password:
            passphrase['YourPassphrase'] = validate_current_password

        return {
            'command': ['UserManagement', 'User', 'Passphrase', 'Set'],
            'arguments': {
                'NewPassphrase': password,
                'Username': username,
                **passphrase,
            },
        }

    def set_password(self, username, password, validate_current_password: Union[bool, str] = True):

        response = self.run_command(
            **self.get_set_password_command(
                username, password, validate_current_password=validate_current_password
            )
        )
        if b'<PassphraseSetResult status="OK"' in response:
            if username == self.endpoint.username:
                self.endpoint.password = password
                if self.endpoint.pk:
                    self.endpoint.save(update_fields=['password'])
            return True

        raise self.error('Password not set: {}'.format(response.decode('utf-8')))

    def clear_other_sessions(self):

        xml = self.run_command(['Security', 'Session', 'List'], {})

        result = []
        for session in safe_xml_fromstring(xml).find('.//SessionListResult'):

            session_id = session.findtext('./Id') or ''
            if session_id == self.endpoint.session_id:
                continue
            self.run_command(['Security', 'Session', 'Terminate'], {'SessionId': session_id})
            result.append(session_id)
        return result

