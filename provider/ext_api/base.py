import json
import logging
from contextlib import contextmanager
from datetime import timedelta
from random import choice
from time import sleep, time
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Tuple, TypeVar, Union

import requests
from django.conf import settings
from django.utils.encoding import force_text
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from sentry_sdk import capture_exception

from provider.types import ProviderAPICompatible
from shared.exceptions import format_exception
from shared.utils import maybe_update

from ..exceptions import (
    AuthenticationError,
    DuplicateError,
    InvalidSSLError,
    NotFound,
    ProxyError,
    ResponseConnectionError,
    ResponseError,
    ResponseTimeoutError,
)

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from customer.models import Customer
    from meeting.models import Meeting
    from provider.models.provider import Cluster


class APIInstanceCache:

    allow_cached_values = None
    use_cached_values = None


class RestProviderAPI:

    verify_certificate = False
    connection_error_count = 0
    error_503_count = 0
    override_post = None
    request_callback = None
    session = None
    host: str

    customer: 'Customer'
    provider: ProviderAPICompatible
    cluster: 'Cluster'
    _cache: APIInstanceCache

    def __init__(self, provider: ProviderAPICompatible, customer=None, allow_cached_values=None):

        if isinstance(provider, RestProviderAPI):
            raise ValueError('provider should not be API instance')

        if getattr(provider, 'is_cluster', False):
            from provider.models.provider import Cluster
            self.cluster = Cluster.get_provider_cluster(provider)
            try:
                provider = choice(provider.get_clustered())
            except IndexError:
                pass
        else:
            self.cluster = provider.cluster if getattr(provider, 'cluster_id', None) else provider

        self.provider = provider
        self.customer = customer
        self.host = provider.api_host or provider.ip or provider.hostname
        self._cache = APIInstanceCache()

    @property
    def ip(self):  # deprecated
        return self.host

    def get_session(self, **kwargs):
        session = requests.Session()
        for k, v in kwargs.items():
            setattr(session, k, v)
        session.verify = self.verify_certificate
        return session

    def get_tenant_id(self, customer=None):
        return ''

    def request(self, url, *args, **kwargs) -> requests.Response:
        method = kwargs.pop('method', None)
        raw_url = kwargs.pop('raw_url', None)

        if not self.session:
            self.session = self.get_session()

        override_function = getattr(self, 'override_post', None)
        if override_function:
            return override_function(url, method=method, *args, **kwargs)

        if method == 'DELETE':
            request_fn = self.session.delete
        elif method == 'PUT':
            request_fn = self.session.put
        elif method == 'PATCH':
            request_fn = self.session.patch
        elif method == 'GET':
            request_fn = self.session.get
        else:
            request_fn = self.session.post

        self.login()
        params = kwargs.pop('params', None) or {}
        params.update(self.get_params())

        self.update_request_kwargs(kwargs)

        if params:
            kwargs['params'] = params

        kwargs.setdefault('timeout', (20, 20 * 60))  # DEFAULT TIMEOUT
        if isinstance(kwargs['timeout'], int):
            if kwargs['timeout'] < 10:
                kwargs['timeout'] = (3.06, kwargs['timeout'])
            else:
                kwargs['timeout'] = (6.06, kwargs['timeout'])

        start_time = time()
        _log = self._error_log

        real_url = self.get_url(url)
        if raw_url == True:
            real_url = url

        result = None

        try:
            logger.debug(
                '{} starting HTTPS request to %s'.format(self.__class__.__name__), real_url
            )
            
            result = request_fn(real_url, *args, **kwargs)
            
            if result.status_code == 503 and self.error_503_count < 5:  # TODO track reccuring errors over threads?
                logger.info(
                    '{} got HTTP 503 in %s. Trying again'.format(
                        self.__class__.__name__,
                    ),
                    time() - start_time,
                )
                self.error_503_count += 1
                if not settings.TEST_MODE:
                    sleep(.2)
                result = request_fn(real_url, *args, **kwargs)

            try:
                self._trace_log_request(url, result)
            except Exception:
                if settings.DEBUG or settings.TEST_MODE:
                    raise
                capture_exception()

            try:
                self.check_response_errors(result)
            except Exception as e:
                _log(e, real_url)
                logger.info(
                    '{} request %s %s resulted in an error: %s, %s'.format(
                        self.__class__.__name__,
                    ),
                    method,
                    url,
                    format_exception(e),
                    time() - start_time,
                )
                raise
            else:
                logger.debug(
                    '{} finished HTTPS request to %s in %ss'.format(self.__class__.__name__),
                    real_url,
                    time() - start_time,
                )
            result.encoding = 'utf-8'  # FIXME
            return result
        except AuthenticationError:
            logger.warning('Session not valid anymore, was %s with expiry %s for %s (id %s)' % (self.provider.session_id, self.provider.session_expires, self.provider, self.provider.pk))
            self.login(force=True)
            params.update(self.get_params())
            self.update_request_kwargs(kwargs)
            result = request_fn(real_url, verify=self.verify_certificate, *args, **kwargs)
            try:
                self.check_response_errors(result)
            except Exception as e:
                logger.warning('Session was not updated (%s), was %s with expiry %s for %s (id %s)' % (e, self.provider.session_id, self.provider.session_expires, self.provider, self.provider.pk))
                raise
            result.encoding = 'utf-8'  # FIXME
            return result
        except requests.exceptions.SSLError as e:
            _log(e, real_url)
            raise InvalidSSLError('SSL error', e)
        except requests.exceptions.ProxyError as e:
            _log(e, real_url)
            raise ProxyError('Proxy error', e)
        except requests.exceptions.Timeout as e:
            _log(e, real_url)
            raise ResponseTimeoutError(e)
        except ValueError as e:  # reraise requests error from invalid input
            _log(e, real_url)
            raise
        except requests.exceptions.RequestException as e:
            _log(e, real_url)
            raise ResponseConnectionError(e)
        except Exception as e:
            _log(e, real_url)
            raise
        finally:
            if self.request_callback:
                self.request_callback(self, url, result)

    def get(self, url: str, *args, **kwargs):
        return self.request(url, *args, method='GET', **kwargs)

    def post(self, url: str, data: Union[None, Dict, str, bytes] = None, *args, **kwargs):
        return self.request(url, data=data, *args, method='POST', **kwargs)

    def put(self, url: str, *args, **kwargs):
        return self.request(url, *args, method='PUT', **kwargs)

    def patch(self, url: str, *args, **kwargs):
        return self.request(url, *args, method='PATCH', **kwargs)

    def delete(self, url: str, *args, **kwargs):
        return self.request(url, *args, method='DELETE', **kwargs)

    def login(self, force=False):
        pass

    def update_request_kwargs(self, kwargs):
        return

    def get_base_url(self):
        if not self.host:
            raise ResponseConnectionError('No ip/hostname/api host provided')
        return 'https://%s' % self.host

    def get_url(self, path):
        return '%s/%s' % (self.get_base_url(), path.lstrip('/'))

    def check_response_errors(self, response):
        self.check_login_status(response)

    def check_login_status(self, response):
        return True

    def get_params(self):
        return {}

    def _get_trace_log_relations(self) -> dict:

        related_objects = {}

        if getattr(self, 'endpoint', None):
            related_objects['endpoint'] = self.endpoint  # type: ignore
            related_objects['endpoint_task'] = self.active_task  # type: ignore
        else:
            related_objects['cluster'] = self.cluster
            related_objects['provider'] = self.provider

        related_objects['customer'] = self.customer
        return related_objects

    def _check_trace_log_active(self, related_objects=None) -> bool:
        from tracelog.models import ActiveTraceLog

        active_trace = ActiveTraceLog.objects.get_active()

        if related_objects is None:
            related_objects = self._get_trace_log_relations()

        is_active = bool({0, self.customer.pk} & active_trace.get('everything', set()))
        for k in related_objects:
            if active_trace.get(k) and getattr(related_objects[k], 'pk', None) in active_trace:
                return True

        return is_active

    def _trace_log_request(self, url: str, response: requests.Response, **kwargs):

        from tracelog.models import TraceLog

        objects = self._get_trace_log_relations()
        if not self._check_trace_log_active(objects):
            return

        kwargs.update(objects)

        if '?' in response.request.url:
            query = response.request.url.split('?', 1)[1]
        else:
            query = ''

        return TraceLog.objects.store(
            content=response.content,
            url_base=url,
            request_body=force_text(response.request.body) if response.request.body else '',
            request_params=query,
            response_status_code=response.status_code,
            response_location=response.headers.get('Location'),
            method=response.request.method,
            **kwargs,
        )

    def _error_log(self, e: Exception, url: str):
        from debuglog.models import ErrorLog
        from endpoint.ext_api.base import EndpointProviderAPI

        if isinstance(e, ResponseConnectionError) and self._check_trace_log_active():
            from tracelog.models import TraceLog

            TraceLog.objects.store(
                content={
                    'error': format_exception(e),
                },
                url_base=url,
            )

        if isinstance(self, EndpointProviderAPI):
            if isinstance(e, (requests.exceptions.ConnectionError,)):
                return  # ignore connection errors - too many

        ErrorLog.objects.store(
            title='Http request to %s resulted in an error' % url,
            type=self.__class__.__name__,
            url=url,
            content=repr(e),
            customer=self.customer,
            endpoint=getattr(self, 'endpoint', None),
        )

    def error(self, content, response=None, extra=None):

        try:
            return self._raise_error(content, response=response, extra=extra)
        except Exception as e:
            from debuglog.models import ErrorLog

            request = response.request if response is not None else None

            ErrorLog.objects.store(
                title=content if request and content else 'Http request resulted in an error',
                type=self.__class__.__name__,
                url=request.url if request else '',
                method=request.method if request else '',
                content=repr(e),
                customer=self.customer,
                **({'extra': extra} if extra else {}),
            )
            raise

    def _raise_error(self, content, response=None, extra=None):
        if response is None and hasattr(content, 'status_code'):
            response = content
            content = response.text

        extra = (extra,) if extra else ()
        if response is not None:
            if response.status_code == 404:
                raise NotFound(response.text, response, *extra)
            self.check_response_errors(response)
            if response.status_code == 401:
                raise AuthenticationError(_('Authentication failed.'), response, *extra)

        raise ResponseError(content, response, *extra)


class BookMeetingProviderAPI(RestProviderAPI):

    def dialout(self, meeting: 'Meeting', dialout):
        raise NotImplementedError()

    def notify(self, meeting: 'Meeting', message: str):
        return NotImplemented

    def book(self, meeting: 'Meeting', uri: str = None):
        raise NotImplementedError()

    def update_meeting_settings(self, meeting: 'Meeting', data: Mapping[str, Any]):
        if data.get('title'):
            meeting.title = data['title']
        if data.get('recording'):
            meeting.recording = data['recording']
        if data.get('room_info'):
            meeting.room_info = data['room_info']
        if data.get('layout'):
            meeting.layout = data['layout']
        if data.get('ts_start'):
            meeting.ts_start = data['ts_start']
        if data.get('ts_stop'):
            meeting.ts_stop = data['ts_stop']
        if data.get('recurring_exceptions'):
            if meeting.recurring_master_id:
                meeting.recurring_master.recurring_exceptions = data['recurring_exceptions']
                meeting.recurring_master.save()
        if data.get('password'):
            meeting.password = data['password']
        if data.get('moderator_password'):
            meeting.moderator_password = data['moderator_password']

    def rebook(self, meeting: 'Meeting', new_data: Mapping[str, Any]):
        self.update_meeting_settings(meeting, new_data)
        return meeting

    def book_unprotected_access(self, meeting):
        raise NotImplementedError()

    def unbook(self, meeting):
        raise NotImplementedError()

    def check_status(self, meeting):
        raise NotImplementedError()

    def close_call(self, meeting: 'Meeting', dialout):
        raise NotImplementedError()

    def get_info(self, meeting):
        raise NotImplementedError()

    def set_layout(self, meeting: 'Meeting', new_layout):
        raise NotImplementedError()

    @staticmethod
    def unbook_expired():
        from customer.models import Customer
        from meeting.models import Meeting
        from provider.models.provider import Cluster

        for cluster in Cluster.objects.filter(type__in=Cluster.MCU_TYPES):
            Meeting.objects.unbook_expired(cluster.get_api(Customer.objects.first()))

    def unbook_webinar(self, meeting, webinar):
        raise NotImplementedError()

    def webinar(self, meeting):
        raise NotImplementedError()


TCallControlProvider = TypeVar('TCallControlProvider', bound='ReadOnlyCallControlProvider')


class ReadOnlyCallControlProvider(RestProviderAPI):

    def get_call_leg(self, call_leg_id) -> Dict:
        raise NotImplementedError()

    def get_call_legs(self, call_id=None, cospace=None, filter=None, tenant=None, limit=None) \
        -> Tuple[List[Dict], int]:
        raise NotImplementedError()

    def get_call(self, call_id, cospace=None, include_legs=False, include_participants=False) \
        -> Dict:
        raise NotImplementedError()

    def get_calls(self, include_legs=False, include_participants=False, filter=None, cospace=None, limit=None,
                  tenant=None, offset=0) -> Tuple[List[Dict], int]:
        raise NotImplementedError()

    def get_clustered_call_leg(self, leg_id) \
        -> Tuple[Dict, RestProviderAPI]:
        raise NotImplementedError()

    def get_clustered_call_legs(
        self,
        call_id: str = None,
        cospace: str = None,
        filter: Union[str, Dict[str, Any]] = None,
        tenant: str = None,
        limit: int = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError()

    def get_clustered_call(self, call_id, cospace=None, include_legs=False, include_participants=False) \
        -> List[Tuple[Dict, 'TCallControlProvider']]:
        raise NotImplementedError()

    def get_clustered_calls(self, include_legs=False, include_participants=False, filter=None, cospace=None, limit=None,
                            tenant=None, offset=0) -> Tuple[List[Dict], int]:
        raise NotImplementedError()

    def get_clustered_participant_count(self, *args, **kwargs):
        raise NotImplementedError()

    def get_clustered_participants(self, call_id=None, cospace=None, filter=None, tenant=None,
                                   limit=None, only_count=False) -> Tuple[List[Dict], int]:
        raise NotImplementedError()

    def get_active_legs(self, participants=None, only_should_count_stats=False, until=None):
        from statistics.models import Leg
        legs = Leg.objects.filter(server__cluster=self.cluster,
                                  ts_start__gt=now() - timedelta(days=7),
                                  ts_start__lt=until or now() - timedelta(minutes=10),
                                  ts_stop__isnull=True,
                                  should_count_stats=True)

        if only_should_count_stats:
            legs = legs.filter(should_count_stats=only_should_count_stats)

        return legs

    def reset_stopped_statistics_legs(self, removed_guids=None, ts=None):

        legs = self.get_active_legs(only_should_count_stats=False, until=ts)

        if removed_guids is None:
            participants = self.get_clustered_call_legs()
            guids = {guid for p in participants for guid in {p.get('call_uuid'), p.get('id')} if guid}
            removed_guids = legs.exclude(guid__in=guids).values_list('guid', flat=True)

        ts_stop = ts or now() - timedelta(minutes=3)
        count = 0
        for leg in legs.filter(guid__in=removed_guids):
            maybe_update(leg, {'ts_stop': ts_stop, 'duration': ts_stop - (leg.ts_start or ts_stop)})
            count += 1
        logger.warning(
            'Reset %s calls thats not still connected for cluster %s', count, self.cluster
        )

    def get_participants(self, call_id=None, cospace=None, filter=None, tenant=None, only_internal=True,
                         limit=None)  -> Tuple[List[Dict], int]:
        raise NotImplementedError()

    def get_sip_uri(self, uri=None, cospace=None):
        raise NotImplementedError()

    def get_web_url(self, alias=None, passcode=None, cospace=None):
        raise NotImplementedError()


class DistributedReadOnlyCallControlProvider(ReadOnlyCallControlProvider):
    """
    Returns all distributed calls from the same API endpoint
    """

    def get_clustered_calls(self, *args, **kwargs) -> Tuple[List[Dict], int]:

        return self.get_calls(*args, **kwargs)

    def get_clustered_participant_count(self, *args, **kwargs) -> int:
        return self.get_participants(limit=1, only_internal=True)[1]

    def get_clustered_participants(self, call_id=None, cospace=None, filter=None, tenant=None,
                                   limit=None, only_count=False) -> Tuple[List[Dict], int]:

        return self.get_participants(call_id=call_id, cospace=cospace, filter=filter, tenant=tenant,
                                       limit=limit, only_internal=True)

    def get_clustered_call(self, call_id, cospace=None, include_legs=False, include_participants=False):

        call = self.get_call(call_id, cospace=cospace, include_legs=include_legs, include_participants=include_participants)
        return [(call, self)]

    def get_clustered_call_legs(
        self,
        call_id: str = None,
        cospace: str = None,
        filter: Union[str, Dict[str, Any]] = None,
        tenant: str = None,
        limit: int = None,
    ) -> List[Dict[str, Any]]:
        return self.get_participants(call_id, cospace=cospace, filter=filter, tenant=tenant, limit=limit)[0]

    def get_clustered_call_leg(self, leg_id):

        if not leg_id:
            raise ValueError('Empty leg id')

        return self.get_call_leg(leg_id), self


class CallControlProvider(ReadOnlyCallControlProvider):

    def add_call_leg(self, call_id, remote, **data):
        raise NotImplementedError()

    def add_call(self, cospace, name=None):
        raise NotImplementedError()

    def add_participant(self, call_id, remote, layout=None, call_leg_profile=None):
        raise NotImplementedError()

    def update_call_leg(self, leg_id, data):
        raise NotImplementedError()

    def update_call_participants(self, call_id, data):
        raise NotImplementedError()

    def update_call(self, call_id, data):
        raise NotImplementedError()

    def set_all_participant_mute(self, call_id, value=True):
        raise NotImplementedError()

    def set_all_participant_video_mute(self, call_id, value=True):
        raise NotImplementedError()

    def set_participant_moderator(self, leg_id, value=True):
        raise NotImplementedError()

    def set_participant_mute(self, leg_id, value=True):
        raise NotImplementedError()

    def set_participant_video_mute(self, leg_id, value=True):
        raise NotImplementedError()

    def set_call_lock(self, call_id, value=True):
        raise NotImplementedError()

    def hangup_call(self, call_id):
        raise NotImplementedError()

    def hangup_call_leg(self, call_leg_id):
        return self.hangup_participant(call_leg_id)

    def hangup_participant(self, participant_id):
        raise NotImplementedError()


class StatusProvider:
    def get_status(self, timeout=None):
        raise NotImplementedError()

    def get_licenses(self):  # ?
        raise NotImplementedError()

    def get_load(self):  # ?
        raise NotImplementedError()

    def get_alarms(self):
        raise NotImplementedError()


class MCUProvider(StatusProvider, CallControlProvider, RestProviderAPI):

    @property
    def tenant_id(self):
        return self.get_tenant_id(self.customer)

    def get_tenant_id(self, customer=None):
        if customer is None:
            customer = self.customer

        if customer.lifesize_provider_id in {self.cluster.pk, self.provider.pk}:
            customer_provider = self.cluster
        else:
            customer_provider = customer.get_provider()

        if customer_provider and customer_provider.is_pexip:
            return customer.get_pexip_tenant_id()
        if customer_provider and customer_provider.is_acano:
            return customer.acano_tenant_id
        return ''

    def add_cospace_accessmethod(self, cospace_id, data, try_increase=False):
        raise NotImplementedError()

    def add_cospace(self, data, creator='', try_increase_number=False, sync=True):
        raise NotImplementedError()

    def add_member(self, cospace_id, user_jid, can_add_remove_members=False, can_remove_self=False, ):
        raise NotImplementedError()

    def delete_cospace(self, cospace_provider_ref):
        raise NotImplementedError()

    def find_cospaces(self, q, offset=0, limit=10, tenant=None, org_unit=None):
        raise NotImplementedError()

    def find_user(self, user_id, tenant=None):
        raise NotImplementedError()

    def find_users(self, q, offset=0, limit=10, tenant=None, org_unit=None, include_user_data=False):
        raise NotImplementedError()

    def get_cospace_accessmethods(self, cospace_id, include_data=False):
        raise NotImplementedError()

    def get_cospace(self, cospace_id):
        raise NotImplementedError()

    def get_internal_domains(self, clear=False):
        raise NotImplementedError()

    @classmethod
    def get_lookup_cospace(cls, call_id):
        raise NotImplementedError()

    def get_members(self, cospace_id, include_permissions=True, include_user_data=False, tenant=None):
        raise NotImplementedError()

    def get_secret_for_access_method(self, cospace_id, access_method_id):
        raise NotImplementedError()

    def get_tenant(self, conference_name=None, obj=None, conference_id=None):  # ?
        raise NotImplementedError()

    def get_tenants(self):
        raise NotImplementedError()

    def get_url_for_access_method(self, cospace_id, access_method_id):
        raise NotImplementedError()

    def get_user_cospaces(self, user_id, include_cospace_data=False):
        raise NotImplementedError()

    def get_user_private_cospace(self, user_id):
        raise NotImplementedError()

    def get_user(self, user_id):
        raise NotImplementedError()

    def _iter_all_cospaces(self, tenant_id=None, filter=''):
        raise NotImplementedError()

    def _iter_all_users(self, **filter):
        raise NotImplementedError()

    def lobby_pin(self, cospace_id, moderator_pin):
        raise NotImplementedError()

    def notify(self, meeting, message):
        raise NotImplementedError()

    def remove_member(self, cospace_id, member_id):
        raise NotImplementedError()

    def set_cdr_settings(self, server=None):
        raise NotImplementedError()

    def set_cospace_stream_urls(self, get_key_callback, tenant_id=''):  # ?
        raise NotImplementedError()

    def set_cospace_tenant(self, cospace_id, tenant_id):
        raise NotImplementedError()

    def sync_ldap(self, ldap_id=None, tenant_id=None):  # ?
        raise NotImplementedError()

    def update_cospace(self, cospace_id, data):
        raise NotImplementedError()

    def update_member(self, cospace_id, member_id, **kwargs):
        raise NotImplementedError()

    USE_CURRENT_CUSTOMER = object()

    def get_settings(self, customer=USE_CURRENT_CUSTOMER):
        if customer is not None:
            customer = self.customer if customer is self.USE_CURRENT_CUSTOMER else customer
        from provider.models.provider import ClusterSettings
        return ClusterSettings.objects.get_for_cluster(self.cluster, customer)

    def get_static_room_number_range(self):
        from numberseries.models import NumberRangeDummy
        try:
            return self.get_settings().get_static_room_number_range()
        except AttributeError:
            return NumberRangeDummy()

    def get_scheduled_room_number_range(self):
        from numberseries.models import NumberRangeDummy
        try:
            return self.get_settings().get_scheduled_room_number_range()
        except AttributeError:
            return NumberRangeDummy()


class ProviderAPI(RestProviderAPI):

    # Is this provider currently syncing data to local database
    is_syncing = False

    # Use false if single user/cospace (using id) always should be updated:
    _use_cache_for_single_objects = False  # Note: overrided by some providers

    def __init__(self, provider=None, customer=None, allow_cached_values=None):

        super().__init__(provider=provider, customer=customer)

        self.customer = customer
        self.allow_cached_values = allow_cached_values

        self.verify_certificate = customer.verify_certificate if customer else False  # TODO
        for verify in [
            getattr(provider, 'verify_certificate', None),
            getattr(self.cluster, 'verify_certificate', None),
            getattr(customer, 'verify_certificate', None),
        ]:
            if verify is not None:
                self.verify_certificate = verify
                break

    @property
    def allow_cached_values(self):
        return self._cache.allow_cached_values

    @allow_cached_values.setter
    def allow_cached_values(self, value):

        self._cache.allow_cached_values = value
        self._cache.use_cached_values = None if value else False

    @property
    def use_cached_values(self):
        if not self.allow_cached_values:
            return False

        if self._cache.use_cached_values is not None:
            return self._cache.use_cached_values

        if self.allow_cached_values:
            from datastore.models.base import ProviderSync

            has_cached = ProviderSync.check_has_cached_values(self.cluster.id)
            cluster_allow = self.cluster.use_local_database if self.cluster else True

            self._cache.use_cached_values = has_cached and cluster_allow

        return self._cache.use_cached_values

    @property
    def use_call_cache(self):
        return self.allow_cached_values and self.has_cdr_events

    @property
    def use_cache_for_single_objects(self):
        if self.is_syncing:
            return False
        return self.allow_cached_values and self._use_cache_for_single_objects

    @property
    def has_cdr_events(self):
        if not self.cluster:
            return False

        return self.cluster.has_cdr_events and self.cluster.use_local_call_state

    @contextmanager
    def disable_cache(self):
        old_allow, old_use = self._cache.allow_cached_values, self._cache.use_cached_values
        self._cache.allow_cached_values = False
        self._cache.use_cached_values = False
        yield
        self._cache.allow_cached_values = old_allow
        self._cache.use_cached_values = old_use

    def find_free_number_request(self, url, data, fields=('callId',), method='POST'):
        'send data and try to increase number in case of duplicate error'

        def _request(data):
            try:
                method_fn = getattr(self, method.lower())
                response = method_fn(url, data)
            except DuplicateError as e:
                return False, e
            except ResponseError:
                raise  # other error

            return True, response

        inc_data = data.copy()
        result = None
        for i in range(20):

            unique, result = _request(inc_data)
            if unique:
                return result, inc_data

            for f in fields:
                inc_data[f] = str(int(inc_data[f]) + i + 1)

        raise result

    def clone_api(self, new_provider):
        api = new_provider.get_api(self.customer, allow_cached_values=self.allow_cached_values)
        api._cache = self._cache
        api.is_syncing = api.is_syncing
        return api

    def iter_clustered_provider_api(self, only_call_bridges=True):

        providers = self.provider.get_clustered(include_self=True, only_call_bridges=only_call_bridges)

        has_enabled = False
        last_not_enabled = None  # return only enabled, except for when all providers as disabled

        for provider in sorted(providers, key=lambda p: p.id):
            if provider.pk == self.provider.pk:
                if provider.enabled:
                    yield self
                    has_enabled = True
                else:
                    last_not_enabled = self
                continue

            api = self.clone_api(provider)
            if provider.enabled:
                yield api
                has_enabled = True
            else:
                last_not_enabled = api

        if not has_enabled and last_not_enabled:
            yield last_not_enabled


    @staticmethod
    def run_threaded(target, args_list, force=False):
        from threading import Thread
        threads = []
        for args in args_list:
            if not isinstance(args, (list, tuple)):
                args = [args]
            cur = Thread(target=target, args=args)
            threads.append(cur)
            if len(args_list) == 1 and not force:  # dont start and wait for separate thread for one tasks
                cur.run()
                return threads
            cur.start()

        for t in threads:
            t.join()
        return threads

    def run_threaded_for_cluster(self, target, force=False):
        return ProviderAPI.run_threaded(target, list(self.iter_clustered_provider_api()))


class RecordingProviderAPI(ProviderAPI):

    provides_recording = True
    provides_streaming = True
    provides_playback = False
    can_update_acano_stream_url = False
    can_schedule_stream = False
    can_retry = False
    can_reschedule = True

    @classmethod
    def embed_callback(cls, meeting, url):
        from recording.models import MeetingRecording
        data = []
        for recording in MeetingRecording.objects.filter(meeting=meeting):

            videos = recording.provider.get_api(recording.meeting.customer).get_embed_callback_data(meeting, recording)

            for video in videos:
                data.append(video)

            recording.ts_callback_sent = now()
            recording.save()

        override_function = getattr(cls, 'override_embed_callback_post', None)
        http_post = override_function or requests.post

        response = http_post(url, data=dict(
            recordings=json.dumps(data),
        ))

        if not response.status_code == 200:
            raise ResponseError('recording callback was not valid: %s' % response.text, response)

        return True

    def get_stream_url(self, cospace_id=None):
        return ''

    def dialout(self, meeting, recording):
        raise NotImplementedError()

    def close_call(self, meeting, recording, recorder_id=None):
        raise NotImplementedError()

    def adhoc_record(self, api, call_id, **kwargs):
        raise NotImplementedError()

    def adhoc_stop_record(self, api, call_id, **kwargs):
        raise NotImplementedError()

    def get_call(self, recording_id):
        raise NotImplementedError()

    def get_embed(self, meeting, recording):
        raise NotImplementedError()

    def get_embed_code(self, recording):
        raise NotImplementedError()

    def get_recording_id(self, recording):
        raise NotImplementedError()

    def get_embed_callback_data(self, meeting, recording):
        raise NotImplementedError()


class InternalAPI(BookMeetingProviderAPI, ProviderAPI):

    def get_base_url(self):
        return '/'

    def login(self, force=False):

        return True

    def get_data(self, meeting):
        return {}

    def get_info(self, meeting):
        return meeting.as_dict()

    def get_url(self, path):
        return '%s/%s' % (self.get_base_url(), path.lstrip('/'))

    def book(self, meeting, uri=None):

        meeting.activate()

    def unbook(self, meeting):

        meeting.deactivate()

    def check_login_status(self, response):
        pass

    def get_params(self):
        return {}


class ExternalNoOpAPI(InternalAPI):

    def dialout(self, meeting, dialout):
        return
