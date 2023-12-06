import secrets
from builtins import StopIteration
from multiprocessing.pool import ThreadPool, AsyncResult, ApplyResult
from random import shuffle
from time import sleep, monotonic
from typing import (
    Dict,
    Iterator,
    List,
    Union,
    TYPE_CHECKING,
    Tuple,
    Callable,
    Any,
    Sequence,
    Mapping,
    TypeVar,
)
from xml.etree.ElementTree import Element
from defusedxml.cElementTree import fromstring as safe_xml_fromstring

from django.db.models.functions import Lower
from django.utils.functional import cached_property
from django.utils.six import wraps
from django.utils.translation import gettext as _

from django.db.models import Q

from django.utils.timezone import now, utc

from shared.utils import partial_update_or_create
from ..exceptions import AuthenticationError, NotFound, ResponseError, ResponseConnectionError, DuplicateError
from datetime import timedelta
from urllib.parse import urlencode, parse_qsl
from .base import ProviderAPI, BookMeetingProviderAPI, MCUProvider
from sentry_sdk import capture_exception
from collections import OrderedDict, defaultdict
import re
from django.conf import settings

import logging

from ..models.acano import AcanoCluster, CoSpaceAccessMethod

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from provider.models.provider import Provider
    from provider.models.provider_data import SettingsProfile
    from meeting.models import Meeting


MAX_THREADS = 4


"""
Nomenclature in class:
* cospace = video meeting room. Have uri, call id and settings. May have multiple access methods
* access method = separate uri to a cospace which may have different profile
* webinar = cospace with profiles and separate access method for moderator
* profile = settings. Different type for call, callLeg, branding etc
* call = live conference call
* participant = one client
* leg = leg of a participant. Some protocols have many legs per participant

Internally Cisco Meeting Service specific code uses the old name Acano.
CMS should be used externally. But CMS is a really confusing abbreviation
"""


def get_url_basename(url):
    url = url.rstrip('/')
    return url.rsplit('/', 1)[-1]


def merge_cospace_sync(fn):
    @wraps(fn)
    def inner(self: 'AcanoAPI', meeting, *args, **kwargs):
        old_is_syncing = self.is_syncing
        old_allow_cached_values = self.allow_cached_values
        try:
            self.is_syncing = True
            self.allow_cached_values = False  # TODO only for single objects?
            return fn(self, meeting, *args, **kwargs)
        finally:
            self.is_syncing = old_is_syncing
            self.allow_cached_values = old_allow_cached_values
            for cospace_id in list(self.queued_cospace_sync_ids[self.cluster.pk]):
                self.sync_single_cospace(cospace_id)

    return inner


class AcanoAPI(BookMeetingProviderAPI, MCUProvider, ProviderAPI):

    provider: 'Provider'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queued_cospace_sync_ids = defaultdict(set)

    def request(self, *args, **kwargs):
        kwargs['auth'] = (self.provider.username, self.provider.password)
        kwargs['allow_redirects'] = False
        return super().request(*args, **kwargs)

    def login(self, force=False):

        return True

    def get_url(self, path=None):
        return '%s/api/v1/%s' % (self.get_base_url(), path or '')

    def check_login_status(self, response):
        if '/accounts/login/' in response.headers.get('location', '') or response.status_code in (401, 403):
            raise AuthenticationError(response.text or 'Authentication error')

    @cached_property
    def is_multitenant(self):
        if self.customer.acano_tenant_id:
            return True
        from datastore.models.customer import Tenant
        return Tenant.objects.filter(provider=self.cluster).exclude(tid='').exists()

    def validate_new_object_id(self, response):
        location = response.headers.get('Location')
        if not location:
            try:
                basename = get_url_basename(response.request.url)
            except AttributeError:
                basename = 'unknown'
            raise self.error('ID for new {}-object not included in response'.format(basename), response)

        return get_url_basename(location)

    def get_sip_uri(self, uri: Union[int, str] = None, cospace: Dict = None):

        if cospace is not None:
            uri = cospace.get('uri') or uri or ''

        if not isinstance(uri, (str, int)):
            raise ValueError('uri is not a string!', uri)

        return '%s@%s' % (uri, self.get_settings(self.customer).get_main_domain())

    def get_web_url(self, call_id=None, secret=None, cospace=None):

        cluster_web_domain = self.get_settings(self.customer).get_web_domain()

        if cospace:
            secret = cospace.get('secret')
            call_id = call_id or cospace.get('callId') or cospace.get('call_id') or ''

        web_domain = cluster_web_domain or self.provider.web_host or self.provider.internal_domain
        if secret:
            return 'https://%s/invited.sf?id=%s&secret=%s' % (web_domain, call_id, secret)

        return 'https://%s/index.html?id=%s' % (web_domain, call_id)

    def error(self, content, response=None, extra=None):

        if response is not None and response.status_code == 400:
            details_match = re.search(
                r'<failureDetails>[^<]*(.*)</failureDetails>', response.text, re.DOTALL
            )
            if details_match and not extra:
                extra = details_match.group(1)

        return super().error(content, response=response, extra=extra)

    def check_response_errors(self, response, extra=None):

        self.check_login_status(response)

        extra = (extra,) if extra else ()

        if '<failureDetails>' in response.text and 'DoesNotExist />' in response.text:
            raise NotFound(response.text, response, *extra)

        if 'unrecognisedObject' in response.text:
            raise NotFound(response.text, response, *extra)

        if response.status_code == 503:
            self.connection_error_count += 1
            self.error_503_count += 1
            raise ResponseConnectionError('Server unavailable', response, *extra)

        details_match = re.search(
            r'<failureDetails>[^<]*(.*)</failureDetails>', response.text, re.DOTALL
        )
        if details_match:
            details = details_match.group(1).strip()
            if details.startswith('<duplicate'):
                raise DuplicateError(details, response)

    def get_apis_with_database(self):
        apis = list(self.iter_clustered_provider_api(only_call_bridges=False))

        return [api for api in apis if not api.provider.is_service_node or api.provider.get_option('has_database')]

    @merge_cospace_sync
    def book(self, meeting: 'Meeting', uri=None):

        existing_id = meeting.provider_ref2
        call_id = meeting.provider_ref

        uri = uri or meeting.get_preferred_uri()

        if not call_id:
            number_range = self.get_scheduled_room_number_range()
            call_id = self.populate_call_id({}, number_range=number_range, random=True)

        call_leg_profile = self._call_leg_profile('cospace', existing_id)
        call_profile = self._call_profile('cospace', existing_id)

        data = {
            'name': meeting.title or _('{} möte').format(self.customer.title),
            'uri': uri or call_id or '',
            'callId': call_id or '',
            'requireCallId': bool(not call_id.strip()),
            'passcode': meeting.password,
            'defaultLayout': meeting.layout,
            'cdrTag': urlencode([
                ('creator', meeting.creator[:75]),
                ('customer', meeting.customer_id),
                ('provider', meeting.provider_id),
            ]),

            'secondaryUri': call_id if uri and uri != call_id else '',
        }

        if meeting.provider_secret:
            data['secret'] = meeting.provider_secret  # dont change on pin/profile change

        if self.customer.acano_tenant_id:
            data['tenant'] = self.customer.acano_tenant_id
        else:
            data['tenant'] = ''

        meeting_settings = meeting.get_settings()

        if meeting_settings['force_encryption']:
            call_leg_profile.add_settings('force_encryption', self._get_force_encryption_call_leg(only_data=True))
        else:
            call_leg_profile.pop_settings('encryption')

        if meeting_settings['disable_chat']:
            call_profile.add_settings('disable_chat', self._get_no_chat_call_profile(only_data=True))
        else:
            call_profile.pop_settings('disable_chat')

        if not meeting_settings.get('lobby_pin') and not meeting.moderator_password:
            call_leg_profile.pop_settings('lobby_pin_access')

        cospace_id = existing_id

        data['callLegProfile'] = call_leg_profile.commit()
        data['callProfile'] = call_profile.commit()

        if existing_id:
            try:
                self.update_cospace(existing_id, data)
            except NotFound:
                cospace_id = ''

        if not cospace_id:
            cospace_id = self.add_cospace(data, try_increase_number=not meeting.provider_ref, sync=False)
            meeting.ts_provisioned = now()

        call_leg_profile.update_target_id(cospace_id)
        call_profile.update_target_id(cospace_id)

        moderator_pin = meeting.moderator_password or meeting_settings.get('lobby_pin')
        if cospace_id and moderator_pin and not meeting.is_webinar:
            self.lobby_pin(cospace_id, meeting.moderator_password or meeting_settings['lobby_pin'], meeting.moderator_layout)

        if cospace_id:
            cospace = self.get_cospace(cospace_id)
        else:
            raise self.error('Cospace ID not found')

        meeting.provider_ref2 = cospace['id']
        meeting.provider_ref = cospace.get('callId') or ''
        meeting.provider_secret = cospace.get('secret') or ''

        if cospace.get('callId') != call_id:
            if uri:
                self.update_cospace(cospace['id'], {'secondaryUri': meeting.provider_ref})
            else:
                self.update_cospace(cospace['id'], {'uri': meeting.provider_ref})

        if not cospace.get('ownerJid') and meeting.creator:  # TODO maybe check for extended validation of user?
            try:
                self.update_cospace(cospace['id'], {'ownerJid': meeting.creator})
            except (AuthenticationError, ResponseError, NotFound):
                pass

        meeting.activate()  # schedules add_member, must be run after owner update

        if not meeting.existing_ref:
            from datastore.models.acano import CoSpace

            CoSpace.objects.filter(provider=self.cluster, cid=meeting.provider_ref2).update(
                is_scheduled=True
            )

        self.sync_single_cospace(cospace_id)

        return cospace['id']

    @merge_cospace_sync
    def rebook(self, meeting: 'Meeting', new_data: Mapping[str, Any]):

        old_password = meeting.password
        self.update_meeting_settings(meeting, new_data)

        if not meeting.backend_active:
            return meeting

        update_data = {}
        if new_data.get('layout'):
            update_data['defaultLayout'] = meeting.layout
        if new_data.get('title'):
            update_data['name'] = new_data['title']

        if new_data.get('password') and new_data['password'] != old_password:
            update_data['passcode'] = new_data['password']
            update_data['regenerateSecret'] = 'true'

        if update_data:
            self.update_cospace(meeting.provider_ref2, update_data)

        if new_data.get('moderator_password'):
            if meeting.is_webinar:
                meeting.api.webinar(meeting)
            else:
                meeting.api.lobby_pin(meeting.provider_ref2, meeting.moderator_password)

        if new_data.get('password') or new_data.get('moderator_password'):
            data = self.get_cospace(meeting.provider_ref2)
            meeting.provider_secret = data['secret']

        self.sync_single_cospace(meeting.provider_ref2)

        return meeting

    def book_unprotected_access(self, meeting):

        data = {
            'uri': meeting.get_unprotected_uri(),
            'scope': 'member' if self.provider.software_version > '3.1' else 'private',
        }
        response = self.post('coSpaces/{}/accessMethods'.format(meeting.provider_ref2), data)

        if response.status_code not in (200,):
            if 'duplicateCoSpaceUriPasscode' not in response.text:
                raise self.error(response.text, response)

    def update_cospace(self, cospace_id, data):

        if data.get('callId') and data.get('uri'):
            if not data.get('secondaryUri'):
                call_id, uri = data['callId'], data['uri']
                data['secondaryUri'] = call_id if uri and uri != call_id else ''

        data.setdefault('regenerateSecret', 'false')

        if 'organization_unit' in data:
            from organization.models import CoSpaceUnitRelation

            data = data.copy()
            unit = data.pop('organization_unit')
            if unit:
                CoSpaceUnitRelation.objects.update_or_create(
                    provider_ref=cospace_id, defaults=dict(unit=unit)
                )
            else:
                CoSpaceUnitRelation.objects.filter(
                    provider_ref=cospace_id, unit__customer=self.customer
                ).delete()

        if 'moderator_passcode' in data:
            moderator_passcode = data.pop('moderator_passcode')
            self._add_or_update_cospace_moderator_accessmethod(
                cospace_id, {'passcode': moderator_passcode}
            )

        result = self.put('coSpaces/{}'.format(cospace_id), data)

        if result.status_code != 200:
            raise self.error(_('CoSpace could not be updated'), result)

        try:
            # refresh cache
            self.sync_single_cospace(cospace_id)
        except Exception:
            pass

        return cospace_id

    def populate_call_id(self, api_data: Dict, number_range=None, random=False):
        "Get callId from static value or from number range"
        from datastore.models.acano import CoSpace

        call_id = api_data.get('callId', None)
        if hasattr(call_id, 'use'):  # number range instance passed using callId
            number_range = number_range or call_id
            call_id = None

        if call_id:
            pass
        elif number_range and random:
            call_id = number_range.random()
            while CoSpace.objects.get_by_call_id(self.cluster, call_id):
                call_id = number_range.random()
        elif number_range:
            call_id = number_range.use()
            while CoSpace.objects.get_by_call_id(self.cluster, call_id):
                call_id = number_range.use()

        if not call_id:
            call_id = self.get_scheduled_room_number_range().random()

        api_data['callId'] = str(call_id)
        return str(call_id)

    def add_cospace(self, data, creator='', try_increase_number=False, sync=True):

        call_id = self.populate_call_id(data, random=data.pop('random_call_id', None))

        uri = data.pop('uri', None) or call_id
        if uri:
            data['uri'] = uri

        if not data.get('cdrTag'):
            cdr_tag = [
                ('creator', creator),
                ('customer', self.customer.id),
                ('provider', self.provider.id),
                ('ou', data.pop('group', None)),
            ]

            data['cdrTag'] = urlencode([x for x in cdr_tag if x[1]])

        data.update({
            'requireCallId': bool(not str(call_id).strip()),
            'secondaryUri': call_id if uri and uri != call_id else '',
        })
        data.setdefault('callLegProfile', '')

        if not data.get('streamUrl'):
            try:
                can_update_acano_stream_url = self.customer.get_streaming_api().can_update_acano_stream_url
            except AttributeError:
                pass
            else:
                if can_update_acano_stream_url:
                    stream_url = self.customer.get_streaming_api().get_stream_url(data['uri'] or data.get('callId'))

                    if stream_url:
                        data['streamUrl'] = stream_url

        if self.customer.acano_tenant_id:
            data['tenant'] = self.customer.acano_tenant_id
        else:
            data['tenant'] = ''

        uri_field = 'uri' if uri and uri != call_id else 'secondaryUri'
        if try_increase_number:
            result, inc_data = self.find_free_number_request('coSpaces', data, ['callId', uri_field])
        else:
            result = self.post('coSpaces', data)

        # ignore invalid stream url
        if '<parameterError parameter="streamUrl" error="invalidValue" />' in result.text:
            data.pop('streamUrl', None)
            result = self.post('coSpaces', data)

        new_url = result.headers.get('Location', '').replace('/api/v1/', '')

        if not new_url:
            raise self.error(_('No cospace created'), result)

        cospace_id = new_url.strip('/').rsplit('/', 1)[-1]

        if sync:  # use sync unless running api.get_cospace() later
            from datastore.utils.acano import sync_single_cospace_full
            sync_single_cospace_full(self, cospace_id=cospace_id)

        if data.get('streamUrl'):
            from recording.models import CoSpaceAutoStreamUrl

            CoSpaceAutoStreamUrl.objects.update_or_create(
                provider=self.cluster,
                cospace_id=cospace_id,
                defaults=dict(tenant_id=data.get('tenant', ''), stream_url=data['streamUrl']),
            )
        return cospace_id

    def set_layout(self, meeting, new_layout):

        data = {
            'defaultLayout': new_layout,
        }

        self.update_cospace(meeting.provider_ref2, data)

    def dialout(self, meeting, dialout):

        data = {
            'coSpace': meeting.provider_ref2,
            'name': 'api-call',
        }
        response = self.post('calls', data)
        call_id = self.validate_new_object_id(response)

        call_leg_id = self.add_call_leg(call_id, dialout.uri)

        dialout.provider_ref = call_leg_id
        dialout.activate()
        return True

    def notify(self, meeting, message):

        data = {
            'message': message,
            'from': _('Mindspace Cloud'),  # TODO
        }
        self.post('coSpaces/%s/messages' % meeting.provider_ref2, data)

    def close_call(self, meeting, dialout):

        try:
            response = self.delete('callLegs/%s' % dialout.provider_ref)
        except NotFound as e:
            response = e.response
        dialout.deactivate()
        return response

    def get_info(self, meeting):

        if not meeting.backend_active:
            return

        return self.get_cospace(meeting.provider_ref2)

    def get_cospace(self, cospace_id):

        if not cospace_id.strip():
            raise NotFound('Invalid cospace id')

        if self.use_cache_for_single_objects:
            cospaces, count = self.find_cospaces_cached(cospace_id=cospace_id)
            if cospaces:
                return cospaces[0]

        try:
            result = self.nodes_dict('coSpaces/%s' % cospace_id)
        except NotFound:
            from datastore.models.acano import CoSpace
            CoSpace.objects.filter(provider=self.cluster, cid=cospace_id, is_active=True).update(is_active=False)
            raise

        if 'callId' in result:
            result['call_id'] = result['callId']
        result['enabled'] = True

        if not self.is_syncing:

            synced = self.sync_single_cospace(cospace_id, data=result)

            if self.allow_cached_values:
                return synced.to_acano_dict()

        return result

    def sync_single_cospace(self, cospace_id: str = None, data: dict = None):
        from datastore.utils.acano import sync_single_cospace_full, sync_single_cospace_list

        if self.is_syncing:
            if data:
                sync_single_cospace_list(self, data)
            self.queued_cospace_sync_ids[self.cluster.pk].add(cospace_id)
            return

        self.queued_cospace_sync_ids[self.cluster.pk].discard(cospace_id)

        return sync_single_cospace_full(self, cospace_id, data=data)

    def get_calls(self, include_legs=False, include_participants=False, filter=None, cospace=None, limit=None, tenant=None, offset=0):

        params = {k: v for k, v in list({
            'limit': limit,
            'filter': filter,
            'offset': offset,
            'tenantFilter': tenant,
            'cospaceFilter': cospace,
            }.items()) if v is not None}

        calls, count = self._iter_pages_with_count('calls', 'calls', params, limit=limit)

        result = []

        for call in calls:
            cur = {
                'id': call.get('id'),
                'name': call.find('./name').text,
                'cospace': call.findtext('./coSpace', ''),
                'correlator': call.findtext('./callCorrelator', ''),
                'tenant': call.findtext('./tenant', None),
            }
            if include_legs:
                cur['legs'], leg_count = self.get_call_legs(cur['id'])
            if include_participants:
                cur['participants'], participant_count = self.get_participants(cur['id'])

            result.append(cur)

        return result, count

    def add_call(self, cospace, name=None):

        data = {
            'coSpace': cospace,
        }
        if name:
            data['name'] = name
        response = self.post('calls', data)

        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        call_id = self.validate_new_object_id(response)
        return call_id

    def get_clustered_calls(self, *args, **kwargs):

        # TODO how to handle limits/offsets in clustered environments? One provider at the time?
        result = []
        correlators = set()

        total_count = 0

        offset = kwargs.get('offset') or 0
        limit = kwargs.get('limit')

        clustered = len(self.cluster.get_clustered(include_self=True)) or 1
        if clustered <= 1:
            return self.get_calls(*args, **kwargs)

        # Temp fix. Split pagination over cluster. Wont work when pages run out on a single bridge
        kwargs['offset'] = max(1 if offset else 0, offset // clustered)
        if limit:
            kwargs['limit'] = max(1, limit // clustered)

        def _fetch(api):
            nonlocal total_count

            try:
                calls, count = api.get_calls(*args, **kwargs)
            except ResponseConnectionError:
                return

            total_count += count

            for call in calls:
                if call['correlator'] and call['correlator'] in correlators:
                    total_count -= 1
                    continue
                correlators.add(call['correlator'])
                result.append(call)

        self.run_threaded_for_cluster(_fetch)

        if limit or offset:
            if limit:  # Temp fix
                result = result[:limit]
            return result, total_count  # This probably wont be correct for clustered calls
        return result, len(result)

    def get_clustered_participant_count(self, *args, **kwargs):
        return self.get_clustered_participants(*args, only_count=True, **kwargs)[1]

    def get_clustered_participants(self, call_id=None, cospace=None, filter=None, tenant=None,
                                   limit=None, only_count=False) -> Tuple[List[Dict], int]:
        if only_count:
            limit = 1

        total_count = 0

        result = []

        def _fetch(api):
            nonlocal total_count

            try:
                participants, count = api.get_participants(call_id=call_id, cospace=cospace, filter=filter,
                                                           tenant=tenant, limit=limit, only_internal=True)
            except ResponseConnectionError:
                return

            if only_count:
                total_count += count
                return

            for participant in participants:
                result.append(participant)

        self.run_threaded_for_cluster(_fetch)

        if only_count:
            return result, total_count

        return result, len(result)

    def get_clustered_call(self, call_id, cospace=None, include_legs=False, include_participants=False):

        result = []
        call = {}

        # get call

        def _fetch_call(api):
            try:
                call = api.get_call(call_id, cospace=cospace)
            except (NotFound, ResponseConnectionError):
                pass
            else:
                result.append((call, api))

        self.run_threaded_for_cluster(_fetch_call)
        if not result:
            raise NotFound('Call id {} not found'.format(call_id))

        call = result[0][0]
        provider = result[0][1].provider
        name = call['name']
        correlator = call['correlator']

        def _fetch_correlated(api):
            if api.provider.pk == provider.pk:
                return

            if call.get('cospace'):
                filter_kwargs = {'cospace': call['cospace']}
            else:
                filter_kwargs = {'filter': name}

            try:
                calls, count = api.get_calls(**filter_kwargs)
            except ResponseConnectionError:
                return

            for c in calls:
                if c['correlator'] == correlator:
                    result.append((api.get_call(c['id']), api))

        self.run_threaded_for_cluster(_fetch_correlated)

        return result

    def get_clustered_call_legs(
        self,
        call_id: str = None,
        cospace: str = None,
        filter: Union[str, Dict[str, Any]] = None,
        tenant: str = None,
        limit: int = None,
    ) -> List[Dict[str, Any]]:

        if call_id:
            return self.get_clustered_call_legs_for_call(call_id)

        result = []

        def _get_call_legs(api: AcanoAPI):
            legs, count = api.get_call_legs(cospace=cospace, filter=filter, tenant=tenant, limit=limit)
            result.extend(legs)

        self.run_threaded_for_cluster(_get_call_legs)
        return result

    def get_clustered_call_legs_for_call(self, call_id, cospace=None, filter=None, tenant=None, limit=None):

        if not call_id:
            raise ValueError('Empty call id')

        result = []
        for call, api in self.get_clustered_call(call_id):

            try:
                legs, count = api.get_call_legs(call_id=call['id'], cospace=cospace, filter=filter, tenant=tenant, limit=limit)
            except NotFound:
                pass
            else:
                result.extend(legs)

        return result

    def get_clustered_call_leg(self, leg_id):

        if not leg_id:
            raise ValueError('Empty leg id')

        for api in self.iter_clustered_provider_api():
            try:
                return (api.get_call_leg(leg_id), api)
            except (NotFound, ResponseConnectionError):
                pass

        raise NotFound('Call leg {} not found'.format(leg_id))

    def get_call(self, call_id, cospace=None, include_legs=False, include_participants=False):

        call = self.nodes_dict('calls/{}'.format(call_id), convert_bool=True)

        duration = int(call.get('durationSeconds') or 0)
        result = {
            **call,
            'cospace': call.get('coSpace', ''),
            'cospace_id': call.get('coSpace', ''),
            'name': call.get('name', ''),
            'duration': duration,
            'ts_start': (now() - timedelta(seconds=duration)).isoformat(),
            'call_legs': int(call.get('numCallLegs') or -1),
            'max_call_legs': int(call.get('maxCallLegs') or -1),
            'correlator': call.get('callCorrelator', ''),
        }

        if include_legs:
            result['legs'], leg_count = self.get_call_legs(result['id'])

        if include_participants:
            result['participants'], participant_count = self.get_participants(result['id'])

        return result

    def _is_internal_call_leg(self, leg):

        if leg.get('subtype') == 'distributionLink':
            return True

        if hasattr(leg, 'find'):  # xml
            remote = leg.findtext('./remoteParty') or leg.findtext('./remoteAddress', '')
            name = leg.findtext('./name', '')
        else:
            remote = leg.get('remote')
            name = leg.get('name')

        for internal in list(settings.INTERNAL_CALL_LEGS) + self.cluster.internal_callbridge_ips:
            if isinstance(internal, str):
                internal = [internal]

            match = True
            for needle in internal:
                if needle not in remote and needle not in name:
                    match = False
                    break

            if match:
                return True
        return False

    def get_call_legs(self, call_id=None, cospace=None, filter=None, tenant=None, limit=None):
        """return call legs in current bridge. clustered calls return one extra leg to each other bridge"""

        if call_id:
            url = 'calls/{}/callLegs'.format(call_id)
            call_legs, count = self._iter_pages_with_count(url, 'callLegs', {'filter': filter or ''}, limit=limit)
        else:
            call_legs, count = self._iter_pages_with_count('callLegs', 'callLegs', {'limit': limit, 'filter': filter or cospace or '', 'tenantFilter': tenant}, limit=limit)

        result = []

        for leg in call_legs:
            if self._is_internal_call_leg(leg):  # TODO return anyway?
                continue

            remote = leg.findtext('./remoteParty') or leg.findtext('./remoteAddress', '')

            alarms = []
            if leg.find('./alarms') is not None:
                for alarm in leg.find('./alarms'):
                    alarms.append(alarm.tag)

            result.append({
                'id': leg.get('id'),
                'name': leg.find('./name').text or remote.split('@')[0] or 'Unspecified',
                'remote': remote,
                'tenant': leg.findtext('./tenant', ''),
                'call': leg.findtext('./call', ''),
                'alarms': alarms,
            })

        return result, count

    def get_call_leg(self, call_leg_id):

        response = self.get('callLegs/{}'.format(call_leg_id))
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        call_leg = safe_xml_fromstring(response.text)

        result = {
            'id': call_leg.get('id'),
            'alarms': {},
            'status': {},
            'configuration': {},
            'provider_id': self.provider.pk,
            'type': call_leg.findtext('./type', ''),
            'subtype': call_leg.findtext('./subType', ''),
        }

        def _iterset(node, target):
            if node is None:
                return
            for tag in node:
                if tag.tag in ('alarms', 'status', 'configuration'):
                    continue

                if tag.tag.endswith('Seconds'):
                    target[tag.tag.replace('Seconds', 'Minutes')] = str(timedelta(seconds=float(tag.text)))

                if (tag.tag.startswith('rx') or tag.tag.startswith('tx')) and tag.text not in ('true', 'false'):
                    name = tag.tag + (tag.get('role') or '')
                    target[name] = {}
                    _iterset(tag, target[name])
                elif tag.text in ('true', 'false'):
                    target[tag.tag] = True if tag.text == 'true' else False
                else:
                    target[tag.tag] = tag.text

        _iterset(call_leg, result)
        _iterset(call_leg.find('./status'), result['status'])
        _iterset(call_leg.find('./configuration'), result['configuration'])
        _iterset(call_leg.find('./alarms'), result['alarms'])

        result['remote'] = result.get('remoteParty') or result.get('remoteAddress') or ''

        if result.get('status') and result['status'].get('durationSeconds'):
            result['ts_start'] = now() - timedelta(seconds=int(result['status'].get('durationSeconds')))

        return result

    def add_call_leg(self, call_id, remote, **data):

        data = {
            'remoteParty': remote,
        }

        response = self.post('calls/{}/callLegs'.format(call_id), data)
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        call_leg_id = self.validate_new_object_id(response)
        return call_leg_id

    def update_call_leg(self, leg_id, data):

        response = self.put('callLegs/{}'.format(leg_id), data)
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        return response

    def hangup_call_leg(self, leg_id):

        response = self.delete('callLegs/{}'.format(leg_id))
        return response.status_code == 200

    def update_call(self, call_id, data):

        response = self.put('calls/{}'.format(call_id), data)
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        return response

    def set_participant_moderator(self, leg_id, value=True):
        response = self.update_call_leg(leg_id, {
            'callLegProfile': self._get_webinar_call_legs()[1 if value else 0],
        })
        return response.status_code == 200

    def set_all_participant_mute(self, call_id, value=True):
        response = self.put('calls/{}/participants/*'.format(call_id), {
            'rxAudioMute': 'on' if value else 'off',
        })
        return response.status_code == 200

    def set_all_participant_video_mute(self, call_id, value=True):
        response = self.put(
            'calls/{}/participants/*'.format(call_id),
            {
                'rxVideoMute': 'on' if value else 'off',
            },
        )
        return response.status_code == 200

    def set_participant_mute(self, leg_id, value=True):
        response = self.update_call_leg(
            leg_id,
            {
                'rxAudioMute': 'on' if value else 'off',
            },
        )
        return response.status_code == 200

    def set_participant_video_mute(self, leg_id, value=True):
        response = self.update_call_leg(
            leg_id,
            {
                'rxVideoMute': 'on' if value else 'off',
            },
        )
        return response.status_code == 200

    def set_call_lock(self, call_id, value=True):
        response = self.update_call(call_id, {
            'locked': 'true' if value else 'false',
        })
        return response.status_code == 200

    def get_participants(self, call_id=None, cospace=None, filter=None, tenant=None,
                         only_internal=True, limit=None):
        "when clustered, returns connected participants + clustered participants in the bridge's calls"

        filters = {'filter': filter or '', 'tenantFilter': tenant}

        if only_internal:
            try:
                filters['callBridgeFilter'] = self.get_call_bridge_id() or ''
            except Exception:
                pass

        if call_id:
            url = 'calls/{}/participants'.format(call_id)
            participants, count = self._iter_pages_with_count(url, 'participants', filters, limit=limit)
        else:
            url = 'participants'
            participants, count = self._iter_pages_with_count(url, 'participants', filters, limit=limit)

        result = []

        for participant in participants:
            result.append({
                'id': participant.get('id'),
                'name': participant.findtext('./name', '') or 'Unspecified',
                'call': participant.findtext('./call', ''),
                'callbridge': participant.findtext('./callBridge', ''),
            })

        if only_internal:
            result = [r for r in result if not r.get('callbridge')]

        return result, count

    def add_participant(self, call_id, remote, layout=None, call_leg_profile=None):

        data = {
            'remoteParty': remote,
        }

        if layout:
            data['chosenLayout'] = layout

        if call_leg_profile:
            data['callLegProfile'] = call_leg_profile

        response = self.post('calls/{}/participants'.format(call_id), data)
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        participant_id = self.validate_new_object_id(response)
        return participant_id

    def update_call_participants(self, call_id, data):
        response = self.put('calls/{}/participants/*'.format(call_id), data)
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)
        return response

    def hangup_participant(self, participant_id):

        try:
            response = self.delete('participants/{}'.format(participant_id))
            return response.status_code == 200
        except NotFound:
            return None

    def hangup_call(self, call_id):

        try:
            response = self.delete('calls/{}'.format(call_id))
            return response.status_code == 200
        except NotFound:
            return None

    def _get_force_encryption_call_leg(self, sync=False, only_data=False):

        encryption_call_leg = self.cluster.get_option('force_encryption_call_leg')

        data = {
                'sipMediaEncryption': 'required',
        }

        if only_data:
            return data

        if not encryption_call_leg:
            response = self.post('callLegProfiles', data)
            encryption_call_leg = self.validate_new_object_id(response)
            self.cluster.set_option('force_encryption_call_leg', encryption_call_leg)
        elif sync:
            try:
                self.put('callLegProfiles/{}'.format(encryption_call_leg), data)
            except NotFound:
                self.cluster.set_option('force_encryption_call_leg', '')

        return encryption_call_leg

    def _get_call_leg_data(self, is_guest, force_encryption=None):

            not_guest_value = 'true' if not is_guest else 'false'
            is_guest_value = 'true' if is_guest else 'false'

            result = {
                'defaultLayout': 'speakerOnly',
                'presentationContributionAllowed': not_guest_value,
                'endCallAllowed': not_guest_value,
                'callLockAllowed': not_guest_value,
                'changeLayoutAllowed': not_guest_value,
                'muteOthersAllowed': not_guest_value,
                'videoMuteOthersAllowed': not_guest_value,
                'muteSelfAllowed': not_guest_value,
                'videoMuteSelfAllowed': not_guest_value,
                'txAudioMute': 'false',
                'txVideoMute': 'false',
                'rxAudioMute': is_guest_value,
                'rxVideoMute': is_guest_value,
            }

            if not is_guest:
                result['needsActivation'] = 'false'
                result['setImportanceAllowed'] = 'true'

            if force_encryption is not None:
                result['sipMediaEncryption'] = 'required' if force_encryption else 'optional'

            return result

    def _call_profile(self, target_type, target, cospace_id=None) -> 'SettingsProfile':
        return self._profile(target_type, target, cospace_id, 'callProfile')

    def _call_leg_profile(self, target_type, target, cospace_id=None) -> 'SettingsProfile':
        return self._profile(target_type, target, cospace_id, 'callLegProfile')

    def _profile(self, target_type, target, cospace_id=None, profile_type='callProfile') -> 'SettingsProfile':
        from provider.models.provider_data import SettingsProfile

        parent = None
        if cospace_id:
            parent = SettingsProfile.objects.get_for(self.cluster, 'cospace', cospace_id, profile_type)

        profile = SettingsProfile.objects.get_for(self.cluster, target_type, target, profile_type, parent=parent)

        url_plural = '{}s'.format(profile_type)

        def _update(obj: SettingsProfile):
            if obj.profile_id:
                try:
                    return self._update_object('{}/{}'.format(url_plural, obj.profile_id), obj.result)
                except NotFound:
                    pass

            obj.profile_id = self._create_object(url_plural, obj.result)

        def _delete(obj: SettingsProfile):
            if obj.profile_id:
                try:
                    return self.delete('{}/{}'.format(url_plural, obj.profile_id))
                except ResponseError:
                    pass

        def _extend(obj: SettingsProfile):
            if obj.extends_profile_id:
                data = self.nodes_dict('{}/{}'.format(url_plural, obj.extends_profile_id))
                obj.add_settings('parent_profile', data, 1000)
            else:
                obj.pop_settings('parent_profile')

        profile.register_hooks(_update, _delete, _extend)
        return profile

    def _create_object(self, uri, data):
        response = self.post(uri, data)
        return self.validate_new_object_id(response)

    def _update_object(self, uri, data):
        response = self.put(uri, data)
        if response.status_code not in (200, 201):
            raise self.error('Invalid status for %s (%s)' % (uri, response.status_code), response)

        return response

    def nodes_dict(self, url, convert_bool=False, convert_case=False):

        response = self.get(url)

        if response.status_code != 200:
            raise self.error('Status not 200: {}'.format(response.status_code), response)

        xml = safe_xml_fromstring(response.content)
        return self.convert_node_to_dict(xml, convert_bool=convert_bool)

    def iter_nodes_list(self, url, require_tag=None, *, convert_bool=False, convert_case=False) -> Iterator[Dict]:

        nodes = self._iter_all_pages(url, require_tag=require_tag)
        return (self.convert_node_to_dict(node, convert_bool=convert_bool, convert_case=convert_case)
                for node in nodes)

    def nodes_list(self, url, require_tag=None, *, convert_bool=False, convert_case=False):
        return list(self.iter_nodes_list(url, require_tag=require_tag, convert_bool=convert_bool, convert_case=convert_case))

    def convert_node_to_dict(self, node, convert_bool=False, convert_case=False):
        result = {}
        for child in node:
            value = child.text
            if convert_bool and value in ('true', 'false'):
                value = (value == 'true')

            if convert_case:  # convert someThing to some_thing
                key = re.sub(r'([a-z])([A-Z])', r'\1_\2', child.tag).lower()
                result[key] = child.text
            else:
                key = child.tag
                result[child.tag] = value

            if convert_bool and result[key] in ('true', 'false'):
                    result[key] = result[key] == 'true'

        if 'id' not in result and node.get('id'):
            result['id'] = node.get('id')

        return result

    def _get_webinar_call_legs(self, force_encryption=None, sync=False, only_data=False):
        "get call legs with input disabled or enabled for use in webinars"

        if force_encryption:
            _get_call_leg_data = lambda is_guest: self._get_call_leg_data(is_guest=is_guest, force_encryption=force_encryption)
            option_suffix = '_enc'
        else:
            _get_call_leg_data = self._get_call_leg_data
            option_suffix = ''

        guest_call_leg = self.cluster.get_option('webinar_guest_call_leg' + option_suffix)
        moderator_call_leg = self.cluster.get_option('webinar_moderator_call_leg' + option_suffix)

        if only_data:
            return _get_call_leg_data(is_guest=True), _get_call_leg_data(is_guest=False)

        if not guest_call_leg:
            response = self.post('callLegProfiles', _get_call_leg_data(is_guest=True))
            guest_call_leg = self.validate_new_object_id(response)
            self.cluster.set_option('webinar_guest_call_leg' + option_suffix, guest_call_leg)
        elif sync:
            try:
                self.put('callLegProfiles/{}'.format(guest_call_leg), _get_call_leg_data(is_guest=True))
            except NotFound:
                self.cluster.set_option('webinar_guest_call_leg' + option_suffix, '')

        if not moderator_call_leg:
            response = self.post('callLegProfiles', _get_call_leg_data(is_guest=False))

            moderator_call_leg = self.validate_new_object_id(response)

            self.cluster.set_option(
                'webinar_moderator_call_leg' + option_suffix, moderator_call_leg
            )
        elif sync:
            try:
                self.put('callLegProfiles/{}'.format(moderator_call_leg), _get_call_leg_data(is_guest=False))
            except NotFound:
                self.cluster.set_option('webinar_moderator_call_leg' + option_suffix, '')

        return guest_call_leg, moderator_call_leg

    def _get_no_chat_call_profile(self, sync=False, only_data=False):
        "get call profile with chat disabled"

        call_profile_id = self.cluster.get_option('no_chat_profile')

        data = {
            'messageBoardEnabled': 'false',
        }

        if only_data:
            return data

        if not call_profile_id:

            response = self.post('callProfiles', data)
            call_profile_id = self.validate_new_object_id(response)

            self.cluster.set_option('no_chat_profile', call_profile_id)
        elif sync:
            try:
                self.put('callProfiles/{}'.format(call_profile_id), data)
            except NotFound:
                self.cluster.set_option('no_chat_profile', '')

        return call_profile_id

    def _get_needs_activation_call_leg_profile(self, force_encryption=None, sync=False, only_data=False):
        "get call leg profile with needsActivation=true"

        if force_encryption:
            option_suffix = '_enc'
        else:
            option_suffix = ''

        call_profile_id = self.cluster.get_option('need_activation_profile' + option_suffix)

        data = {
            'needsActivation': 'true',
        }
        if force_encryption is not None:
            data['sipMediaEncryption'] = 'required' if force_encryption else 'optional'

        if only_data:
            return data

        if not call_profile_id:

            response = self.post('callLegProfiles', data)
            call_profile_id = self.validate_new_object_id(response)

            self.cluster.set_option('need_activation_profile' + option_suffix, call_profile_id)
        elif sync:
            try:
                self.put('callLegProfiles/{}'.format(call_profile_id), data)
            except NotFound:
                self.cluster.set_option('need_activation_profile' + option_suffix, '')

        return call_profile_id

    def webinar(self, meeting):

        from meeting.models import MeetingWebinar

        webinar_config = meeting.get_webinar_info()

        guest_call_leg_data = self._get_webinar_call_legs(force_encryption=meeting.get_settings()['force_encryption'], only_data=True)[0]

        call_profile = self._call_profile('cospace', meeting.provider_ref2)
        call_leg_profile = self._call_leg_profile('cospace', meeting.provider_ref2)
        call_leg_profile.add_settings('guest', guest_call_leg_data)

        call_profile.toggle_settings('disable_chat', not webinar_config['disable_chat'],
            self._get_no_chat_call_profile(only_data=True))

        # guest access as default to keep connection details secret in invite etc
        data = {
            'passcode': meeting.password,
            'callLegProfile': call_leg_profile.commit(),
            'callProfile': call_profile.commit(),
            'secret': meeting.provider_secret,
        }
        if meeting.get_webinar_info().get('uri'):
            data['uri'] = meeting.get_webinar_info().get('uri')

        cospace_id = meeting.provider_ref2
        self.update_cospace(cospace_id, data)

        base_moderator_call_leg_profile_id = self._get_webinar_call_legs(
            force_encryption=meeting.get_settings()['force_encryption']
        )[1]

        moderator_call_leg_profile = self._call_leg_profile(
            'accessmethod', '', cospace_id=cospace_id
        )
        moderator_call_leg_profile.extend(base_moderator_call_leg_profile_id)

        if meeting.moderator_layout:
            moderator_call_leg_profile.add_settings('moderator_layout', {'defaultLayout': meeting.moderator_layout})
        else:
            moderator_call_leg_profile.pop_settings('moderator_layout')

        moderator_call_leg_profile_id = moderator_call_leg_profile.commit()

        # set all members as moderators
        for m in self.get_members(cospace_id):
            self.update_member(cospace_id, m['id'], callLegProfile=moderator_call_leg_profile_id)

        cur_call_id = ''
        cur_secret = ''

        for w in MeetingWebinar.objects.filter(meeting=meeting):

            cur_call_id = w.provider_ref
            cur_secret = w.provider_secret
            self.unbook_webinar(meeting, w)

        number_range = self.get_scheduled_room_number_range()

        call_id = cur_call_id or number_range.random()

        data = {
            'callId': call_id,
            'uri': call_id,
            'passcode': meeting.moderator_password or webinar_config['moderator_pin'],
            'callLegProfile': moderator_call_leg_profile_id,
            'secret': cur_secret or secrets.token_urlsafe(22),
            'scope': 'member' if self.provider.software_version > '3.1' else 'private',
            'name': _('Moderator'),
        }

        # Create or update
        access_method_id = self._add_or_update_cospace_moderator_accessmethod(cospace_id, data)

        moderator_call_leg_profile.update_target_id(access_method_id)

        webinar = MeetingWebinar.objects.create(meeting=meeting, password=meeting.moderator_password or webinar_config['moderator_pin'],
                                                provider_ref=data['callId'],
                                                provider_secret=data['secret'],
                                                access_method_id=access_method_id,
                                                group=webinar_config['group'] or '')

        return webinar

    @merge_cospace_sync
    def lobby_pin(self, cospace_id, moderator_pin, moderator_layout=None):

        cospace_data = self.get_cospace(cospace_id)

        guest_call_leg, base_moderator_call_leg_id = self._get_webinar_call_legs()

        # set guest access
        call_leg_profile = self._call_leg_profile('cospace', cospace_id)
        call_leg_profile.add_settings('lobby_pin_access', {'needsActivation': 'true'})

        update_cospace_data = {
            'callLegProfile': call_leg_profile.commit(),
            'passcode': cospace_data.get('passcode') or '',  # TODO save old value?
            'secret': cospace_data.get('secret') or '',
        }
        self.update_cospace(cospace_id, update_cospace_data)

        moderator_call_leg_profile = self._call_leg_profile(
            'accessmethod', '', cospace_id=cospace_id
        )
        moderator_call_leg_profile.extend(base_moderator_call_leg_id)

        if moderator_layout:
            moderator_call_leg_profile.add_settings(
                'moderator_layout', {'defaultLayout': moderator_layout}
            )
        else:
            moderator_call_leg_profile.pop_settings('moderator_layout')

        moderator_call_leg_profile_id = moderator_call_leg_profile.commit()

        # set all members as moderators
        for m in self.get_members(cospace_id):
            self.update_member(cospace_id, m['id'], callLegProfile=moderator_call_leg_profile_id)

        # Create or update
        data = {
            'passcode': moderator_pin,
            'uri': cospace_data['uri'],
            'callId': cospace_data['callId'],
            'scope': 'member' if self.provider.software_version > '3.1' else 'private',
            'callLegProfile': moderator_call_leg_profile_id,
            'name': _('Moderator'),
        }
        access_method_id = self._add_or_update_cospace_moderator_accessmethod(cospace_id, data)
        moderator_call_leg_profile.update_target_id(access_method_id)

        self.sync_single_cospace(cospace_id)

        return access_method_id

    def _add_or_update_cospace_moderator_accessmethod(self, cospace_id, data):

        access_method_id = None
        from provider.models.acano import CoSpace

        existing = CoSpace.objects.filter(provider=self.cluster, provider_ref=cospace_id).first()
        if existing and existing.moderator_ref:
            access_method_id = existing.moderator_ref

            regenerate_secret = (data.get('passcode') or '') != existing.moderator_password

            try:
                self.update_cospace_accessmethod(
                    cospace_id,
                    existing.moderator_ref,
                    {'regenerateSecret': 'true' if regenerate_secret else 'false', **data},
                )
            except NotFound:
                access_method_id = None

        if not access_method_id:
            if 'callLegProfile' not in data:
                data['callLegProfile'] = self._get_webinar_call_legs()[1]

            access_method_id = self.add_cospace_accessmethod(
                cospace_id, data, system_id='moderator'
            )

        try:

            partial_update_or_create(
                CoSpace,
                provider=self.cluster,
                provider_ref=cospace_id,
                defaults={
                    'customer': self.customer,
                    'lobby': True,
                    'moderator_ref': access_method_id,
                    'moderator_password': data.get('passcode') or '',
                },
            )

            CoSpaceAccessMethod.objects.filter(
                provider=self.cluster,
                cospace_id=cospace_id,
                provider_ref2=access_method_id,
            ).update(
                provider_secret=self.get_secret_for_access_method(cospace_id, access_method_id),
            )
        except Exception:
            capture_exception()

        return access_method_id

    def add_cospace_accessmethod(self, cospace_id, data, try_increase=False, system_id=None):

        response, inc_data = self.find_free_number_request('coSpaces/{}/accessMethods'.format(cospace_id), data, ['callId', 'uri'])
        access_method_id = self.validate_new_object_id(response)

        secret = data.get('secret')
        if not secret:
            secret = self.get_secret_for_access_method(cospace_id, access_method_id)

        CoSpaceAccessMethod.objects.update_or_create(
            provider=self.cluster,
            cospace_id=cospace_id,
            system_id=system_id,
            defaults={
                'provider_ref2': access_method_id,
                'provider_ref': data.get('callId') or '',
                'is_virtual': False,
                'provider_secret': secret,
                'password': data.get('passcode') or '',
            },
        )

        self.sync_single_cospace(cospace_id)

        return access_method_id

    def update_cospace_accessmethod(self, cospace_id, method_id, data):
        url = 'coSpaces/{}/accessMethods/{}'.format(cospace_id, method_id)
        response = self.put(url, data)

        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        self.sync_single_cospace(cospace_id)
        return True

    def remove_cospace_accessmethod(self, cospace_id, method_id):
        url = 'coSpaces/{}/accessMethods/{}'.format(cospace_id, method_id)
        response = self.delete(url)

        if response.status_code not in (404, 200):
            raise self.error('status not ok: %s' % response.text, response)

        CoSpaceAccessMethod.objects.filter(
            provider=self.cluster, cospace_id=cospace_id, provider_ref=method_id
        ).delete()

        self.sync_single_cospace(cospace_id)

        return True

    def get_cospace_accessmethods(self, cospace_id, include_data=False):

        result = self.nodes_list('coSpaces/{}/accessMethods'.format(cospace_id))

        if include_data:
            for am, cur in zip(  # noqa: B020
                AcanoDistributedRunner(
                    self,
                    lambda api, am: api.get_cospace_accessmethod(cospace_id, am.get('id')),
                    result,
                    ordered_result=True,
                ),
                result,
            ):
                cur.update(am)

        return result

    def get_cospace_accessmethod(self, cospace_id: str, access_method_id: str):

        return self.nodes_dict('coSpaces/{}/accessMethods/{}'.format(cospace_id, access_method_id))

    def get_cospace_moderator_settings(self, cospace_id: str, system_id='moderator'):
        from provider.models.acano import CoSpaceAccessMethod

        moderator_accessmethod = CoSpaceAccessMethod.objects.filter(
            provider=self.cluster, cospace_id=cospace_id, system_id=system_id
        ).first()
        if moderator_accessmethod:
            return {
                'secret': moderator_accessmethod.provider_secret,
                'call_id': moderator_accessmethod.provider_ref,
                'password': moderator_accessmethod.password,
            }

        for access_method in self.get_cospace_accessmethods(cospace_id):

            data = self.nodes_dict(
                'coSpaces/{}/accessMethods/{}'.format(cospace_id, access_method['id'])
            )

            return {
                'secret': data['secret'],
                'call_id': data.get('callId') or data.get('uri') or '',
                'password': data.get('passcode') or '',
            }

    def unbook(self, meeting):
        if not meeting.backend_active:
            return

        if meeting.existing_ref:  # don't delete
            meeting.deactivate()
            return

        def _done():
            from datastore.models.acano import CoSpace
            CoSpace.objects.filter(provider=self.cluster, cid=meeting.provider_ref2).update(is_active=False)
            meeting.deactivate()

            if meeting.provider_ref2:
                self._call_profile('cospace', meeting.provider_ref2).delete()
                self._call_leg_profile('cospace', meeting.provider_ref2).delete()

        try:
            result = self.delete('coSpaces/%s' % meeting.provider_ref2)
        except NotFound:
            _done()
            result = None

        meeting.ts_deprovisioned = now()
        _done()

        return result

    def unbook_webinar(self, meeting, webinar):

        if not meeting.backend_active:
            return

        try:
            if self.remove_cospace_accessmethod(meeting.provider_ref2, webinar.access_method_id):
                webinar.delete()
        except self.error:
            pass
        return

    def delete_cospace(self, cospace_provider_ref):

        from meeting.models import Meeting

        meetings = Meeting.objects.filter(
            provider=self.cluster, provider_ref2=cospace_provider_ref, backend_active=True
        )

        if meetings:
            return self.unbook(meetings[0])

        result = self.delete('coSpaces/%s' % cospace_provider_ref)

        self._call_profile('cospace', cospace_provider_ref).delete()
        self._call_leg_profile('cospace', cospace_provider_ref).delete()

        if result.status_code in (200, 404):
            from datastore.models.acano import CoSpace

            CoSpace.objects.filter(provider=self.cluster, cid=cospace_provider_ref).update(
                is_active=False
            )

            CoSpaceAccessMethod.objects.filter(
                provider=self.cluster,
                cospace_id=cospace_provider_ref,
            ).delete()
            return True
        return False

    def unbook_cached_values(self):

        options = self.provider.get_options()

        for call_leg in [options[k] for k in 'webinar_guest_call_leg webinar_moderator_call_leg need_activation_profile'.split() if options.get(k)]:
            self.delete('callLegProfiles/{}'.format(call_leg))

        for call_profile in [options[k] for k in 'no_chat_profile'.split() if options.get(k)]:
            self.delete('callProfiles/{}'.format(call_profile))

    def find_cospaces_cached(self, q=None, cospace_id=None, offset=0, limit=10, tenant=None, org_unit=None):
        from datastore.models.acano import CoSpace

        result = CoSpace.objects.search_active(
            provider=self.cluster, q=q, tenant=tenant, org_unit=org_unit
        )
        if cospace_id is not None:
            result = result.filter(cid=cospace_id)

        if org_unit:
            result = result.prefetch_related('organization_unit', 'organization_unit__parent')

        return [u.to_dict() for u in result[offset:offset + limit if limit else None]], result.count()

    def find_cospaces(self, q, offset=0, limit=10, tenant=None, org_unit=None):

        if org_unit or self.use_cached_values:
            return self.find_cospaces_cached(q, offset=offset, limit=limit, tenant=tenant, org_unit=org_unit)

        cospaces, count = self._iter_pages_with_count('coSpaces', 'coSpaces',
            {'filter': q, 'offset': offset or 0, 'tenantFilter': tenant},
            limit=limit if limit else None)

        result = []
        for cospace in cospaces:
            result.append({
                'id': cospace.get('id'),
                'call_id': cospace.findtext('./callId'),
                'name': cospace.findtext('./name', ''),
                'uri': cospace.findtext('./uri', ''),
                'auto_generated': cospace.find('./autoGenerated').text == 'true',
                'tenant': cospace.findtext('./tenant', ''),
            })
            if not self.is_syncing:
                from datastore.utils.acano import sync_single_cospace_list

                sync_single_cospace_list(self, self.convert_node_to_dict(cospace))

        return result, count

    def find_users_cached(self, q=None, user_id=None, offset=0, limit=10, tenant=None, org_unit=None):
        from datastore.models.acano import User

        result = User.objects.search_active(self.cluster, q, tenant=tenant, org_unit=org_unit)
        if user_id is not None:
            result = result.filter(uid=user_id)

        result = result.select_related('tenant').order_by(Lower('username'))

        return [u.to_dict() for u in result[offset:offset + limit if limit else None]], result.count()

    def find_users(self, q, offset=0, limit=10, tenant=None, org_unit=None, include_user_data=False):

        if self.use_cached_values or org_unit:
            return self.find_users_cached(q=q, offset=offset, limit=limit, tenant=tenant, org_unit=org_unit)

        users, count = self._iter_pages_with_count('users', 'users',
            {'filter': q, 'offset': offset or 0, 'tenantFilter': tenant},
            limit=limit if limit else None)

        if include_user_data:
            result = AcanoDistributedRunner(self, lambda api, user: api.get_user(user.get('id')), users).as_list()
        else:

            result = [{
                'id': user.get('id'),
                'jid': user.findtext('./userJid'),
                'tenant': user.findtext('./tenant', ''),
            } for user in users]

            if not self.is_syncing:
                from datastore.utils.acano import sync_single_user_list

                for u in users:
                    sync_single_user_list(self, self.convert_node_to_dict(u))

        return result, count

    def find_user(self, user_jid, tenant=None):

        if not user_jid or len(user_jid) <= 5 or '@' not in user_jid:
            raise NotFound('User {} not found'.format(user_jid))

        users, count = self._iter_pages_with_count('users', 'users',
            {'filter': user_jid, 'tenantFilter': tenant})

        for u in users:
            if u.findtext('./userJid', '') == user_jid:
                return self.get_user(u.get('id'))

        raise NotFound('User {} not found'.format(user_jid))

    def get_tenants(self):
        # TODO remove? Not used anymore at the moment since move to datastore sync

        tenants = self.nodes_list('tenants', 'tenants', convert_case=True, convert_bool=True)
        urls = ['tenants/{}'.format(t['id']) for t in tenants]

        result = []
        for node in AcanoDistributedGet(self, urls):
            result.append({
                'name': '',
                'call_branding_profile': '',
                'ivr_branding_profile': '',
                'tenant_group': '',
                **self.convert_node_to_dict(node, convert_case=True, convert_bool=True)
                })

        return result

    def get_callbrandings(self):

        result = []
        for profile in self._iter_all_pages('callBrandingProfiles', 'callBrandingProfiles', {}):

            callbranding_id = profile.get('id')

            location = profile.findtext('./resourceLocation', '')

            invite = profile.findtext('./invitationTemplate', '')

            result.append({
                'id': callbranding_id,
                'location': location,
                'invite': invite,
            })
        return result

    def get_ivrbrandings(self):

        result = []
        for profile in self._iter_all_pages('ivrBrandingProfiles', 'ivrBrandingProfiles', {}):

            ivrbranding_id = profile.get('id')

            try:
                location = profile.find('./resourceLocation').text
            except Exception:
                location = ''

            result.append({
                'id': ivrbranding_id,
                'location': location,
            })
        return result

    def get_ldapsources(self):

        return self.nodes_list('ldapSources', 'ldapSources', convert_case=True, convert_bool=True)

    def get_ldapservers(self):
        return self.nodes_list('ldapServers', 'ldapServers', convert_case=True, convert_bool=True)

    def get_ldapmappings(self):
        return self.nodes_list('ldapMappings', 'ldapMappings', convert_case=True, convert_bool=True)

    def get_systemprofiles(self, native_names=False):

        response = self.get('system/profiles')
        profiles = safe_xml_fromstring(response.text)

        result = {}
        for node in profiles:
            result[node.tag] = node.text

        return result

    def save_tenant(self, name, callbranding=None, ivrbranding=None, id=None, enable_recording=False, enable_streaming=False):

        data = {
                'name': name,
                'callBrandingProfile': callbranding or '',
                'ivrBrandingProfile': ivrbranding or '',
                }

        if enable_recording or enable_streaming:
            profile = {}
            if enable_recording:
                profile['recordingControlAllowed'] = 'true'
            if enable_streaming:
                profile['streamingControlAllowed'] = 'true'

            data['callProfile'] = self._create_object('callProfiles', profile)

        if id:
            response = self.put('tenants/%s' % id, data)
        else:
            response = self.post('tenants', data)
            id = get_url_basename(response.headers['Location'])

        from datastore.utils.acano import sync_tenants_from_acano_extended
        sync_tenants_from_acano_extended(self, [self.nodes_dict('tenants/{}'.format(id), convert_case=True, convert_bool=True)])
        return id

    def add_callbranding(self, location, invite_text=None):

        data = {
                'resourceLocation': location,
                'invitationTemplate': invite_text or '',
                }

        response = self.post('callBrandingProfiles', data)

        return response.headers['Location'].strip('/').split('/')[-1]

    def update_callbranding(self, id, location=None, invite_text=None):

        data = {}
        if location is not None:
            data['resourceLocation'] = location
        if invite_text is not None:
            data['invitationTemplate'] = invite_text

        response = self.put('callBrandingProfiles/%s' % id, data)
        if response.status_code != 200:
            raise self.error('Invalid status', response)

        return id

    def save_ivrbranding(self, location, id=None):

        data = {
                'resourceLocation': location,
                }

        if id:
            response = self.put('ivrBrandingProfiles/%s' % id, data)
        else:
            response = self.post('ivrBrandingProfiles', data)

        return response.headers['Location'].strip('/').split('/')[-1]

    def save_ldapsource(self, filter, server_id, mapping_id, base_dn, tenant_id, id=None):

        data = {
                'server': server_id,
                'mapping': mapping_id,
                'tenant': self.customer.acano_tenant_id if tenant_id is None else tenant_id,
                'baseDn': base_dn,
                'filter': filter,
            }

        if id:
            response = self.put('ldapSources/%s' % id, data)
            if response.status_code != 200:
                raise self.error('Invalid status', response)
            return id

        response = self.post('ldapSources', data)

        return response.headers['Location'].strip('/').split('/')[-1]

    def get_members(self, cospace_id, include_permissions=True, include_user_data=False, tenant=None):

        url = 'coSpaces/%s/coSpaceUsers' % cospace_id

        result = []

        for relation in self._iter_all_pages(url, 'coSpaceUsers'):

            relation_id = relation.get('id')

            user_jid = relation.findtext('./userJid', '')
            user_id = relation.findtext('./userId', '')
            if not user_id:  # CMS version <2.3
                user_id = relation.find('./userJid').get('id')

            cur = {
                'id': relation_id,
                'user_jid': user_jid,
                'user_id': user_id,
                'auto_generated': relation.findtext('./autoGenerated', '') == 'true',
                'permissions': None,
            }
            result.append(cur)

        if include_permissions:
            for permissions, cur in zip(
                AcanoDistributedRunner(self, lambda api, member: api._get_permissions_for_member(cospace_id, member.get('id')), result, ordered_result=True),
                result
            ):
                cur['permissions'] = permissions

        if include_user_data:
            for user_data, cur in zip(
                AcanoDistributedRunner(self, lambda api, member: api.get_user(member.get('user_id')), result, ordered_result=True),
                result
            ):
                for k, v in user_data.items():
                    if k not in cur:
                        cur[k] = v

        if not self.is_syncing:
            from datastore.utils.acano import sync_cospace_members
            sync_cospace_members(self, cospace_id, data=result)
        return result

    def get_user_private_cospace(self, user_id):
        try:
            cospaces = self.get_user_cospaces(user_id, include_cospace_data=True)
            return [c for c in cospaces if c.get('auto_generated') and c.get('ownerId') == user_id][0]
        except IndexError:
            return None

    def get_user_cospaces(self, user_id, include_cospace_data=False):

        url = 'users/%s/userCoSpaces' % user_id

        def _remove_scheduled(cospaces):
            from meeting.models import Meeting

            meeting_cospace_ids = set(
                Meeting.objects.filter(
                    provider=self.cluster,
                    provider_ref2__in=[c['id'] for c in cospaces],
                )
                .exclude(existing_ref=True)
                .values_list('provider_ref2', flat=True)
            )
            return [c for c in cospaces if str(c['id']) not in meeting_cospace_ids]

        # TODO cache

        result = []

        for cospace in self._iter_all_pages(url, 'userCoSpaces'):

            relation_id = cospace.get('id')
            cospace_id = cospace.findtext('./coSpaceId', '')

            cur = {
                'relation_id': relation_id,  # id of relation
                'id': cospace_id,
                'cospace_id': cospace_id,
            }
            result.append(cur)

        if include_cospace_data:
            for cospace_data, cur in zip(
                AcanoDistributedRunner(
                    self,
                    lambda api, cospace: api.get_cospace(cospace.get('id')),
                    result,
                    ordered_result=True,
                ),
                result,
            ):
                cur.update(
                    {
                        **cospace_data,
                        'auto_generated': cospace_data.get('autoGenerated') in (True, 'true'),
                    }
                )

        return _remove_scheduled(result)

    def add_member(
        self,
        cospace_id,
        user_jid,
        can_add_remove_members=False,
        can_remove_self=False,
        can_destroy=False,
        can_delete_messages=False,
        can_change_scope=None,
        call_leg_profile=None,
        is_moderator=False,
    ):

        if is_moderator:
            if call_leg_profile:
                raise ValueError(
                    'is_moderator and call_leg_profile can not be provided at the same time'
                )

            call_leg_profile = self._get_webinar_call_legs()[1]

        if can_change_scope is None:
            can_change_scope = is_moderator or can_add_remove_members

        data = {
            'userJid': user_jid,
            'canAddRemoveMember': 'true' if can_add_remove_members else 'false',
            'canRemoveSelf': 'true' if can_remove_self else 'false',
            'canDestroy': 'true' if can_destroy else 'false',
            'canDeleteAllMessages': 'true' if can_delete_messages else 'false',
            'canChangeScope': 'true' if can_change_scope else 'false',
            'callLegProfile': call_leg_profile or '',
        }

        response = self.post('coSpaces/%s/coSpaceUsers' % cospace_id, data)

        return response

    def remove_member(self, cospace_id, member_id):

        if '@' in member_id:
            try:
                members = self.get_members(cospace_id)
            except ResponseError as e:
                if '<coSpaceDoesNotExist' in e.get_message():
                    return
                raise
            member_id = [m for m in members if m['user_jid'] == member_id]

            if not member_id:
                return
            member_id = member_id[0]['id']

        response = self.delete('coSpaces/%s/coSpaceUsers/%s' % (cospace_id, member_id))

        if response.status_code != 200:
            raise self.error('status not 200: %s' % response.text, response)

        return response

    def update_member(self, cospace_id, member_id, **kwargs):

        if '@' in member_id:
            members = self.get_members(cospace_id)
            member_id = [m for m in members if m['user_jid'] == member_id]

            if not member_id:
                return
            member_id = member_id[0]['id']

        if kwargs.get('isModerator') is not None:
            if kwargs.pop('isModerator') in (True, 'true'):
                kwargs['callLegProfile'] = self._get_webinar_call_legs()[1]
            else:
                kwargs['callLegProfile'] = ''

        url = 'coSpaces/%s/coSpaceUsers/%s' % (cospace_id, member_id)

        # TODO check for kwargs/use same names as add_member?
        response = self.put(url, data=kwargs)

        if not response.status_code == 200:
            raise self.error('status not 200: %s' % response.text, response)

        # TODO check response?
        return response

    def get_user(self, user_id):

        if self.use_cache_for_single_objects:
            users, count = self.find_users_cached(user_id=user_id)
            if users:
                return users[0]

        try:
            response = self.get('users/%s' % user_id)
        except NotFound:
            from datastore.models.acano import User
            User.objects.filter(provider=self.cluster, uid=user_id, is_active=True).update(is_active=False)
            raise

        user = safe_xml_fromstring(response.text)

        if not user.tag == "user":
            raise self.error('Result tag is not user (%s)' % user.tag, response)

        user_jid = user.findtext('./userJid')

        result = {
            'id': user.get('id'),
            'uid': user.get('id'),
            'jid': user_jid,
            'name': user.findtext('./name', ''),
            'email': user.findtext('./email', ''),
            'tenant': user.findtext('./tenant', ''),
            'cdr_tag': user.findtext('./cdrTag', ''),
        }

        if not self.is_syncing:
            from datastore.utils.acano import sync_acano_user
            synced = sync_acano_user(self, user_id, data=result)
            if self.allow_cached_values:
                return synced.to_dict()

        return result

    def clear_chat(self, cospace_id, date_from=None, date_to=None):

        data = {}
        if date_from:
            data['maxAge'] = int((now() - date_from).total_seconds())
        if date_to:
            data['minAge'] = int((now() - date_to).total_seconds())

        response = self.delete('coSpaces/{}/messages'.format(cospace_id), data=data)
        if not response.status_code == 200:
            raise self.error('status not ok: %s' % response.text, response)

        return True

    def get_status(self, timeout=None):

        response = self.get('system/status', timeout=timeout)

        if not response.status_code == 200:
            raise self.error('status not ok: %s' % response.text, response)

        status = safe_xml_fromstring(response.text)

        result = {}
        for t in status:
            result[t.tag] = t.text or ''

        if result.get('softwareVersion') and result['softwareVersion'] != self.provider.software_version:
            self.provider.software_version = result['softwareVersion']
            if self.provider.pk:
                self.provider.save(update_fields=['software_version'])

        has_database = True
        if self.provider.is_service_node and result.get('clusterEnabled') == 'false':
            if safe_xml_fromstring(self.get('system/database').content).get('clustered') == 'disabled':
                has_database = False

        if self.provider.get_option('has_database') != has_database:
            self.provider.set_option('has_database', has_database)

        if result.get('uptimeSeconds'):
            result['uptime'] = timedelta(seconds=int(result['uptimeSeconds']))

        return result

    def get_alarms(self):
        response = self.get('system/alarms')

        if not response.status_code == 200:
            raise self.error('status not ok: %s' % response.text, response)

        alarms = safe_xml_fromstring(response.text)

        result = []
        for alarm in alarms:
            active_since = int(alarm.findtext('./activeTimeSeconds', '0'))
            cur = {
                'type': alarm.findtext('./type', '') or alarm.text or '',
                'start': now() - timedelta(seconds=active_since),
                'timesince': active_since,
                'id': alarm.get('id'),
            }
            extra = {}
            for a in alarm:
                if a.tag in ('type', 'activeTimeSeconds'):
                    continue
                extra[a.tag] = a.text

            for k, v in alarm.attrib.items():
                if k in ('id',):
                    continue
                extra[k] = v

            if extra:
                cur['extra'] = extra
            result.append(cur)

        return result

    def check_cdr_enabled(self):
        from statistics.models import Server
        response = self.get('system/cdrReceivers')

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        hosts = {settings.EPM_HOSTNAME, settings.HOSTNAME}
        valid = {'https://{}{}'.format(host, server.get_cdr_path())
                 for server in Server.objects.filter(type=Server.ACANO)
                 for host in hosts
                 }
        receivers = safe_xml_fromstring(response.text)
        for receiver in receivers:
            if receiver.findtext('./uri') in valid:
                return True

        return False

    def get_clustered_call_bridges(self, include_data=False):

        result = []
        for cb in self._iter_all_pages('callBridges', 'callBridges'):
            cur = self.convert_node_to_dict(cb, convert_bool=True)
            if include_data:
                cur.setdefault('address', '')
                cur.update(self.nodes_dict('callBridges/{}'.format(cur['id'])))
            cur['id'] = cb.get('id')
            result.append(cur)
        return result

    def get_call_bridge_id(self, force=False):
        call_bridge_id = self.provider.get_option('call_bridge_id')
        if not call_bridge_id or force:
            cluster_data = self.nodes_dict('system/configuration/cluster')

            for cb in self.get_clustered_call_bridges():
                if cb.get('name') == cluster_data['uniqueName']:
                    call_bridge_id = cb.get('id')
                    self.provider.set_option('call_bridge_id', call_bridge_id)
                    break
            else:
                return None

        return call_bridge_id

    def get_clustered_databases(self):
        result = []
        for cluster in safe_xml_fromstring(self.get('system/database').content):
            for node in cluster:
                result.append(dict(node.items()))
        return result

    def get_all_clustered_servers(self):

        result = {
            'call_bridges': self.get_clustered_call_bridges(include_data=True),
            'database': self.get_clustered_databases(),
            'recorders': [],
            'streamers': [],
        }
        try:
            result['recorders'] = [self.convert_node_to_dict(r) for r in self._iter_all_pages('recorders', 'recorders')]
            result['streamers'] = [self.convert_node_to_dict(r) for r in self._iter_all_pages('streamers', 'streamers')]
        except NotFound:
            pass

        return result

    def _iter_all_pages(self, url, require_tag=None, params=None, yield_root=False):
        return AcanoPageIterator(self, url, params=params, require_tag=require_tag, yield_root=yield_root)

    def _iter_pages_with_count(self, url, require_tag, params, limit=None):

        i = 0
        result = []
        count = None

        if limit and params.get('limit') is not None and params['limit'] != limit:
            raise ValueError('Missmatching limit in kwarg ')
        if limit:
            params['limit'] = limit

        break_early = False

        for item in self._iter_all_pages(url, require_tag, params, yield_root=True):
            if count is None:
                count = int(item.get('total'))
                continue

            if limit is not None and i >= limit:
                break_early = True
                break

            result.append(item)
            i += 1

        # no real filter for default tenant. guess value instead of iterating all pages
        if params.get('tenantFilter') == '' and self.is_multitenant:
            count = (params.get('offset') or 0) + len(result)
            if limit and (count > limit or (break_early and count == limit)):
                count += 1  # allow next page
            return result, count

        return result, count

    def _iter_all_cospaces(self, tenant_id=None, filter=''):

        for item in self._iter_all_pages('coSpaces', 'coSpaces', {'filter': filter, 'tenantFilter': tenant_id}):
            yield item

    def _iter_all_users(self, tenant_id=None, filter=''):

        for item in self._iter_all_pages('users', 'users', {'filter': filter, 'tenantFilter': tenant_id}):
            yield item

    def set_cospace_stream_urls(self, get_key_callback, tenant_id=''):

        from recording.models import CoSpaceAutoStreamUrl
        if not callable(get_key_callback):
            raise ValueError('Callback must be callable')

        existing = CoSpaceAutoStreamUrl.objects.filter(tenant_id=tenant_id).values_list('cospace_id', 'stream_url')
        existing_map = dict(existing)

        result = {}

        for cospace_node in self._iter_all_cospaces(tenant_id=tenant_id):

            cospace_id = cospace_node.get('id')

            correct_url = get_key_callback(cospace_node.findtext('./uri', cospace_node.findtext('./callId', '')))

            if not correct_url:
                continue

            if existing_map.get(cospace_id) == correct_url:
                continue

            cospace = self.get_cospace(cospace_id)
            if cospace.get('streamUrl') == correct_url:
                continue

            should_update = cospace.get('streamUrl', '') == ''

            if cospace.get('streamUrl') and cospace['streamUrl'] == existing_map.get(cospace_id):  # update previously autoset
                should_update = True

            if should_update:

                result[cospace_id] = correct_url

                self.update_cospace(cospace_id, {'streamUrl': correct_url})
                CoSpaceAutoStreamUrl.objects.update_or_create(
                    provider=self.cluster,
                    cospace_id=cospace_id,
                    defaults=dict(tenant_id=cospace.get('tenant', ''), stream_url=correct_url),
                )

        return result

    def sync_ldap(self, ldap_id=None, tenant_id=None):

        data = {}
        if ldap_id:
            data['ldapSource'] = ldap_id
        if tenant_id is not None:
            data['tenant'] = tenant_id

        response = self.post('ldapSyncs', data)
        if response.status_code != 200:
            raise self.error('Invalid status', response)

        from provider import tasks

        tasks.cache_single_cluster_data.apply_async(
            [self.cluster.pk], {'incremental': True}, countdown=30
        )

        return response

    def clear_old_call_chat_messages(self, since=None, tenant_id=None):
        from statistics.models import Server, Call

        since = since or now() - timedelta(minutes=10)

        tenant_filter = {'tenant': tenant_id} if tenant_id is not None else {}

        for server in Server.objects.filter(type=Server.ACANO).filter(Q(customer=self.customer) | Q(customer__isnull=True)):

            cospace_ids = set(Call.objects.filter(server=server, ts_stop__gte=since, **tenant_filter)
                              .values_list('cospace_id', flat=True))

            ongoing_call_cospaces = set(Call.objects.filter(server=server, cospace_id__in=cospace_ids,
                                                ts_start__gt=since - timedelta(hours=4), ts_stop__isnull=True)
                            .values_list('cospace_id', flat=True))

            for cospace_id in (cospace_ids - ongoing_call_cospaces):
                if not cospace_id or not cospace_id.strip():
                    continue

                try:
                    self.clear_chat(cospace_id)
                except NotFound:
                    pass
                except Exception:
                    capture_exception()


    def _get_permissions_for_member(self, cospace_id, member_id):
        response = self.get('coSpaces/%s/coSpaceUsers/%s' % (cospace_id, member_id))
        member = safe_xml_fromstring(response.text)
        keys = [
            'canDestroy',
            'canAddRemoveMember',
            'canChangeName',
            'canChangeUri',
            'canChangeCallId',
            'canChangePasscode',
            'canPostMessage',
            'canDeleteAllMessages',
            'canRemoveSelf',
            'canChangeNonMemberAccessAllowed',
        ]
        result = OrderedDict([
            (key, (member.findtext('./{}'.format(key), '') == 'true')) for key in keys
        ])

        moderator_profile_ids = self.get_moderator_call_profile_ids()
        result['isModerator'] = member.findtext('./callLegProfile', '') in moderator_profile_ids
        return result

    def get_moderator_call_profile_ids(self, force=True):
        profile_ids = self.cluster.get_option('moderator_call_profiles') or []
        if not profile_ids or not all(isinstance(p, str) for p in profile_ids) or force:
            profile_ids.append(self._get_webinar_call_legs()[1])
            profile_ids.append(self._get_webinar_call_legs(True)[1])

            for api in self.iter_clustered_provider_api(only_call_bridges=True):
                profile_ids.append(api.provider.get_option('webinar_guest_call_leg'))
                profile_ids.append(api.provider.get_option('webinar_guest_call_leg_enc'))

            self.cluster.set_option('moderator_call_profiles', profile_ids)
        return profile_ids

    def get_secret_for_access_method(self, cospace_id, access_method_id):
        return self.get_cospace_accessmethod(cospace_id, access_method_id)['secret']

    def get_internal_domains(self, clear=False):
        response = self.get('inboundDialPlanRules')
        if response.status_code != 200:
            raise self.error('Invalid response code: {}'.format(response.status_code), response)

        initial = [d for d in self.provider.internal_domains.split(',') if d.strip()]
        if clear:
            initial = []

        domains = set(initial)

        root = safe_xml_fromstring(response.content)
        for plan in root:
            domain = plan.findtext('./domain', '').strip()
            if not domain or domain.replace('.', '').isdigit():  # ignore empty + ip
                continue

            domains.add(domain)

        return initial + list(domains - set(initial))

    def get_load(self):
        response = self.get('system/load')

        m = re.search(r'<mediaProcessingLoad>(\d+)</mediaProcessingLoad>', response.text)
        return int(m.group(1)) if m else -1

    def sync_tenant_customers(self, name_conflict='add_suffix'):
        from customer.models import Customer

        if name_conflict not in ('add_suffix', 'merge', 'ignore', 'skip'):
            raise ValueError('Invalid conflict mode')

        customers = Customer.objects.all()
        tenant_map = {}
        name_list_map = defaultdict(list)
        for c in customers:
            if c.acano_tenant_id:
                tenant_map[c.acano_tenant_id] = c
            name_list_map[str(c)].append(c)

        suffix_name_count = defaultdict(lambda: 0)

        def _match_name(customer_name, tenant_id):
            'match customer without provider and acano_tenant_id'
            if not customer_name:
                return

            for name_match in name_list_map.get(customer_name, []):
                if name_match.acano_tenant_id:
                    continue

                if name_match.lifesize_provider_id:
                    if name_conflict != 'merge':
                        continue

                existing = name_match
                if not existing.lifesize_provider:
                    existing.lifesize_provider = self.cluster
                existing.acano_tenant_id = tenant_id
                existing.save()
                return existing

        for tenant in self.iter_nodes_list('tenants', 'tenants'):

            if tenant['id'] in tenant_map:
                existing = tenant_map[tenant['id']]
                continue

            default_name = 'No name {}'.format(tenant['id'].split('-')[0])
            name = tenant.get('name') or ''

            existing = _match_name(name, tenant['id'])
            if existing:
                continue

            if name and name in name_list_map:
                if name_conflict == 'add_suffix':
                    if suffix_name_count[name]:
                        suffix = ' ({} {})'.format(self.cluster, suffix_name_count[name] + 1)
                    else:
                        suffix = ' ({})'.format(self.cluster)
                    suffix_name_count[name] += 1

                    name = '{}{}'.format(name, suffix)
                    existing = _match_name(name, tenant['id'])
                elif name_conflict == 'skip':
                    continue

            if not existing:
                Customer.objects.get_or_create(lifesize_provider=self.cluster,
                                               acano_tenant_id=tenant['id'],
                                               defaults=dict(
                                                   title=name or default_name,
                                               ))

        from datastore.utils.acano import sync_tenants_from_acano
        sync_tenants_from_acano(self, force_full_sync=True)

    @classmethod
    def sync_profiles_all(cls):
        from customer.models import Customer

        result = []

        for cluster in AcanoCluster.objects.all():

            for provider in cluster.get_clustered():
                try:
                    api = provider.get_api(Customer.objects.first())
                    api.sync_profiles()
                except (ResponseConnectionError, AuthenticationError):
                    pass
                except Exception:
                    logger.info(
                        'Error when syncing profiles on provider %s (%s)',
                        provider.pk,
                        provider,
                        exc_info=True,
                    )
                result.append(provider)

        return result

    def sync_profiles(self):
        self._get_webinar_call_legs(True, sync=True)
        self._get_webinar_call_legs(False, sync=True)

        self._get_no_chat_call_profile(sync=True)

        self._get_needs_activation_call_leg_profile(True, sync=True)
        self._get_needs_activation_call_leg_profile(False, sync=True)

        self.get_moderator_call_profile_ids(force=True)

    def set_cdr_settings(self, server=None):

        from statistics.models import Server

        server = server or Server.objects.filter(type=Server.ACANO).first()
        if not server:
            server = Server.objects.create(name='CMS', type=Server.ACANO)

        data = {
            'uri': server.get_cdr_url(),
        }
        response = self.post('system/cdrReceivers', data)

        if response.status_code not in (200, 201):
            raise self.error('Invalid status when adding cdr receiver ({})'.format(response.status_code), response)

        return response

    def get_ssh(self):
        from .acano_ssh import AcanoSSHClient
        provider = self.provider
        return AcanoSSHClient(self.provider.get_option('ssh_host') or provider.ip or provider.hostname,
                              self.provider.get_option('ssh_port') or 22,
                              self.provider.username,
                              self.provider.password,
                              )


clusters_in_threads = {}

T = TypeVar('T')
RT = TypeVar('RT')


class AcanoDistributedRunner:
    def __init__(
        self,
        api: AcanoAPI,
        run_fn: Callable[[AcanoAPI, T], RT],
        items: Sequence[T] = None,
        ordered_result=False,
        task_timeout=120,
    ):

        self.api = api
        self.items = list(items or [])[:]
        self.apis = api.get_apis_with_database()
        shuffle(self.apis)
        self.run_fn = run_fn
        self.ordered_result = ordered_result
        self.task_timeout = task_timeout

    @property
    def enable_threads(self):
        if len(self.items) <= 1:
            return False
        if settings.TEST_MODE:
            return False
        if self.api.cluster.pk in clusters_in_threads:
            return False
        return True

    def iter(self) -> Iterator[RT]:

        if self.enable_threads:
            try:
                clusters_in_threads[self.api.cluster.pk] = True
                yield from self.run_threaded()
            finally:
                clusters_in_threads.pop(self.api.cluster.pk, None)
        else:
            yield from self.run_single()

    def run_threaded(self) -> Iterator[RT]:

        from multiprocessing.pool import ThreadPool
        from queue import SimpleQueue
        queue = SimpleQueue()

        for api in self.apis:
            queue.put(api)

        for api in self.apis:  # Use more than one connection to the same server
            if queue.qsize() >= MAX_THREADS:
                break
            queue.put(api.clone_api(api.provider))

        available = len(self.apis)

        count = 0

        start = monotonic()

        def _run(obj):
            nonlocal available, count

            count += 1

            for _try in range(3):
                if available <= 0:
                    raise ResponseConnectionError('No servers available')

                api = queue.get(timeout=max(0, self.task_timeout - (monotonic() - start)))
                try:
                    result = self.run_fn(api, obj)
                except ResponseConnectionError as e:
                    if not settings.TEST_MODE:
                        sleep(1)
                    if api.connection_error_count > 5:
                        available -= 1  # dont put back into queue
                        return e
                    result = e
                except Exception as e:
                    result = e

                queue.put(api)
                return result

        with ThreadPool(min(len(self.apis), MAX_THREADS)) as pool:
            _map = pool.imap if self.ordered_result else pool.imap_unordered
            for result in _map(_run, self.items):
                if isinstance(result, Exception):
                    raise result
                else:
                    yield result

    def run_single(self):
        for item in self.items:
            result = self.run_fn(self.api, item)
            if isinstance(result, Exception):
                raise result
            else:
                yield result

    def as_list(self) -> List[RT]:
        return list(self.iter())

    def __iter__(self):
        return self.iter()


class AcanoDistributedGet(AcanoDistributedRunner):

    def __init__(self, api: AcanoAPI, urls: Sequence[str] = None, ordered_result=False):
        super().__init__(api, run_fn=self.get, items=urls, ordered_result=ordered_result)

    def get(self, api: AcanoAPI, url: str) -> Element:
        response = api.get(url)
        if response.status_code != 200:
            raise api.error('Invalid status code {}'.format(response.status_code), response)

        return safe_xml_fromstring(response.content)

    def iter_dicts(self, convert_case=False, convert_bool=False):
        for node in self.iter():
            yield self.api.convert_node_to_dict(node, convert_case=convert_case, convert_bool=convert_bool)


class AcanoPageIterator:

    DISABLE_THREADS = {'calls', 'legs', 'calllegs', 'participants'}

    def __init__(self, api: AcanoAPI, url: str, params: Dict = None, require_tag='', yield_root=False):
        self.url = url
        self.api = api
        self.params = (params or {}).copy()
        if '?' in url:
            self.params = {**dict(parse_qsl(url.split('?', 1)[1])), **self.params}

        self.params.setdefault('limit', 50)

        self.require_tag = require_tag
        self.yield_root = yield_root

        self.offset = self.params.get('offset') or 0
        self.total_count = 0
        self.per_page = 0

        self.only_call_bridges = False  # use all available servers

        self.tenant = self.params.get('tenantFilter')

        self.processed = 0

        if self.tenant is None:
            self.params.pop('tenant', None)

    @property
    def allow_threads(self):
        parts = self.url.split('?')[0].strip('/').split('/')

        if parts[0].lower() in self.DISABLE_THREADS or parts[-1].lower() in self.DISABLE_THREADS:
            return False

        if self.api.cluster.pk in clusters_in_threads:
            return False

        return True

    def get_xml(self, api: AcanoAPI, offset: int):

        if api is None:
            api = self.api

        logger.debug('Start fetching %s offset %s using %s' % (self.url, offset, api.provider))

        response = api.get(self.url, params={**self.params, 'offset': offset})

        logger.debug('Fetched %s offset %s using %s' % (self.url, offset, api.provider))
        items = safe_xml_fromstring(response.text)
        self.processed += len(items)

        if self.require_tag and items.tag != self.require_tag:
            raise api.error('Result tag is not %s (%s)' % (self.require_tag, items.tag), response,
                            {'url': self.url, 'params': self.params})

        return items

    def get_first_page(self) -> Element:
        items = self.get_xml(self.api, self.offset)
        self.total_count = int(items.get('total'))

        self.per_page = len(items)  # acano has different max limits for different api calls

        self.offset += len(items)
        return items

    def buffer_pages(self, it) -> Iterator[List[Element]]:
        """
        Buffer one page to try to start fetching next batch in background
        """
        last = None

        def _reset_last(replace=None):
            nonlocal last
            was_last, last = last, replace
            if isinstance(was_last, AsyncResult):
                was_last = was_last.get()
            if was_last is not None:
                yield was_last

        while True:
            try:
                if isinstance(last, AsyncResult):
                    # wait for last page before starting next batch
                    last = last.get()
                pages = next(it)
                yield from _reset_last(replace=pages)
            except StopIteration:
                yield from _reset_last()
                break
            except Exception:
                yield from _reset_last()
                raise

    def get_apis(self):
        if self.only_call_bridges:
            apis = list(self.api.iter_clustered_provider_api())
        else:
            apis = self.api.get_apis_with_database()

        for api in apis[:]:  # Use more than one connection to the same server
            if len(apis) >= MAX_THREADS:
                break
            apis.append(api.clone_api(api.provider))

        return apis

    def iter_pages_single(self) -> Iterator[List[Element]]:
        while self.offset < self.total_count:
            yield [self.get_xml(self.api, self.offset)]
            self.offset += self.per_page

    def iter_pages_threaded(self, apis) -> Iterator[Union[ApplyResult, List[Element]]]:

        while self.offset < self.total_count:
            with ThreadPool(min(len(apis), MAX_THREADS)) as pool:
                args = []
                for api in apis[:MAX_THREADS]:
                    if self.offset > self.total_count:
                        break
                    args.append((api, self.offset))
                    self.offset += self.per_page
                pages = pool.starmap_async(self.get_xml, args)
                yield pages

    def iter_pages(self) -> Iterator[Element]:
        yield self.get_first_page()

        if self.offset > self.total_count:
            return

        if self.allow_threads and self.offset + self.per_page < self.total_count:
            apis = self.get_apis()
            if len(apis) > 1:
                clusters_in_threads[self.api.cluster.pk] = True
                try:
                    for pages in self.buffer_pages(self.iter_pages_threaded(apis)):
                        yield from pages
                finally:
                    clusters_in_threads.pop(self.api.cluster.pk, None)
                return

        for pages in self.iter_pages_single():
            yield from pages

    def iter(self) -> Iterator[Element]:

        yield_root = self.yield_root

        for items in self.iter_pages():
            if yield_root:
                yield_root = False
                yield items

            for item in items:
                if self.tenant is None or item.findtext('./tenant', '') == self.tenant:
                    yield item

        if self.processed != self.total_count:
            logger.info('Total item diff after iterating all pages. %s processed but initial count is %s',
                        self.processed, self.total_count)

    def __iter__(self):
        return self.iter()
