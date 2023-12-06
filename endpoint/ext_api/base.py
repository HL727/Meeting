from __future__ import annotations

import binascii
import hashlib
import re
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from xml.etree import ElementTree as ET

from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.encoding import force_bytes
from django.utils.timezone import now
from django.utils.translation import gettext as _

from customer.models import Customer
from endpoint import consts
from endpoint_data.models import EndpointCurrentState, EndpointDataFileBase
from endpoint_provision.models import EndpointProvision, EndpointProvisionedObjectHistory
from provider.exceptions import (
    AuthenticationError,
    InvalidSSLError,
    ResponseConnectionError,
    ResponseError,
)
from provider.ext_api.base import ProviderAPI
from shared.utils import maybe_update

from ..consts import PLACEHOLDER_PASSWORD, CallControlAction
from .parser import cisco_ce as parser
from .types.cisco_ce import (
    CaCertificate,
    CallHistoryDict,
    CommandDict,
    ConfigurationDict,
    DialInfoDict,
    ProvisionTypes,
    StatusDict,
)

if TYPE_CHECKING:
    from requests.adapters import Response

    from endpoint.models import Endpoint, CustomerSettings
    from endpoint_backup.models import EndpointBackup
    from endpoint_provision.models import EndpointTask

    from .parser.cisco_ce import (
        NestedConfigurationXMLResult,
        NestedStatusXMLResult,
        NestedXMLResult,
    )
    from .parser.types import ParsedCommandTuple, ParsedConfigurationTuple, ValueSpaceDict


class EndpointProviderAPI(ProviderAPI):

    _configuration_buffer: Optional[List[ConfigurationDict]] = None
    provider: Endpoint
    endpoint: Endpoint
    active_task: Optional[EndpointTask] = None

    def __init__(self, provider: Endpoint, customer=None, allow_cached_values=None):
        self.customer = customer
        super().__init__(provider=provider, customer=customer, allow_cached_values=allow_cached_values)

    @property
    def endpoint(self):
        return self.provider

    def get_session(self, *args, **kwargs):
        if self.endpoint.connection_type == consts.CONNECTION.PROXY and self.provider.proxy:
            proxies = self.provider.proxy.http_proxy_settings
        else:
            proxies = None

        if self.endpoint.connection_type == consts.CONNECTION.PASSIVE:
            if settings.TEST_MODE or settings.DEBUG:
                raise BaseException('Trying to get data from a passive system')  # noqa
            raise ResponseConnectionError('No direct connection available')

        session = super().get_session(*args, **kwargs)
        session.proxies = proxies
        return session

    def get_base_url(self):
        if self.endpoint.http_mode == consts.HTTP_MODES.HTTP or self.endpoint.api_port == 80:
            return 'http://%s' % self.ip
        return 'https://%s:%s' % (self.ip, self.endpoint.api_port or 443)

    def check_response_errors(self, response):
        super().check_response_errors(response)

        if response.status_code == 502:
            if b'sslv3 alert handshake failure' in response.content:
                raise InvalidSSLError(_('SSL Error from proxy'), response)
            raise ResponseConnectionError('502 error', response)

    _valuespace: ValueSpaceDict

    def get_valuespace_data(self, force=False, fd: EndpointDataFileBase = None) -> ValueSpaceDict:
        """Retrieve and parse valuespace data (info about configuration/commands)"""

        if hasattr(self, '_valuespace'):
            return self._valuespace

        fd = fd or self.get_valuespace_data_file(force=force)
        
        result = self.endpoint.get_parser('valuespace', fd.content).parse()
        self._valuespace = result
        return result

    def get_cached_valuespace_data_file(self, age=60 * 60):

        if not self.endpoint.has_direct_connection or not self.endpoint.is_online:
            cached = self.endpoint.get_cached_file('valuespace', None)
        else:
            cached = self.endpoint.get_cached_file('valuespace', age)

        if cached:
            return cached

        if not self.endpoint.has_direct_connection and self.endpoint.product_name:
            software_version = self.endpoint.status.software_version[:2]
            similar_state = (
                EndpointCurrentState.objects.filter(
                    endpoint__customer=self.endpoint.customer,
                    endpoint__product_name=self.endpoint.product_name,
                    endpoint__status__software_version__istartswith=software_version,
                    valuespace__isnull=False,
                )
                .order_by('-valuespace__ts_created')
                .first()
            )
            if similar_state:
                return similar_state.valuespace
            if similar_state and similar_state.valuespace:
                return similar_state.valuespace

    def get_valuespace_data_file(self, force=True):

        if not force or not self.endpoint.has_direct_connection:
            cached = self.get_cached_valuespace_data_file()
            if cached:
                return cached

        if not self.endpoint.has_direct_connection and not self.endpoint.is_poly:
            raise ResponseConnectionError('No direct connection available')

        response = self._fetch_valuespace_data_file()

        if response.status_code != 200:
            raise self.error('Invalid status code {}'.format(response.status_code), response)
        state = EndpointCurrentState.objects.store(self.endpoint, valuespace=response.content)
        state.valuespace.ts_last_used = now()

        return state.valuespace

    def _fetch_valuespace_data_file(self) -> Response:
        """Fetch actual valuespace content"""
        raise NotImplementedError()

    def get_commands_data(
        self,
        fd: Optional[EndpointDataFileBase] = None,
        valuespace: Optional[EndpointDataFileBase] = None,
    ) -> NestedXMLResult[ParsedCommandTuple]:
        """Fetch configuration settings and their current values"""

        if not fd:
            fd, valuespace = self.get_commands_data_file()

        if b'<Valuespace type' in fd.content:  # inline in file
            valuespace_data = None
        elif valuespace:
            valuespace_data = self.endpoint.get_parser('valuespace', valuespace.content).parse()
        else:
            valuespace_data = self.get_valuespace_data()

        return self.endpoint.get_parser('command', fd.content, valuespace_data).parse()

    def get_cached_commands_data_file(
        self,
        allow_similar=False,
    ) -> Tuple[Optional[EndpointDataFileBase], Optional[EndpointDataFileBase]]:

        cached = self.endpoint.get_cached_file('command', None)
        valuespace = None

        if not cached and self.endpoint.product_name and allow_similar:
            similar_state = (
                EndpointCurrentState.objects.filter(
                    endpoint__customer=self.endpoint.customer,
                    endpoint__product_name=self.endpoint.product_name,
                    command__isnull=False,
                )
                .order_by('-command__ts_created')
                .first()
            )
            if similar_state:
                cached = similar_state.command
                if (
                    similar_state.valuespace
                    and b'<Valuespace type' not in similar_state.command.content
                ):
                    valuespace = similar_state.valuespace

        return cached, valuespace

    def get_commands_data_file(
        self, force=False
    ) -> Tuple[EndpointDataFileBase, Optional[EndpointDataFileBase]]:

        if not force:
            cached, valuespace = self.get_cached_commands_data_file(
                allow_similar=not self.endpoint.has_direct_connection
            )
            if cached:
                return cached, valuespace

        if not self.endpoint.has_direct_connection:
            raise ResponseConnectionError('No direct connection available')

        try:
            response = self._fetch_commands_data_file()
        except ResponseConnectionError as e:
            cached, valuespace = self.get_cached_commands_data_file(allow_similar=True)
            if cached:
                return cached, valuespace
            raise e

        if response.status_code != 200:
            raise self.error('Invalid status code {}'.format(response.status_code), response)

        state = EndpointCurrentState.objects.store(self.endpoint, command=response.content)
        state.command.ts_last_used = now()

        return state.command, None

    def _fetch_commands_data_file(self) -> Response:
        """Fetch actual command list content"""
        raise NotImplementedError()

    def run_command(
        self,
        command: List[str],
        arguments: Mapping[str, Union[str, List[str]]] = None,
        body=None,
        timeout: int = 30,
    ):
        raise NotImplementedError()

    def run_multiple_commands(self, command_dicts: Iterable[CommandDict], timeout=30):
        raise NotImplementedError()

    def get_status(self, data: NestedStatusXMLResult = None) -> StatusDict:  # noqa: CCR001
        raise NotImplementedError()

    @staticmethod
    def load_status_xml(content: bytes) -> ET.Element:
        return safe_xml_fromstring(content)

    def get_status_data(
        self, force=False, fd: Optional[EndpointDataFileBase] = None
    ) -> parser.NestedStatusXMLResult:

        fd = fd or self.get_status_data_file(force=force)
        try:
            self.load_status_xml(fd.content)
        except Exception:
            raise self.error('Could not parse response XML data')
        return self.endpoint.get_parser('status', fd.content).parse()

    def get_cached_status_data(self, age=4 * 60 * 60):

        fd = self.get_cached_status_data_file(age=age)
        if not fd:
            return None, None

        return self.get_status_data(fd=fd), fd

    def get_cached_status_data_file(self, age=1) -> Union['EndpointDataFileBase', None]:

        if not self.endpoint.has_direct_connection:
            cached = self.endpoint.get_cached_file('status', None)
        else:
            cached = self.endpoint.get_cached_file('status', age)

        return cached

    def get_status_data_file(self, force=False) -> 'EndpointDataFileBase':
        if not force:
            cached = self.get_cached_status_data_file()
            if cached:
                return cached

        if not self.endpoint.has_direct_connection:
            raise ResponseConnectionError('No direct connection available')

        from endpoint import consts

        try:
            response = self._fetch_status_data_file()
        except InvalidSSLError:
            if self.endpoint.http_mode == consts.HTTP_MODES.HTTPS:
                self.endpoint.http_mode = consts.HTTP_MODES.HTTP
                self.endpoint.api_port = 80
                self.endpoint.save(update_fields=['http_mode', 'api_port'])
                return self.get_status_data_file(force=force)
            raise
        except ResponseConnectionError:
            if not force:
                cached = self.get_cached_status_data_file(age=30 * 24 * 60 * 60)
                if cached:
                    return cached
            raise
        else:
            if response.status_code != 200:
                raise self.error('Invalid status code {}'.format(response.status_code), response)

        state = EndpointCurrentState.objects.store(self.endpoint, status=response.content)
        state.status.ts_last_used = now()

        return state.status

    def _fetch_status_data_file(self):
        raise NotImplementedError()

    def get_configuration_data(
        self, force=False, fd: Optional[EndpointDataFileBase] = None, require_valuespace=False
    ) -> NestedXMLResult[ParsedConfigurationTuple]:
        fd = fd or self.get_configuration_data_file(force=force)

        valuespace = {}
        try:
            valuespace_fd = self.get_cached_valuespace_data_file()
            if valuespace_fd or require_valuespace:
                valuespace = self.get_valuespace_data(fd=valuespace_fd)
        except (AuthenticationError, ResponseConnectionError):
            pass  # TODO display message?

        return parser.ConfigurationParser(safe_xml_fromstring(fd.content), valuespace).parse()

    def get_cached_configuration_data(self, age=4 * 60 * 60):

        fd = self.get_cached_configuration_data_file(age=age)
        if not fd:
            return None, None

        return self.get_configuration_data(fd=fd), fd

    def get_cached_configuration_data_file(self, age=1) -> Optional[EndpointDataFileBase]:

        if not self.endpoint.has_direct_connection:
            cached = self.endpoint.get_cached_file('configuration', None)
        else:
            cached = self.endpoint.get_cached_file('configuration', age)

        return cached

    def get_configuration_data_file(self, force=False) -> 'EndpointDataFileBase':

        if not force:
            cached = self.get_cached_configuration_data_file()
            if cached:
                return cached

        if not self.endpoint.has_direct_connection:
            raise ResponseConnectionError('No direct connection available')

        try:
            response = self._fetch_configuration_data_file()
        except ResponseConnectionError:
            if not force:
                cached = self.get_cached_configuration_data_file(age=30 * 24 * 60 * 60)
                if cached:
                    return cached
            raise

        if response.status_code != 200:
            raise self.error('Invalid status code {}'.format(response.status_code), response)

        state = EndpointCurrentState.objects.store(self.endpoint, configuration=response.content)
        state.configuration.ts_last_used = now()

        return state.configuration

    def _fetch_configuration_data_file(self):
        """Fetch actual configuration values for all known settings"""
        raise NotImplementedError()

    def buffer_configuration(self, arg='start', task=None, disable_buffer=True):
        if arg == 'start':
            self._configuration_buffer = []
        elif arg == 'commit':
            if self._configuration_buffer:
                self.set_configuration(self._configuration_buffer, task=task)
            self._configuration_buffer = None if disable_buffer else []
        else:
            raise ValueError('Invalid arg: {}'.format(arg))

    def set_configuration(self, config: List[ConfigurationDict], task=None):

        if getattr(self, '_configuration_buffer', None) is not None:
            self._configuration_buffer.extend(config)
            return

        raise NotImplementedError()

    _customer_settings: Optional[CustomerSettings] = None

    def get_customer_settings(self):
        from endpoint.models import CustomerSettings

        if self._customer_settings is None:
            self._customer_settings = CustomerSettings.objects.get_for_customer(self.customer)
        return self._customer_settings

    def get_dial_info(
        self, configuration_data: NestedConfigurationXMLResult = None
    ) -> DialInfoDict:
        raise NotImplementedError()

    def get_saved_dial_info(self):
        return {
            'name': self.endpoint.title,
            'sip_display_name': self.endpoint.title,
            'sip': self.endpoint.sip,
            'h323': self.endpoint.h323,
            'h323_e164': self.endpoint.h323_e164,
        }

    def save_dial_info(self, data):
        """Save new information to endpoint object"""
        if data.get('current'):
            # update from current settings, to be used in provision
            data.update(self.get_saved_dial_info())
            data.pop('sip_uri', None)

        update_data = {k: data[k] for k in ('sip', 'h323', 'h323_e164') if data.get(k) is not None}
        if data.get('sip_uri') and 'sip' not in data:
            update_data['sip'] = data['sip_uri']

        if data.get('name'):
            update_data['title'] = data['name']
        result = maybe_update(self.endpoint, update_data)

        return result

    def set_dial_info(self, data: DialInfoDict, task=None):
        data = data.copy()
        self.save_dial_info(data)
        result = self.set_configuration(
            self.get_update_dial_info_configuration(
                data, self.customer, [self.endpoint.status.software_version]
            ),
            task=task,
        )
        return result

    @classmethod
    def get_update_dial_info_configuration(
        cls, data: DialInfoDict, customer: Customer = None, versions: Sequence[str] = None
    ) -> List[ConfigurationDict]:
        raise NotImplementedError()

    def run_task(self, action='', **kwargs):

        obj, result = EndpointProvision.objects.run_single(
            customer=self.endpoint.customer,
            endpoint=self.endpoint,
            user=str(kwargs.pop('user', None) or '')[:100],
            **kwargs
        )
        return obj, result

    @staticmethod
    def validate_ca_certificates(
        certificate_content: str, raise_exception=False
    ) -> List[CaCertificate]:
        """Validate certificate and return tuple with content, sha1- and sha256-fingerprint"""
        delimiter = '-----END CERTIFICATE-----'

        result = []

        for content in re.split(r'\r?\n' + delimiter, certificate_content):
            if not content.strip():
                continue

            from cryptography import x509
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.serialization import Encoding

            try:
                cert = x509.load_pem_x509_certificate(force_bytes(content + '\r\n' + delimiter))
            except Exception:
                if settings.TEST_MODE or settings.DEBUG:
                    raise
                if raise_exception:
                    raise
            else:
                cur = CaCertificate(
                    cert.public_bytes(Encoding.PEM).decode(),
                    binascii.hexlify(cert.fingerprint(hashes.SHA1())).decode(),
                    binascii.hexlify(cert.fingerprint(hashes.SHA256())).decode(),
                    cert.not_valid_after.isoformat(),
                )
                result.append(cur)

        return result

    def call_control(self, action: CallControlAction, argument=None):
        raise NotImplementedError()

    def get_call_history(self, limit=3) -> List[CallHistoryDict]:
        NotImplemented
        return []

    @classmethod
    def _get_sip_proxy_password(
        cls, sip_proxy_password, customer: 'Customer' = None, data: dict = None
    ):
        if sip_proxy_password != PLACEHOLDER_PASSWORD:
            return sip_proxy_password or None

        if not customer:
            return None

        from endpoint.models import CustomerSettings
        c_settings = CustomerSettings.objects.get_for_customer(customer)

        if not data or not data.get('sip_proxy'):
            return c_settings.sip_proxy_password

        is_default_proxy = data.get('sip_proxy') and data['sip_proxy'] == c_settings.sip_proxy
        is_default_user = (
            data.get('sip_proxy_username')
            and data['sip_proxy_username'] == c_settings.sip_proxy_username
        )

        if is_default_proxy and is_default_user:
            return c_settings.sip_proxy_password

        return None

    def get_local_call_statistics(self, limit=3, day_limit=14) -> List[CallHistoryDict]:

        from statistics.models import Leg, Server

        server = Server.objects.get_endpoint_server(self.customer)
        legs = Leg.objects.filter(
            endpoint=self.endpoint,
            server=server,
            direction='outgoing',
            ts_start__gte=now() - timedelta(days=14),
        )
        return [
            {
                'number': leg.remote,
                'name': leg.name,
                'ts_start': leg.ts_start,
                'type': 'Placed',
                'protocol': leg.protocol_str,
                'count': 1,
            }
            for leg in legs
        ]

    def add_ca_certificates(self, certificate_content: str):
        raise NotImplementedError()

    def save_provisioned_certificates(self, certificates: List[CaCertificate]):
        for certificate in certificates:
            self.save_provisioned_object(
                'ca_certificates',
                {
                    'sha1': certificate.sha1_fingerprint,
                    'sha256': certificate.sha256_fingerprint,
                    'not_valid_after': certificate.not_valid_after,
                },
            )

    def save_provisioned_object(self, type: ProvisionTypes, data: Dict[str, Any], replace=False):
        if replace:
            EndpointProvisionedObjectHistory.objects.filter(
                endpoint=self.endpoint, type=type, ts_replaced__isnull=False
            ).update(ts_replaced=now())
        return EndpointProvisionedObjectHistory.objects.create(
            endpoint=self.endpoint, type=type, data=data
        )

    def set_password(self, username, password, validate_current_password: Union[bool, str] = True):
        raise NotImplementedError()

    def get_macro_status(self, configuration_data: NestedConfigurationXMLResult = None) -> bool:
        return False

    def get_support_macros(self) -> bool:
        return False

    def backup(self, backup: EndpointBackup):

        try:
            response = self._fetch_configuration_data_file()
            if response.status_code != 200:
                raise self.error('Invalid status code {}'.format(response.status_code), response)

            backup.hash = hashlib.md5(response.content).hexdigest()
            backup.file.save('{}.xml'.format(backup.hash), ContentFile(response.content))

            backup.set_data('configuration', response.content)

            self.backup_extended_data(backup)

            try:
                response = self._fetch_status_data_file()
                backup.set_data('status', response.content)
            except ResponseError:
                pass

            backup.ts_completed = now()
            backup.save()
        except Exception as e:
            backup.error += str(e) + "\n"
            backup.save()
            raise
        return response

    def backup_extended_data(self, backup: EndpointBackup):
        pass

    def get_analytics_status(self, configuration_data: NestedConfigurationXMLResult = None):
        return {'head_count': False, 'presence': False}

    def get_room_analytics_configuration(
        self,
        head_count: Optional[bool] = True,
        presence: Optional[bool] = True,
        detect_support=True,
    ) -> List[ConfigurationDict]:
        return []

    def get_addressbook_status(self, configuration_data: NestedConfigurationXMLResult = None):
        return {'is_set': False, 'id': False}

    def set_bookings(self, bookings):
        return None  # TODO exception?

    def get_passive_status(self, configuration_data: NestedConfigurationXMLResult = None):
        """
        Return status of current passive provisioning server, and if it is this Rooms installation
        """
        NotImplemented  # TODO
        return {
            'is_set': False,
            'this_installation': False,
            'url': '',
        }

    def set_chained_passive_provisioning(self):
        status = self.get_passive_status()
        if status.get('url') and not status.get('this_installation'):
            self.endpoint.external_manager_service = status['url']
            self.endpoint.save(update_fields=['external_manager_service'])
            return status['url']
        return None

    def check_events_status(self, status_data: NestedStatusXMLResult = None, delay_fix=False):
        return False
