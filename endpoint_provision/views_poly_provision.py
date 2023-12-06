import base64
import logging
import os
import re
import struct
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Dict, Iterable, List
from xml.sax.saxutils import escape

from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.conf import settings
from django.http import HttpResponse, HttpRequest
from django.utils.encoding import force_text
from django.views.decorators.csrf import csrf_exempt
from sentry_sdk import capture_exception

from customer.models import Customer
from endpoint.consts import MANUFACTURER
from endpoint.ext_api.parser.poly_event import PolyEvent
from endpoint.models import CustomerSettings, Endpoint
from endpoint.types import CommandDict, ConfigurationDict
from endpoint_provision.models import EndpointTask
from endpoint_provision.views_tms_provision import (
    check_endpoint_customer,
    get_passive_endpoint_tasks,
)
from provider.exceptions import AuthenticationError
from shared.exceptions import format_exception

if TYPE_CHECKING:
    from xmlschema import XMLSchema

DEFAULT_HEARTBEAT_INTERVAL = 7 * 60

logger = logging.getLogger(__name__)


def _log_poly(request, endpoint=None, **extra):
    try:
        event = extra.pop('event', None) or 'tms'
        from debuglog.models import EndpointPolyProvision

        extra.setdefault('headers', {k: v for k, v in request.META.items() if k.startswith('HTTP')})

        EndpointPolyProvision.objects.store(
            ip=request.META.get('REMOTE_ADDR'),
            content=request.body,
            event=event,
            endpoint=endpoint,
            **extra
        )
    except Exception:
        capture_exception()



def get_msg_str(msg, start):
    msg_len, _, msg_off = struct.unpack("<HHH", msg[start : start + 6])
    return msg[msg_off : msg_off + msg_len].replace("\0", '')


def ntlm_auth(request):
    """
    ntlm auth flow, no actual verification.
    Return user_name, error-response.
    """
    auth = request.META.get('HTTP_AUTHORIZATION')
    if not auth:
        response = HttpResponse(status=401)
        response['WWW-Authenticate'] = "NTLM"
        return None, response

    if not auth.startswith("NTLM"):
        return None, None

    msg = base64.b64decode(auth[5:])
    ntlm_fmt = "<8sb"  # string, length 8, 4 - op
    NLTM_SIG = b"NTLMSSP\0"
    signature, op = struct.unpack(ntlm_fmt, msg[:9])
    if signature != NLTM_SIG:
        logger.info("ntlm error: header not recognized")
        return None, None

    if op == 1:
        out_msg_fmt = ntlm_fmt + "2I4B2Q2H"
        out_msg = struct.pack(
            out_msg_fmt,
            NLTM_SIG,  # Signature
            2,  # Op
            0,  # target name len
            0,  # target len off
            1,
            2,
            0x81,
            1,  # flags
            0,  # challenge
            0,  # context
            0,  # target info len
            0x30,  # target info offset
        )

        response = HttpResponse(status=401)
        response['WWW-Authenticate'] = b"NTLM %s" % base64.b64encode(out_msg).strip()
        return None, response
    elif op == 3:
        username = get_msg_str(msg, 36)
        return username, None

    return None, None


def find_request_auth(request):
    auth_method, payload = request.META.get('HTTP_AUTHORIZATION', '').split(' ')
    if auth_method == 'NTLM':
        return ntlm_auth(request)
    elif auth_method == 'Basic':
        parts = [p for p in force_text(base64.b64decode(payload)).split(':') if p != 'mividas']
        return parts[0], None
    return None, None


def get_endpoint_attributes_from_request(request: HttpRequest):

    endpoint_serial = None
    endpoint_mac = None

    if not endpoint_serial and request.META.get('HTTP_SERIALNUMBER'):
        endpoint_serial = request.META.get('HTTP_SERIALNUMBER') or ''

    if not endpoint_serial and '(SN:' in request.META.get('HTTP_USER_AGENT'):
        endpoint_serial = re.search(r'SN:([^ \)]+)', request.META.get('HTTP_USER_AGENT')).group(1)

    if request.META.get('HTTP_X_DEVICE'):
        endpoint_serial, endpoint_mac, endpoint_ip = request.META['HTTP_X_DEVICE'].split('/')

    if request.body and request.body[:1] in ('<', b'<'):
        try:
            endpoint_serial = (
                re.search(r'<serialNumber>([^<]+)</serialNumber>', force_text(request.body))
                .group(1)
                .strip()
            )
        except Exception:
            pass

    return {
        'endpoint_serial': endpoint_serial,
        'endpoint_mac': Endpoint.format_mac_address(endpoint_mac),
    }


@csrf_exempt
def poly_rprm_provision(request, customer_secret=None, endpoint_secret=None, endpoint_serial=None):
    print(request.body)
    print(request.META.get('Authorization'))
    print({k: v for k, v in request.META.items() if k.startswith('HTTP')})

    if request.META.get('HTTP_AUTHORIZATION', ''):
        try:
            username, response = find_request_auth(request)
        except ValueError:
            pass
        else:
            if response:
                return response
            customer_secret = username

    customer = check_endpoint_customer(request, customer_secret, partial(_log_poly, request))
    if isinstance(customer, HttpResponse):
        return customer

    endpoint_attributes = get_endpoint_attributes_from_request(request)

    if endpoint_serial and endpoint_serial.startswith('config-'):
        endpoint_serial = endpoint_serial[len('config-') :]
        endpoint_attributes['endpoint_serial'] = endpoint_serial

    return PolyPassiveProvisionBase.from_request(
        request,
        customer_secret=customer_secret,
        endpoint_secret=endpoint_secret,
        **endpoint_attributes,
    ).get_response()


@csrf_exempt
def poly_directory_root_passive_provision(
    request, customer_secret=None, endpoint_secret=None, endpoint_serial=None
):
    if not customer_secret and request.META.get('HTTP_AUTHORIZATION'):
        try:
            username, response = find_request_auth(request)
        except ValueError:
            pass
        else:
            if response:
                return response
            customer_secret = username

    customer = check_endpoint_customer(request, customer_secret, partial(_log_poly, request))
    if isinstance(customer, HttpResponse):
        return customer

    _log_poly(request)

    if endpoint_serial and ('config-' in endpoint_serial or 'logs-' in endpoint_serial):
        return poly_rprm_provision(
            request,
            customer_secret=customer_secret,
            endpoint_secret=endpoint_secret,
            endpoint_serial=endpoint_serial,
        )

    endpoint_attributes = get_endpoint_attributes_from_request(request)

    xml_data = '''
    <?xml version="1.0" standalone="yes"?>
    <APPLICATION
        APP_FILE_PATH="" CONFIG_FILES="config-{serial}.cfg" MISC_FILES="" LOG_FILE_DIRECTORY="logs-{serial}"
        OVERRIDES_DIRECTORY="" CONTACTS_DIRECTORY="" LICENSE_DIRECTORY="" USER_PROFILES_DIRECTORY=""
        CALL_LISTS_DIRECTORY="">
    </APPLICATION>
    '''.strip().format(
        serial=escape(
            endpoint_serial
            or endpoint_attributes.get('endpoint_serial')
            or endpoint_attributes.get('endpoint_mac')
            or ''
        )
    )
    return HttpResponse(xml_data, content_type='text/xml')


class PolyPassiveProvisionBase:
    def __init__(
        self,
        request,
        customer: Customer,
        endpoint: Endpoint,
        tasks: Iterable[EndpointTask] = None,
    ):

        self.request = request

        self.customer = customer
        self.endpoint = endpoint
        self.tasks = self.get_tasks() if tasks is None else tasks

        self.configuration: List[ConfigurationDict] = []
        self.commands: List[CommandDict] = []

    response_base: str

    def get_default_configuration(self) -> Dict[str, Any]:
        raise NotImplementedError()

    @classmethod
    def from_request(
        cls,
        request,
        customer_secret=None,
        endpoint_secret=None,
        endpoint_serial=None,
        endpoint_mac=None,
    ):

        customer = check_endpoint_customer(request, customer_secret, partial(_log_poly, request))
        if isinstance(customer, HttpResponse):
            raise AuthenticationError()

        handler = PolyEvent(
            endpoint_serial, customer, endpoint_mac=endpoint_mac, endpoint_secret=endpoint_secret
        )
        try:
            handler.get_endpoint()
        except Endpoint.DoesNotExist:
            if not customer:
                raise
            handler.create_endpoint(customer, request_ip=request.META['REMOTE_ADDR'])

        endpoint = handler.handle_event()

        return cls.get_endpoint_instance(endpoint, request=request)

    @classmethod
    def get_endpoint_instance(cls, endpoint: 'Endpoint', **kwargs):

        kwargs.setdefault('request', None)
        kwargs.setdefault('customer', endpoint.customer)

        if endpoint.manufacturer == MANUFACTURER.POLY_STUDIO_X:
            return PolyXSeriesPassive(endpoint=endpoint, **kwargs)
        elif endpoint.manufacturer == MANUFACTURER.POLY_GROUP:
            return PolyGroupRPRMPassive(endpoint=endpoint, **kwargs)
        elif endpoint.manufacturer == MANUFACTURER.POLY_TRIO:
            return PolyTrioPassive(endpoint=endpoint, **kwargs)
        elif endpoint.manufacturer == MANUFACTURER.POLY_HDX:
            return PolyHdxPassive(endpoint=endpoint, **kwargs)

        raise KeyError(endpoint.manufacturer)

    def get_tasks(
        self,
        lock_tasks: bool = False,
        constraint_ts: datetime = None,
        ignore_constraints: bool = False,
    ):
        return get_passive_endpoint_tasks(
            endpoint=self.endpoint,
            lock_tasks=lock_tasks,
            constraint_ts=constraint_ts,
            ignore_constraints=ignore_constraints,
        )

    def populate_tasks(self):
        """Update self.configuration"""
        for task in self.tasks:
            try:
                self.populate_single_task(task)
            except NotImplementedError:
                task.fail('Not implemented')
                if not settings.TEST_MODE or len(self.tasks) == 1:
                    raise
                logging.warning(
                    'Not implemented: %s for %s',
                    task.action,
                    self.endpoint.get_api().__class__.__name__,
                )
            except Exception as e:
                if settings.TEST_MODE or settings.DEBUG:
                    task.fail(str(e))
                else:
                    task.fail(format_exception(e))
                capture_exception()
            else:
                task.complete('Run in background')  # TODO set status after returning response

    def populate_single_task(self, task: EndpointTask):
        """Add configuration values to self.configuration from single task"""

        extra_properties = task.data and task.data.extra_properties or {}

        if task.action == 'configuration':
            self.configuration.extend(task.data.configuration)
        elif task.action == 'dial_info':
            self.configuration.extend(
                self.endpoint.get_api().get_update_dial_info_configuration(
                    task.data.dial_info,
                    customer=self.customer,
                )
            )
        elif task.action == 'password':
            self.configuration.extend(self.endpoint.get_api().get_set_password_config(task.data.password))
        elif task.action == 'commands':
            self.commands.extend(task.data.commands)
        elif task.action == 'ca_certificates':
            result = self.endpoint.get_api().get_add_ca_certificates_config(task.data.ca_certificates)
            print('========ca_certificate result=========\n', result)
            self.configuration.extend(result)
        elif task.action == 'passive':
            api = self.endpoint.get_api()
            if extra_properties.get('passive', {}).get('chain'):
                api.set_chained_passive_provisioning()

            self.configuration.extend(api.get_passive_provisioning_configuration())
        else:
            # TODO
            raise NotImplementedError(task.action)

    def get_configuration_content(self, include_default_configuration=True) -> str:
        if include_default_configuration:
            configuration = self.get_default_configuration()
        else:
            configuration = {}

        try:
            self.populate_tasks()
        except Exception:
            logger.warning('Serialization error', exc_info=True)
            # raise  # TODO

        key_map = self.endpoint.get_api().configuration_key_map_reversed

        def _key(config):
            key = config['key']
            if not isinstance(config['key'], str):
                key = '.'.join(config['key'])
            key = key.replace('[', '.').replace(']', '')
            return key_map.get(key) or key

        configuration.update({_key(item): item['value'] for item in self.configuration})

        return self.get_nested_configuration_content(configuration)

    def get_nested_configuration_content(self, configuration: Dict[str, str]):

        configuration_values = self.endpoint.get_api().get_configuration_settings()

        # TODO recurse and set attribute on nested xml node using parent_elements

        errors = []
        ignore = ('prov.heartbeat.interval',)

        values = []
        for key, value in configuration.items():

            try:
                parent_elements = configuration_values.find(key).meta.get('parents')
            except (KeyError, AttributeError):
                parent_elements = ('',)

            if not parent_elements and key not in ignore:
                errors.append(key)

            cur = '{}="{}"'.format(escape(key), escape(str(value)))
            values.append(cur)

        if settings.DEBUG or settings.TEST_MODE:
            if errors:
                logger.warning(
                    'Parent node missing for {} configuration values: {}'.format(
                        self.endpoint.get_api().__class__.__name__, key
                    )
                )

        # TODO replace ALL with correct nodes
        return '<ALL \n{} />'.format('\n  '.join(values))

    def get_response_content(self, include_default_configuration=True):

        content = self.response_base.strip().format(
            self.get_configuration_content(
                include_default_configuration=include_default_configuration
            )
        )
        return content

    def get_response(self):

        content = self.get_response_content()
        _log_poly(self.request, self.endpoint, response=content)

        if settings.DEBUG or settings.TEST_MODE:
            try:
                self.get_xml_schema().validate(safe_xml_fromstring(content))
            except NotImplementedError:
                pass
            except Exception:
                logger.warning('Invalid XML %s', content, exc_info=True)
                if settings.TEST_MODE:
                    raise

        return HttpResponse(content, content_type='text/xml')

    schema_cache = {}

    def get_xml_schema(self):

        if self.__class__.__name__ in self.schema_cache:
            return self.schema_cache[self.__class__.__name__]

        import xmlschema

        content = self.get_xml_schema_content()
        content = content.replace(
            '</xsd:schema>',
            '''
        <xsd:element name="PHONE_CONFIG" />
        <xsd:element name="ALL" />
        <xsd:element name="ProvisionResponseMessage" />
        </xsd:schema>''',
        )
        result = xmlschema.XMLSchema(content)
        self.schema_cache[self.__class__.__name__] = result
        return result

    def get_xml_schema_content(self) -> str:
        raise NotImplementedError()

    # TODO
    provision_base: str = '<All>{}</All>'


class PolyXSeriesPassive(PolyPassiveProvisionBase):
    def get_default_configuration(self):
        c_settings = CustomerSettings.objects.get_for_customer(self.customer)
        return {
            'prov.heartbeat.interval': "120",
            'prov.polling.period': "60",
            'prov.softupdate.https.enable': "false",
            'device.prov.password': c_settings.secret_key or '',
            'device.prov.serverName': self.endpoint.get_provision_url(),
            'device.prov.user': "mividas",
        }

    def get_xml_schema_content(self):
        filename = os.path.join(settings.BASE_DIR, 'endpoint_data', 'temp', 'x30polycomConfig.xsd')
        with open(filename) as fd:
            return fd.read()

    # TODO correct structure:
    response_base = '''
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <PHONE_CONFIG>
      {}
    </PHONE_CONFIG>
    '''.strip()


class PolyGroupDPMSPassive(PolyPassiveProvisionBase):
    def get_default_configuration(self):
        return {
            'generalConfig.softwareUpdateCheckInterval': "PT120S",
            'generalConfig.profileUpdateCheckInterval': "PT60S",
            'generalConfig.heartbeatPostInterval': "false",
        }

    def get_configuration_content(self):
        configuration = self.get_default_configuration()

        values = []
        for key, value in configuration.items():
            cur = '{}="{}"'.format(key.replace('"', '\\"'), value.replace('"', '\\"'))
            values.append(cur)

        return '\n'.join(values)

    def get_xml_schema_content(self):

        filename = os.path.join(
            settings.BASE_DIR, 'endpoint_data', 'temp', 'group500polycomConfig.xsd'
        )
        with open(filename) as fd:
            return fd.read()

    # TODO correct structure:
    response_base = '''
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ProvisionResponseMessage xmlns:ns2="http://polycom.com/polaris">
  <protocolVersion>1.0</protocolVersion>
  <status>OK</status>
    <provItems>
    <provItemsVersion>1.0</provItemsVersion>
    {}
      </provItems>
</ProvisionResponseMessage>
    '''

class PolyGroupRPRMPassive(PolyPassiveProvisionBase):

    def get_default_configuration(self):
        return {
            'generalConfig.softwareUpdateCheckInterval': "PT120S",
            'generalConfig.profileUpdateCheckInterval': "PT60S",
            'generalConfig.heartbeatPostInterval': "false",
        }

    def get_xml_schema_content(self):
        filename = os.path.join(
            settings.BASE_DIR, 'endpoint_data', 'temp', 'group500polycomConfig.xsd'
        )
        with open(filename) as fd:
            return fd.read()

    # TODO correct structure:
    response_base = '''
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ProvisionResponseMessage xmlns:ns2="http://polycom.com/polaris">
  <protocolVersion>1.0</protocolVersion>
  <status>OK</status>
    <provItems>
    <provItemsVersion>1.0</provItemsVersion>
    {}
      </provItems>
</ProvisionResponseMessage>
    '''

    # sync request:
    cdrSyncRequestArgument = '<cdrSyncRequest />'


class PolyTrioPassive(PolyPassiveProvisionBase):
    # TODO

    def get_default_configuration(self):
        return {
            'generalConfig.softwareUpdateCheckInterval': "PT120S",
            'generalConfig.profileUpdateCheckInterval': "PT60S",
            'generalConfig.heartbeatPostInterval': "false",
        }

    def get_xml_schema_content(self):

        filename = os.path.join(
            settings.BASE_DIR, 'endpoint_data', 'temp', 'trio8300polycomConfig.xsd'
        )
        with open(filename) as fd:
            return fd.read()

    def populate_single_task(self, task: EndpointTask):
        # if task.action == 'password':

        return super().populate_single_task(task)
    # TODO correct structure:
    response_base = '''
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!-- Generated global.cfg Configuration File -->
<polycomConfig xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="polycomConfig.xsd">
    {}
</polycomConfig>
    '''


class PolyHdxPassive(PolyPassiveProvisionBase):
    # TODO
    def get_default_configuration(self):
        return {
            'generalConfig.softwareUpdateCheckInterval': "PT120S",
            'generalConfig.profileUpdateCheckInterval': "PT60S",
            'generalConfig.heartbeatPostInterval': "false",
        }

    def get_xml_schema_content(self):

        filename = os.path.join(
            settings.BASE_DIR, 'endpoint_data', 'temp', 'hdxpolycomConfig.xsd'
        )
        with open(filename) as fd:
            return fd.read()

    def populate_single_task(self, task: EndpointTask):
        if task.action == 'commands':
            # FIXME are commands ever used? Best way to convert to configuration in that case?
            return self.configuration.extend(
                {'key': cmd['command'], 'value': cmd.get('body', '')} for cmd in task.data.commands
            )
        return super().populate_single_task(task)

    # TODO correct structure:
    response_base = '''
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ProvisionResponseMessage xmlns:ns2="http://polycom.com/polaris">
  <protocolVersion>1.0</protocolVersion>
  <status>OK</status>
    <provItems>
    <provItemsVersion>1.0</provItemsVersion>
    {}
      </provItems>
</ProvisionResponseMessage>
    '''
