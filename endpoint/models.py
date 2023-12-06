from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from random import choice
from typing import TYPE_CHECKING, Literal, Sequence, Tuple, Union

import pytz
from cacheout import fifo_memoize
from django.conf import settings
from django.db import models, transaction
from django.utils.text import slugify
from django.utils.timezone import localtime, now
from django.utils.translation import ugettext_lazy as _
from sentry_sdk import capture_exception
from timezone_field import TimeZoneField

from customer.models import Customer
from provider.exceptions import AuthenticationError, ResponseConnectionError, ResponseError
from provider.types import ProviderAPICompatible
from shared.utils import maybe_update_or_create, partial_update

from . import consts
from .consts import (
    CONNECTION,
    DIAL_PROTOCOL,
    GHOST_TIMEOUT,
    HTTP_MODES,
    MANUFACTURER,
    STATUS,
    MeetingStatus,
)

if TYPE_CHECKING:
    from customer.models import Customer  # noqa
    from endpoint_data.models import EndpointDataContent
    from endpointproxy.models import EndpointProxy as EndpointProxyFK  # noqa

    from .ext_api import AnyEndpointAPI
    from .ext_api.parser.cisco_ce import NestedConfigurationXMLResult, NestedStatusXMLResult
    from .ext_api.parser.types import ValueSpaceDict
else:
    EndpointProxyFK = 'endpointproxy.EndpointProxy'
    CustomerFK = 'provider.Customer'


Q = models.Q


def default_key():

    return uuid.uuid4().hex


def new_customer_secret(key_length=7):
    chars = 'qertyuasdfghjkzxcbm23456789'

    for _tries in range(50):
        key = ''.join(choice(chars) for _i in range(key_length))
        if not CustomerSettings.objects.filter(secret_key=key).exists():
            return key
    raise ValueError('Could not find id')


def new_proxy_secret(key_length=5):
    return new_customer_secret(key_length)


@fifo_memoize(100, ttl=10)
def all_endpoint_uris():

    endpoints = list(
        Endpoint.objects.filter(connection_type__gte=0).values_list(
            'id', 'h323_e164', 'h323', 'sip'
        )
    )
    return {uri: e[0] for e in endpoints for uri in e[1:] if uri}


@fifo_memoize(100, ttl=10)
def all_endpoint_secrets():
    endpoints = list(
        Endpoint.objects.filter(connection_type__gte=0).values_list(
            'id', 'mac_address', 'serial_number'
        )
    )
    return {secret: e[0] for e in endpoints for secret in e[1:] if secret}


class EndpointManager(models.Manager['Endpoint']):
    def get_from_uri(self, target: str, only: Sequence[str] = None):
        if not target:
            return None

        endpoint_id = all_endpoint_uris().get(target)
        if not endpoint_id:
            return None

        result = Endpoint.objects.filter(pk=endpoint_id)
        if only:
            return Endpoint(id=endpoint_id) if only == 'id' else result.only(only).first()
        return result.first()

    def get_queryset(self):
        return super().get_queryset().select_related('status')

    def get_customer_for_key(self, secret_key: str, raise_exception=True) -> Customer:
        try:
            return Customer.objects.get(epm_settings__secret_key=secret_key)
        except Customer.DoesNotExist:
            if raise_exception:
                raise
        return None  # type: ignore


class Endpoint(ProviderAPICompatible, models.Model):

    customer = models.ForeignKey(Customer, related_name='endpoints', on_delete=models.CASCADE)

    org_unit = models.ForeignKey('organization.OrganizationUnit', null=True, blank=True, on_delete=models.SET_NULL)

    title = models.CharField(_('Namn'), max_length=100, blank=True)
    ip = models.GenericIPAddressField(_('IP-nummer'), blank=True, null=True)

    track_ip_changes = models.BooleanField(
        _('Uppdatera IP automatiskt'),
        default=False,
        blank=True,
        help_text=_('Kräver att event-prenumeration'),
    )

    hostname = models.CharField(_('DNS-namn'), max_length=100, blank=True)

    sip = models.CharField('SIP', max_length=100, blank=True)
    h323 = models.CharField('H323', max_length=100, blank=True)
    h323_e164 = models.CharField(_('H323 E.164'), max_length=100, blank=True)

    timezone = TimeZoneField(null=True, blank=True)

    username = models.CharField(_('Användarnamn'), max_length=50, blank=True)
    password = models.CharField(_('Lösenord'), max_length=50, blank=True)

    connection_type = models.SmallIntegerField(choices=tuple((c.value, c.name) for c in CONNECTION), default=CONNECTION.DIRECT)

    api_port = models.SmallIntegerField(default=443, null=True, blank=True)
    http_mode = models.SmallIntegerField(choices=tuple((h.value, h.name) for h in HTTP_MODES), default=HTTP_MODES.HTTPS)

    proxy = models.ForeignKey('endpointproxy.EndpointProxy', null=True, blank=True, on_delete=models.SET_NULL)

    email_key = models.CharField(_('E-postbrevlåda'), default=default_key, max_length=200, blank=True)

    location = models.CharField(max_length=100, blank=True)
    manufacturer = models.SmallIntegerField(choices=tuple((m.value, m.name) for m in MANUFACTURER), default=MANUFACTURER.CISCO_CE)
    product_name = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    mac_address = models.CharField(max_length=100, blank=True, db_index=True)
    has_head_count = models.BooleanField(null=True)

    dial_protocol = models.CharField(
        max_length=100,
        choices=(('', _('Standardinställning')),) + tuple((d.value, d.name) for d in DIAL_PROTOCOL),
        default="",
        blank=True,
    )

    room_capacity = models.SmallIntegerField(_('Antal platser'), null=True, blank=True)

    sip_registration = models.BooleanField(default=False)
    webex_registration = models.BooleanField(null=True)
    pexip_registration = models.BooleanField(null=True)

    personal_system = models.BooleanField(_('Personligt system'), default=False, blank=True)
    owner_email_address = models.CharField(
        _('E-postadress till person'), max_length=200, blank=True
    )

    external_manager_service = models.URLField(max_length=255, blank=True, null=True)

    hide_from_addressbook = models.BooleanField(_('Dölj i adressböcker'), default=False, blank=True)

    ts_created = models.DateTimeField(auto_now_add=True)

    meetings = models.ManyToManyField('meeting.Meeting', through='EndpointMeetingParticipant',
                                      blank=True, related_name='endpoints')

    session_id = models.CharField(max_length=128, blank=True, editable=False, default='basic')  #  keep using basic?
    session_expires = models.DateTimeField(null=True, blank=True, editable=False)

    ts_feedback_events_set = models.DateTimeField(editable=False, null=True)

    event_secret_key = models.CharField(max_length=64, default=default_key, null=True, unique=True)

    status: 'EndpointStatus'

    objects = EndpointManager()

    STATUS = consts.STATUS
    CONNECTION = consts.CONNECTION
    MANUFACTURER = consts.MANUFACTURER

    @property
    def api_host(self):
        return self.hostname or self.ip

    @property
    def email_address(self):
        return '{}@{}'.format(self.email_key, settings.BOOK_EMAIL_HOSTNAME)

    @property
    def is_cisco(self):
        return self.manufacturer == MANUFACTURER.CISCO_CE

    @property
    def is_poly(self):
        return self.manufacturer in (
            MANUFACTURER.POLY_GROUP,
            MANUFACTURER.POLY_HDX,
            MANUFACTURER.POLY_STUDIO_X,
            MANUFACTURER.POLY_TRIO,
        )

    @property
    def is_new(self):
        return (now() - self.ts_created).total_seconds() < 2 * 60 * 60

    @property
    def is_online(self):
        try:
            return self.status.status > STATUS.UNKNOWN
        except Exception:  # dont know how this is possible
            EndpointStatus.objects.get_or_create(endpoint=self)

    @property
    def is_incoming(self):
        return self.connection_type == CONNECTION.INCOMING

    @property
    def has_direct_connection(self):
        return self.connection_type == CONNECTION.DIRECT or self.proxy_online

    @property
    def proxy_online(self):
        return self.connection_type == CONNECTION.PROXY and self.proxy_id and self.proxy.is_online

    @property
    def is_in_call(self):
        return self.status.status == STATUS.IN_CALL

    @property
    def should_update_provision_document(self):
        if self.status.ts_last_provision_document is None:
            return True
        return self.status.ts_last_provision_document < now() - timedelta(minutes=10)

    @property
    def should_try_password(self):
        return self.password == '__try__'

    def set_offline(self):
        if self.is_online:
            self.set_status(status=STATUS.OFFLINE, head_count=None, ts_last_head_count=now())
        elif self.status == STATUS.AUTH_ERROR:
            pass
        elif self.status.status == STATUS.CONNECTION_ERROR:
            pass
        elif self.status.status != STATUS.OFFLINE:
            self.set_status(status=STATUS.OFFLINE)

    def get_cached_file_content(self, type: str, max_age=10) -> bytes:
        result = self.get_cached_file(type, max_age=max_age)
        if result:
            return result.content
        return None

    def get_cached_file(self, type, max_age=10) -> 'EndpointDataContent':
        try:
            data = getattr(self.files, type)
        except Exception:
            return None
        else:
            if not data:
                return None
            if max_age and max_age < (now() - data.ts_created).total_seconds():
                return None
            return data

    _api = None

    def get_api(self) -> AnyEndpointAPI:  # type: ignore

        if self._api:
            return self._api

        api = None
        if self.manufacturer == MANUFACTURER.CISCO_CE:
            from .ext_api.cisco_ce import CiscoCEProviderAPI
            api = CiscoCEProviderAPI(self, self.customer)
        elif self.manufacturer == MANUFACTURER.POLY_STUDIO_X:
            from .ext_api.poly_studiox import PolyStudioXProviderAPI
            api = PolyStudioXProviderAPI(self, self.customer)
        elif self.manufacturer == MANUFACTURER.POLY_GROUP:
            from .ext_api.poly_group import PolyGroupProviderAPI

            api = PolyGroupProviderAPI(self, self.customer)
        elif self.manufacturer == MANUFACTURER.POLY_TRIO:
            from .ext_api.poly_trio import PolyTrioProviderAPI

            api = PolyTrioProviderAPI(self, self.customer)
        elif self.manufacturer == MANUFACTURER.POLY_HDX:
            from .ext_api.poly_hdx import PolyHDXProviderAPI

            api = PolyHDXProviderAPI(self, self.customer)

        self._api = api
        return api

    def get_parser(
        self,
        type: Literal['status', 'configuration', 'command', 'valuespace'],
        xml_data: bytes,
        valuespace=None,
    ):
        from defusedxml.cElementTree import fromstring as safe_xml_fromstring

        def _valuespace() -> ValueSpaceDict:
            if valuespace is None:
                return self.get_api().get_valuespace_data()
            return valuespace

        if self.manufacturer == MANUFACTURER.CISCO_CE:
            from .ext_api.parser import cisco_ce
            if type == 'status':
                return cisco_ce.StatusParser(self.get_api().load_status_xml(xml_data))
            elif type == 'configuration':
                return cisco_ce.ConfigurationParser(safe_xml_fromstring(xml_data), _valuespace())
            elif type == 'command':
                return cisco_ce.CommandParser(safe_xml_fromstring(xml_data), _valuespace())
            elif type == 'valuespace':
                return cisco_ce.ValueSpaceParser(safe_xml_fromstring(xml_data))
        else:
            from .ext_api.parser import poly_x

            if type == 'status':
                return poly_x.PolyXStatusParser(xml_data)
            elif type == 'configuration':
                return poly_x.PolyXConfigurationParser(safe_xml_fromstring(xml_data), _valuespace())
            elif type == 'command':
                raise NotImplementedError()
            elif type == 'valuespace':
                return poly_x.PolyXValueSpaceParser(safe_xml_fromstring(xml_data))

    def update_all_data(self):

        self.maybe_try_password(do_raise=True)
        status_data = self.get_api().get_status_data()
        self.update_status(status_data=status_data)

        try:
            configuration_data = self.get_api().get_configuration_data()
        except Exception:
            return

        timezone = configuration_data.findtext('./Time/Zone') or configuration_data.findtext(
            './device.local.timezone'
        )
        if timezone:
            try:
                self.timezone = str(pytz.timezone(timezone))
                self.save(update_fields=['timezone'])
            except Exception:
                pass

        if self.is_online:
            self.update_dial_info(configuration_data=configuration_data)

        self.get_api().check_events_status(status_data=status_data)

    @property
    def should_update_online_status(self):
        return not self.status.ts_last_check or self.status.ts_last_check < now() - timedelta(seconds=30)

    def check_online(self):
        if self.is_online:
            return True

        if not self.has_direct_connection or not self.should_update_online_status:
            return False

        try:
            self.update_status(raise_exceptions=False)
        except Exception:
            capture_exception()

        return self.is_online

    def update_status(self, status_data: NestedStatusXMLResult = None, raise_exceptions=True):

        api = self.get_api()

        try:
            if not status_data:
                status_data = api.get_status_data(force=True)
            elif isinstance(status_data, Exception):  # fetched elsewhere - reuse handling
                if not raise_exceptions:
                    return
                raise status_data
            data = api.get_status(data=status_data)
        except AuthenticationError as e:
            data = {'status': STATUS.AUTH_ERROR, 'message': str(e)}
            self.set_status(status=data['status'])
            if raise_exceptions:
                raise
        except ResponseError as e:
            if self.has_direct_connection:
                self.set_offline()
            data = {'status': self.status.status, 'message': str(e)}
            if raise_exceptions:
                raise
        else:
            self.set_status(uptime=data['uptime'], status=data['status'],
                            has_warnings=bool(data['warnings']))
            self.update_basic_data(status_data=status_data)


            if self.manufacturer == consts.MANUFACTURER.CISCO_CE:
                from room_analytics import parse

                parse.store_cisco_ce(status_data, self)

        return data

    def get_new_basic_data_values(self, basic_data):

        new_data = {k: basic_data[k] for k in ['product_name', 'serial_number', 'mac_address', 'has_head_count']
                    if basic_data.get(k) or basic_data.get(k) == False}

        if 'mac_address' in new_data:
            if self.mac_address and new_data['mac_address'].upper() != self.mac_address:

                return {
                    'status': 'Error',
                    'new_status': self.status.status,
                    'message': _('MAC-adressen matchar inte värdet i Rooms'),
                }

            new_data['mac_address'] = new_data['mac_address'].upper()

        if basic_data.get('ip') and self.track_ip_changes:
            new_data['ip'] = basic_data['ip']

        bool_fields = (
            'sip_registration',
            'webex_registration',
            'pexip_registration',
            'has_head_count',
        )
        for f in bool_fields:
            if basic_data.get(f) is not None:
                new_data[f] = bool(basic_data[f])

        if basic_data.get('sip') and not self.sip:
            new_data['sip'] = basic_data['sip']

        if basic_data.get('sip_display_name') and not self.title:
            new_data['title'] = basic_data['sip_display_name']

        return new_data

    def update_basic_data(self, status_data: NestedStatusXMLResult = None):
        data = status_data
        try:
            if data and isinstance(data, Exception):
                raise data
            basic_data = self.get_api().get_basic_data(status_data=data)
        except AuthenticationError as e:
            self.set_status(status=Endpoint.STATUS.AUTH_ERROR)
            return {'status': 'Error', 'new_status': self.status.status, 'message': str(e)}
        except ResponseError as e:
            if not self.has_direct_connection:
                self.set_offline()
            return {'status': 'Error', 'new_status': self.status.status, 'message': str(e)}

        new_data = self.get_new_basic_data_values(basic_data)

        if new_data.get('status', '') == 'Error':
            return new_data

        if new_data != {k: getattr(self, k) for k in new_data}:
            for k, v in new_data.items():
                setattr(self, k, v)

            self.save(update_fields=new_data.keys() if self.pk else None)

        software = {k: basic_data[k] for k in ['software_version', 'software_release']
                    if basic_data.get(k)}

        if software:
            self.set_status(**software)

        return data

    def update_dial_info(self, configuration_data: NestedConfigurationXMLResult = None):

        data = self.get_api().get_dial_info(configuration_data=configuration_data)
        self.sip = self.sip or data['sip'] or ''
        self.title = self.title or data['sip_display_name'] or ''
        self.h323 = self.h323 or data['h323'] or ''
        self.h323_e164 = self.h323_e164 or data['h323_e164'] or ''

        last_sip_proxy_domain = '.'.join(data['sip_proxy'].split('.')[-2:])
        self.pexip_registration = last_sip_proxy_domain in (
            'pexip.me',
            'vp.vc',
            'videxio.net',
            'vmr.vc',
        )

        self.save(update_fields=['sip', 'title', 'h323', 'h323_e164', 'pexip_registration'])

    def set_status(self, **kwargs):

        if kwargs.get('status', self.status.status) > 0:
            kwargs.setdefault('ts_last_online', now())

        if kwargs.get('status'):
            kwargs.setdefault('ts_last_check', now())

        self.status, created = maybe_update_or_create(EndpointStatus, endpoint=self, defaults=kwargs)

    def update_active_meeting(self):

        active_meeting = EndpointMeetingParticipant.objects.filter(endpoint=self) \
            .filter(meeting__ts_start__lte=now(), meeting__ts_stop__gt=now(), meeting__backend_active=True) \
            .order_by('-meeting__ts_start').first()

        if self.status.active_meeting and self.status.active_meeting != active_meeting:
            self.status.active_meeting.maybe_update_stats()

        if active_meeting:
            update_active_meeting = {}
            if not (self.status.head_count == active_meeting.head_count == None):
                update_active_meeting['head_count'] = max(active_meeting.head_count or 0, self.status.head_count or 0)
            if self.status.presence is not None:
                update_active_meeting['presence'] = active_meeting.presence or self.status.presence
            partial_update(active_meeting, update_active_meeting)

        self.set_status(active_meeting=active_meeting)

    def sync_bookings(self):

        return self.get_api().set_bookings([b.as_dict('html') for b in self.get_bookings()])

    def get_bookings(self):

        from meeting.models import Meeting
        return Meeting.objects.get_active().distinct().filter(endpoints=self)

    @classmethod
    def format_mac_address(cls, mac):
        if mac and ':' not in mac:
            return ':'.join(mac[i : i + 2] for i in range(0, 12, 2))
        return mac

    def backup(self, sync=True):

        if not sync and settings.ACTIVATE_CELERY:
            from . import tasks
            tasks.backup_endpoint.apply_async([self.pk])
            return

        from endpoint_backup.models import EndpointBackup
        obj = EndpointBackup.objects.create(endpoint=self, customer=self.customer)
        return self.get_api().backup(obj)

    def get_email_key(self):

        from emailbook.consts import RESERVED_USERNAMES

        if not self.title:
            return self.email_key or default_key()

        key = slugify(self.title)

        if key in RESERVED_USERNAMES:
            key = slugify('{} - {}'.format(self.customer, self.title))

        suffix = ''
        full_key = ''
        for _i in range(10):

            full_key = key + suffix

            suffix = '-' + default_key()[:4]

            if Endpoint.objects.exclude(pk=self.pk).filter(email_key=full_key):
                continue
            if EndpointSIPAlias.objects.exclude(endpoint=self.pk).filter(sip=full_key):
                continue
            for alias in EndpointSIPAlias.objects.exclude(endpoint=self.pk).filter(sip__startswith=full_key):
                if alias.sip.split('@')[0] == full_key:
                    continue

            return full_key

        raise ValueError('Could not find new key {}'.format(full_key))

    def change_email_key(self, new_key: str = None, last_key: str = None, commit=True):

        last_key = last_key or self.email_key
        self.email_key = new_key or self.get_email_key()
        if self.pk and last_key != self.email_key:
            EndpointSIPAlias.objects.get_or_create(endpoint=self, sip=last_key)

        if commit:
            self.save()

    def maybe_try_password(self, do_raise=False):
        if self.should_try_password:
            self.try_password(do_raise=do_raise)

    def try_password(self, do_raise=False):
        api = self.get_api()
        passwords = CustomerDefaultPassword.objects.filter(customer=self.customer).values_list('password', flat=True)

        if self.session_id:
            api.logout()

        for password in {''} | set(passwords):
            self.password = password
            try:
                api.get_status()  # TODO change to api.login() if it's possible for all endpoint versions
            except ResponseConnectionError:
                if do_raise:
                    raise
                return None
            except (AuthenticationError, ResponseError):
                self.session_id = 'basic'
            else:
                self.password = password
                self.save(update_fields=['password'])
                return password

        if do_raise:
            raise AuthenticationError('Could not match standard password')

        return None

    def save(self, *args, **kwargs):

        try:
            existing = self.pk and Endpoint.objects.get(pk=self.pk)
        except Endpoint.DoesNotExist:
            existing = None

        if existing:
            if existing.title != self.title:
                self.change_email_key(commit=False)
            if self.session_id and existing.password != self.password:
                try:
                    self.get_api().logout()
                except ResponseError:
                    pass

        if self.manufacturer in (consts.MANUFACTURER.OTHER,):
            self.connection_type = consts.CONNECTION.PASSIVE

        if self.api_port != 80:
            self.http_mode = HTTP_MODES.HTTPS

        if (not existing and self.title) or not self.email_key:
            self.change_email_key(commit=False)

        update_fields = list(
            kwargs.get('update_fields') or []
        )  # only used if already set in kwargs
        if update_fields and self.email_key and existing and existing.email_key != self.email_key:
            update_fields.append('email_key')
            kwargs['update_fields'] = update_fields

        if not self.event_secret_key:
            if existing and existing.event_secret_key:
                self.event_secret_key = existing.event_secret_key
            else:
                self.event_secret_key = default_key()
                update_fields.append('event_secret_key')

        if not self.pk and update_fields:  # dont work for new objects. really use update_fields?
            kwargs.pop('update_fields', None)


        super().save(*args, **kwargs)

        all_endpoint_secrets.cache.clear()
        all_endpoint_uris.cache.clear()

        try:
            self.status.status
        except Exception:
            self.status = EndpointStatus.objects.get_or_create(endpoint=self)[0]

    def __str__(self):
        return self.title or self.hostname or self.ip or ''

    def get_absolute_url(self):
        return '/epm/endpoint/{}/?customer={}'.format(self.pk, self.customer_id)

    def get_feedback_url(self):
        c_settings = CustomerSettings.objects.get_for_customer(self.customer_id)

        if settings.EPM_EVENT_ENDPOINT_SECRET:
            return 'https://{}/tms/event/{}/{}/'.format(
                settings.EPM_HOSTNAME, c_settings.secret_key, self.event_secret_key
            )

        return 'https://{}/tms/event/{}/'.format(settings.EPM_HOSTNAME, c_settings.secret_key)

    def get_provision_path(self):
        c_settings = CustomerSettings.objects.get_for_customer(self.customer_id)
        return c_settings.get_provision_path(self.event_secret_key)

    def get_provision_url(self):
        return 'https://{}{}'.format(settings.EPM_HOSTNAME, self.get_provision_path())

    def get_document_path(self):
        c_settings = CustomerSettings.objects.get_for_customer(self.customer_id)
        return c_settings.get_document_path(self.event_secret_key)

    def get_document_url(self):
        return 'https://{}{}'.format(settings.EPM_HOSTNAME, self.get_document_path())

    def get_external_manager_url(self):
        if self.external_manager_service:
            return self.external_manager_service
        c_settings = CustomerSettings.objects.get_for_customer(self.customer_id)
        return c_settings.external_manager_service or ''

    @property
    def software_version_tuple(self) -> Tuple[int, int]:
        """
        return tuple with (major_version, minor_version_two_digits) without software
        family prefix (tc, ce, ...)
        """
        if not self.status.software_version:
            return (0, 0)
        parts = re.sub(r'^[A-z][A-z](\d+)', r'\1', self.status.software_version).split('.', 2)
        try:
            return (int(parts[0]), int(parts[1][:2]))
        except ValueError:
            return (0, 0)

    @property
    def supports_webrtc(self):
        return self.software_version_tuple >= (9, 14)

    @property
    def supports_teams(self):
        return self.supports_webrtc and self.webex_registration

    @property
    def is_active(self) -> True:
        """
        Decrease passive provision heartbeat if this system been specifically requested recently
        """
        if not self.status.ts_last_opened:
            return False
        return (now() - self.status.ts_last_opened).total_seconds() < 5 * 60


class EndpointSIPAlias(models.Model):

    endpoint = models.ForeignKey(Endpoint, on_delete=models.CASCADE, related_name='sip_aliases')
    sip = models.CharField(max_length=200)

    def __str__(self):
        return self.sip


class EndpointMeetingParticipant(models.Model):

    endpoint = models.ForeignKey(Endpoint, on_delete=models.CASCADE, related_name='+')
    meeting = models.ForeignKey('meeting.Meeting', on_delete=models.CASCADE, related_name='+')

    head_count = models.IntegerField(null=True)
    air_quality = models.SmallIntegerField(null=True)
    presence = models.BooleanField(null=True, default=False)
    ts_connected = models.DateTimeField(null=True)

    def maybe_update_stats(self):
        from room_analytics.models import (
            EndpointAirQuality,
            EndpointHeadCount,
            EndpointRoomPresence,
        )

        update = {
            'head_count': EndpointHeadCount.objects.get_for_time(
                self.endpoint, self.meeting.ts_start, self.meeting.ts_stop
            ),
            'presence': EndpointRoomPresence.objects.get_for_time(
                self.endpoint, self.meeting.ts_start, self.meeting.ts_stop
            ),
            'air_quality': EndpointAirQuality.objects.get_for_time(
                self.endpoint, self.meeting.ts_start, self.meeting.ts_stop
            ),
        }
        partial_update(self, update)

    @property
    def meeting_status(self):
        if not self.meeting_id:
            return MeetingStatus.NO_MEETING

        if self.ts_connected:
            return MeetingStatus.CONNECTED

        if self.meeting.ts_start < now() - timedelta(minutes=GHOST_TIMEOUT):
            return MeetingStatus.GHOST_MEETING


class EndpointStatus(models.Model):

    endpoint = models.OneToOneField(Endpoint, on_delete=models.CASCADE, related_name='status', unique=True)
    status = models.SmallIntegerField(choices=tuple((s.value, s.name) for s in STATUS), default=STATUS.CONNECTION_ERROR)

    software_version = models.CharField(max_length=100)
    software_release = models.DateField(null=True)
    has_warnings = models.BooleanField(default=False)

    uptime = models.IntegerField(default=0)
    head_count = models.SmallIntegerField(null=True, blank=True)
    temperature = models.SmallIntegerField(null=True, blank=True)
    humidity = models.SmallIntegerField(null=True, blank=True)
    air_quality = models.SmallIntegerField(null=True, blank=True)
    presence = models.BooleanField(null=True)
    active_meeting = models.ForeignKey('EndpointMeetingParticipant', null=True, on_delete=models.SET_NULL)

    ts_last_opened = models.DateTimeField(null=True, blank=True)
    ts_last_check = models.DateTimeField(null=True, blank=True)
    ts_last_online = models.DateTimeField(null=True, blank=True)
    ts_last_provision = models.DateTimeField(null=True, blank=True)
    ts_last_provision_document = models.DateTimeField(null=True, blank=True)
    ts_last_event = models.DateTimeField(null=True, blank=True)
    ts_last_head_count = models.DateTimeField(null=True, blank=True)
    ts_last_presence = models.DateTimeField(null=True, blank=True)


class CustomerSettingsManager(models.Manager['CustomerSettings']):
    def get_for_customer(self, customer: Union[Customer, int]):
        return self.customer_settings(customer if isinstance(customer, int) else customer.pk)

    @staticmethod
    @fifo_memoize(100, ttl=5)
    def customer_settings(customer_id: int):
        customer = Customer.from_db(CustomerSettings.objects.db, ['id'], [customer_id])
        try:
            result = CustomerSettings.objects.get(customer=customer)
        except CustomerSettings.DoesNotExist:
            with transaction.atomic():
                Customer.objects.select_for_update(of=('self',)).only('id').get(pk=customer_id)
                result = CustomerSettings.objects.get_or_create(customer=customer)[0]
        return result


class CustomerSettings(models.Model):

    PROTOCOLS = (
        ('SIP', 'SIP'),
        ('H323', 'H323'),
        ('H320', 'H320'),
        ('Spark', _('Spark')),
    )

    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, editable=False, related_name='epm_settings')
    booking_time_before = models.IntegerField(_('Visa bokning före möte, antal minuter'), default=5)
    dial_protocol = models.CharField(max_length=100, choices=tuple((d.value, d.name) for d in DIAL_PROTOCOL), default="SIP", blank=True)

    default_branding_profile = models.ForeignKey('endpoint_branding.EndpointBrandingProfile', blank=True,
                                                 null=True, on_delete=models.SET_NULL)

    default_address_book = models.ForeignKey(
        'address.AddressBook', null=True, blank=True, on_delete=models.SET_NULL
    )
    default_portal_address_book = models.ForeignKey(
        'address.AddressBook',
        verbose_name=_('Standard adressbok för portalenbokningar'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        editable=settings.ENABLE_CORE,
    )
    default_proxy = models.ForeignKey(
        'endpointproxy.EndpointProxy', null=True, blank=True, on_delete=models.SET_NULL
    )
    use_standard_password = models.BooleanField(_('Försök skapa aktiv anslutning'), default=False)
    http_feedback_slot = models.SmallIntegerField(_('HTTP Feedback Slot'), default=4)

    sip_proxy = models.CharField(max_length=255, blank=True)
    sip_proxy_username = models.CharField(max_length=255, blank=True)
    sip_proxy_password = models.CharField(max_length=255, blank=True)
    h323_gatekeeper = models.CharField(max_length=255, blank=True)

    ca_certificates = models.TextField(blank=True)

    enable_obtp = models.BooleanField(default=True, blank=True)
    external_manager_service = models.URLField(max_length=255, blank=True)

    enable_user_debug_statistics = models.BooleanField(default=False, blank=True)

    secret_key = models.CharField(
        _('Nyckel för events'), max_length=100, default=new_customer_secret, null=True, unique=True
    )
    proxy_password = models.CharField(
        _('Nyckel för proxy-klienter'),
        max_length=100,
        default=new_proxy_secret if settings.EPM_REQUIRE_PROXY_PASSWORD else None,
        null=True,
        blank=True,
        unique=True,
    )

    night_first_hour = models.SmallIntegerField(_('Första timme för nattetid'), default=23)
    night_last_hour = models.SmallIntegerField(_('Sista timme för nattetid'), default=4)

    _override_localtime = None

    objects = CustomerSettingsManager()

    @property
    def provision_path(self):
        return '/tms/{}/'.format(self.secret_key)

    def get_provision_path(self, endpoint_secret=None):
        if endpoint_secret:
            return '{}{}/'.format(self.provision_path, endpoint_secret)
        return self.provision_path

    @property
    def document_path(self):
        return '/tms/document/{}/'.format(self.secret_key)

    def get_document_path(self, endpoint_secret=None):
        if endpoint_secret:
            return '{}{}'.format(self.document_path, endpoint_secret)
        return self.document_path

    def save(self, *args, **kwargs):
        if not self.secret_key:
            self.secret_key = new_customer_secret()
        super().save(*args, **kwargs)

    @classmethod
    def get_hour(cls, ts: datetime = None, timezone=None):
        if not ts:
            ts = cls._override_localtime or now()

        if isinstance(timezone, str):
            try:
                timezone = pytz.timezone(timezone)
            except Exception:
                timezone = None

        return localtime(ts, timezone=timezone).replace(minute=0, second=0, microsecond=0)

    def is_night(self, ts: datetime = None, timezone=None):
        ts = self.get_hour(ts=ts, timezone=timezone)

        if self.night_last_hour < self.night_first_hour:
            if ts.hour <= self.night_last_hour or ts.hour >= self.night_first_hour:
                return True
        elif self.night_first_hour <= ts.hour <= self.night_last_hour:
            return True

        return False

    def get_next_night_end(self, ts: datetime = None, timezone=None):
        ts = self.get_hour(ts, timezone=timezone)

        # past 00:00
        if self.night_last_hour < self.night_first_hour:
            if ts.hour <= self.night_last_hour:
                return ts.replace(hour=self.night_last_hour) + timedelta(hours=1)

        elif ts.hour <= self.night_last_hour:
            return ts.replace(hour=self.night_last_hour) + timedelta(hours=1)

        # next day
        return (ts + timedelta(days=1)).replace(hour=self.night_last_hour)

    def get_next_night_start(self, ts=None, timezone=None):
        ts = self.get_hour(ts, timezone=timezone)

        if ts.hour < self.night_first_hour:
            return ts.replace(hour=self.night_first_hour)

        # next day
        return (ts + timedelta(days=1)).replace(hour=self.night_first_hour)


class CustomerDefaultPassword(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, editable=False)
    index = models.SmallIntegerField(default=0, null=True)
    password = models.CharField(max_length=100)

    class Meta:
        ordering = ('index',)


class CustomerAutoRegisterIpNetManager(models.Manager['CustomerAutoRegisterIpNet']):

    def get_for_ip(self, ip, customer=None):

        customer_id = getattr(customer, 'pk', customer) if customer else None

        for net in self.get_queryset():
            if net.contains(ip) and (not customer_id or net.customer_id == customer_id):
                return net

        return None


class CustomerAutoRegisterIpNet(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, editable=False)
    index = models.SmallIntegerField(default=0, null=True)
    ip_net = models.CharField(max_length=100)

    objects = CustomerAutoRegisterIpNetManager()

    def __str__(self):
        return self.ip_net

    def contains(self, ip):

        from ipaddress import IPv4Interface
        return IPv4Interface(ip).ip in IPv4Interface(self.ip_net).network


class CustomerDomain(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, editable=False)
    domain = models.CharField(max_length=100)


def clear_cache(sender, **kwargs):

    CustomerSettingsManager.customer_settings.cache.clear()


models.signals.post_save.connect(clear_cache, sender=Customer)
models.signals.post_save.connect(clear_cache, sender=CustomerSettings)
