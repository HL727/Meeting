import time
import uuid
from math import ceil
from random import randint
from typing import List, Union, Dict, TYPE_CHECKING, Tuple

import sentry_sdk
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.utils.dateparse import parse_datetime

from django.utils.text import slugify
from django.utils.timezone import now, utc, make_aware
from requests import Response

import datastore.models.customer
from datastore.models import pexip as ds
from statistics.parser.utils import clean_target
from ..exceptions import AuthenticationError, DuplicateError, MessageResponseError, NotFound, \
    ResponseConnectionError, ResponseTimeoutError
from datetime import timedelta, datetime
from urllib.parse import urlencode, quote
from .base import ProviderAPI, BookMeetingProviderAPI, MCUProvider, DistributedReadOnlyCallControlProvider
from sentry_sdk import capture_exception, capture_message
from collections import defaultdict
import re
from django.conf import settings

import logging

from ..models.pexip import PexipSpace, PexipEndUser


if TYPE_CHECKING:
    from provider.models.provider import Provider
    from numberseries.models import NumberRange
    from debuglog.models import PexipHistoryLog

logger = logging.getLogger(__name__)


LOOKUP_CALL_CONFERENCE_PREFIX = 'lookup.'

"""
Nomenclature in class:
* cospace = video meeting room / auditorium / test call. Have aliases and settings
* webinar = audatorium
* call = live conference call
* leg / participant = participant in live conference call
* alias = uri. local_alias = uri on the pexip bridge, remote_alias = uri of remote client

In pexip both meeting room and live calls are called conference
and have no difference between legs and participants.

Multiple participants can belong to the same client (e.g. skype)
"""

"""
Multi tenant mode matching priority:

1. Local override
2. Service tag argument using t=123456-12345
3. VMR using conference-name, goto 1)
4. local_alias using CustomerMatch matching
5. remote_alias (only for participants) using Customer Match
6. empty string
"""


class PexipAPI(BookMeetingProviderAPI, DistributedReadOnlyCallControlProvider, MCUProvider, ProviderAPI):

    _use_cache_for_single_objects = True
    provider: 'Provider'

    def update_request_kwargs(self, kwargs):
        kwargs['auth'] = (self.provider.username, self.provider.password)

        kwargs['allow_redirects'] = False
        headers = kwargs.pop('headers', None) or {}
        headers['Content-Type'] = 'application/json'
        kwargs['headers'] = headers

        return kwargs

    def request(self, url, *args, **kwargs):

        data = False
        if args and args[0]:
            data = args[0]
            args = args[1:]
        elif 'data' in kwargs:
            data = kwargs['data'] or {}

        if data and isinstance(data, (list, tuple, dict)):
            kwargs['data'] = DjangoJSONEncoder().encode(data)
        return super().request(url, *args, **kwargs)

    def login(self, force=False):

        return True

    def get_url(self, path=None):
        return '%s/api/admin/%s' % (self.get_base_url(), path or '')

    def check_login_status(self, response: Response):
        if '/accounts/login/' in response.headers.get('Location', '') or response.status_code in (401, 403):
            raise AuthenticationError(_('Authentication failed'), response)

    def check_response_errors(self, response: Response):

        self.check_login_status(response)

        if response.status_code == 503:
            self.error_503_count += 1
            self.connection_error_count += 1
            raise ResponseConnectionError('Server Unavailable', response)

        if response.status_code != 400:
            return

        try:
            data: dict = response.json()
        except (ValueError, AttributeError):
            return

        if len(data) == 1 and data.get('error') and isinstance(data['error'], str):
            return MessageResponseError(data.get('error'), response)

        self._check_form_errors(response)

    def _check_form_errors(self, response: Response):
        data = response.json()

        if len(data) != 1:
            return

        _key, error_list = list(response.json().items())[0]

        if not isinstance(error_list, dict):
            return

        for k, v in error_list.items():
            if isinstance(v, list) and isinstance(v[0], str):
                if 'already exists' in v[0]:
                    raise DuplicateError('{}: {}'.format(k, v[0]), response)
                if (k, v[0]) == ('participant_id', 'Failed to find participant.'):
                    raise NotFound(v[0], response)
                if (k, v[0]) == ('conference_id', 'Failed to find conference.'):
                    raise NotFound(v[0], response)
                raise MessageResponseError(
                    '{}: {}'.format(k, v[0]).replace('__all__: ', ''), response, error_list
                )

    def get_sip_uri(self, uri: Union[int, str] = None, cospace: Dict = None):

        if cospace:
            if cospace.get('full_uri'):
                return cospace.get('full_uri')

            try:  # full uri
                return [a['alias'] for a in cospace['aliases'] if '@' in a['alias']][0]
            except (IndexError, KeyError):
                pass

            if cospace.get('aliases'):
                uri = cospace['aliases'][0]['alias']

        if uri is None:
            return ''

        if not isinstance(uri, (str, int)):
            raise ValueError('uri is not a string!', uri)

        if '@' in str(uri):
            return uri

        return '%s@%s' % (uri, self.get_settings(self.customer).get_main_domain())

    def get_web_url(self, alias=None, passcode=None, cospace=None):

        cluster_web_domain = self.get_settings(self.customer).get_web_domain()

        if cospace:
            try:
                alias = alias or cospace.get('call_id') or [a['alias'] for a in cospace.get('aliases') or ()][0]
            except IndexError:
                return ''

            if not passcode:
                passcode = cospace['guest_pin'] if cospace.get('allow_guests') else cospace.get('pin') or ''

        params = {}

        if alias:
            params['conference'] = alias
        if alias and passcode:
            params['pin'] = passcode

        return 'https://{}/webapp/home/?{}'.format(cluster_web_domain or self.provider.web_host or self.provider.internal_domain,
                                                   urlencode(params),
                                                   ).rstrip('?')

    def check_not_found(self, response, extra=None):
        pass  # 404 in parent is enough

    def get_alias_urls(self, title, call_id):
        domains = [self.provider.internal_domain]

        aliases = [slugify(title), call_id]

        result = []
        for alias in aliases:
            result.append({'alias': alias})
            for domain in domains:
                result.append({'alias': '{}@{}'.format(alias, domain)})
        return result

    @classmethod
    def translate_layout(cls, acano_layout):
        return {
            'automatic': 'five_mains_seven_pips',
            'allEqual': 'two_mains_twentyone_pips',
            'speakerOnly': 'one_main_zero_pips',
            'telepresence': 'one_main_seven_pips',
            'stacked': 'one_main_seven_pips',
        }.get(acano_layout) or 'five_mains_seven_pips'

    def book(self, meeting, uri=None):

        existing_id = meeting.provider_ref2
        call_id = meeting.provider_ref

        uri = uri or meeting.get_preferred_uri()

        if not call_id:
            number_range = self.get_scheduled_room_number_range()
            call_id = str(number_range.random())

        name = meeting.title or '{} möte'.format(self.customer.title)
        name = '{} : {}'.format(name, call_id)  # TODO uuid for uniqueness? Check for duplicate first?

        data = {
            'name': name,
            'call_id': call_id,
            'pin': meeting.password,
            'guest_pin': '',
            'host_view': self.translate_layout(meeting.moderator_layout or meeting.layout),
            'guest_view': self.translate_layout(meeting.layout),
            'primary_owner_email_address': meeting.creator,
        }

        theme_profile = self.get_settings(meeting.customer).get_theme_profile()
        if theme_profile:
            data['ivr_theme'] = theme_profile

        meeting_settings = meeting.get_settings()

        if meeting_settings['force_encryption']:
            data['crypto_mode'] = 'on'

        if meeting_settings['disable_chat']:
            data['enable_chat'] = 'no'

        if meeting.moderator_password or meeting_settings.get('lobby_pin'):
            data.update(
                {
                    'pin': meeting.moderator_password or meeting_settings['lobby_pin'],
                    'guest_pin': meeting.password,
                    'allow_guests': True,
                }
            )

        webinar_config = meeting.get_webinar_info()
        if webinar_config:
            data.update(
                {
                    'pin': meeting.moderator_password
                    or webinar_config['moderator_pin']
                    or meeting_settings.get('lobby_pin'),
                    'guest_pin': meeting.password,
                    'allow_guests': True,
                    'service_type': 'lecture',
                }
            )
        else:
            data.update({
                'service_type': 'conference',
            })

        cospace_id = existing_id

        if existing_id:
            try:
                self.update_cospace(existing_id, data)
            except NotFound:
                cospace_id = None

        data['tag'], guid = self._get_tag(existing_id=cospace_id)

        if not cospace_id:
            cospace_id = self.add_cospace(data, try_increase_number=not meeting.provider_ref, sync=False)
            meeting.ts_provisioned = now()

        if cospace_id:
            cospace = self.get_cospace(cospace_id)
        else:
            raise self.error('Cospace ID not found')

        meeting.provider_ref2 = cospace['id']
        meeting.provider_ref = call_id
        meeting.provider_secret = cospace.get('secret') or ''

        PexipSpace.objects.update_or_create(cluster=self.cluster or self.provider, external_id=cospace['id'], defaults={
            'guid': guid,
            'call_id': call_id,
        })

        meeting.activate()

        if not meeting.existing_ref:
            from datastore.models.pexip import Conference

            Conference.objects.filter(provider=self.cluster, cid=meeting.provider_ref2).update(
                is_scheduled=True
            )

        return cospace['id']

    def rebook(self, meeting, new_data):
        self.update_meeting_settings(meeting, new_data)
        self.book(meeting)
        return meeting

    def lobby_pin(self, cospace_id, moderator_pin, moderator_layout=None):
        data = {
            'pin': moderator_pin,
            'allow_guests': True,
        }
        if moderator_layout:
            data['host_view'] = self.translate_layout(moderator_layout)
        return self.update_cospace(cospace_id, data)

    def book_unprotected_access(self, meeting):
        raise NotImplementedError()

    def update_cospace(self, cospace_id, data):

        def _sync():
            try:  # refresh cache
                self.sync_single_conference(cospace_id)
            except Exception:
                pass
            return cospace_id

        data.pop('id', None)

        _unset = object()

        tenant = data.pop('tenant', _unset)
        if tenant is not _unset:
            self.set_cospace_tenant(cospace_id, tenant)

        organization_unit = data.pop('organization_unit', _unset)
        if organization_unit is not _unset:
            self.set_cospace_organization_unit(cospace_id, organization_unit)

        if not data:  # only local changes, skip api call
            return _sync()

        if data.get('guest_pin'):
            data['allow_guests'] = True

        result = self.patch('configuration/v1/conference/{}/'.format(cospace_id), data)

        if result.status_code != 202:
            raise self.error(result)

        return _sync()

    def set_cospace_tenant(self, cospace_id, tenant_id):

        from customer.models import Customer
        return PexipSpace.objects.update_or_create(cluster=self.cluster, external_id=cospace_id,
                                                   defaults=dict(customer=Customer.objects.find_customer(pexip_tenant_id=tenant_id, cluster=self.cluster)))

    def set_cospace_organization_unit(self, cospace_id, organization_unit):

        from organization.models import OrganizationUnit
        if organization_unit and isinstance(organization_unit, (int, str)):
            organization_unit = OrganizationUnit.objects.filter(pk=organization_unit)

        return PexipSpace.objects.update_or_create(cluster=self.cluster, external_id=cospace_id,
                                                   defaults=dict(organization_unit=organization_unit or None))

    def _get_tag(self, existing_id=None, guid=None, meeting=None):
        cdr_tag = [
            ('t', self.customer.pexip_tenant_id),
            ('c', self.customer.id),
        ]

        if existing_id:
            if guid:
                raise ValueError('Both guid and existing_id cant be provider')
            space, created = PexipSpace.objects.get_or_create(cluster=self.cluster or self.provider,
                                                              external_id=existing_id,
                                                              defaults={
                                                                  'guid': uuid.uuid4(),
                                                              })
            guid = space.guid
        else:
            guid = guid or uuid.uuid4()

        cdr_tag.append(('i', str(guid)))

        if meeting:
            cdr_tag.append(('m', meeting.pk))
        return urlencode([x for x in cdr_tag if x[1]]), guid

    def get_next_call_id(self, call_id: Union[None, int, str, 'NumberRange'], number_range=None, random=False):
        """Get callId from static value or from number range"""
        from datastore.models.pexip import Conference

        if hasattr(call_id, 'use'):  # number range instance passed call_id
            number_range = number_range or call_id
            call_id = None

        if call_id:
            pass
        elif number_range and random:
            call_id = number_range.random()
            while Conference.objects.match_by_alias(str(call_id), self.cluster):
                call_id = number_range.random()
        elif number_range:
            call_id = number_range.use()
            while Conference.objects.match_by_alias(str(call_id), self.cluster):
                call_id = number_range.use()

        return str(call_id) if call_id else None

    def add_cospace(self, data, creator='', try_increase_number=False, sync=True):

        tenant = data.pop('tenant', None)
        organization_unit = data.pop('organization_unit', None)
        random_call_id = data.pop('random_call_id', None)

        call_id = self.get_next_call_id(data.pop('call_id', None), random=random_call_id)

        aliases = data.pop('aliases', None) or []

        if data.get('guest_pin'):
            data['allow_guests'] = True

        if call_id:
            add_call_id_aliases = [str(call_id)]
            domain = self.get_settings().get_main_domain()
            if domain:
                add_call_id_aliases.append('{}@{}'.format(call_id, domain))

            for alias in add_call_id_aliases:
                if any(a['alias'] == alias for a in aliases):
                    continue
                aliases.append({'alias': alias})

        data['aliases'] = aliases

        result = self.post('configuration/v1/conference/', data)

        if result.status_code != 201:
            raise self.error('Could not create conference (status {})'.format(result.status_code), result)

        cospace_id = result.headers.get('Location', '').strip('/').split('/')[-1]

        if sync:  # use sync unless running api.get_cospace() later
            self.sync_single_conference(cospace_id)

        from customer.models import Customer
        PexipSpace.objects.update_or_create(cluster=self.cluster, external_id=cospace_id, defaults={
            'name': data['name'],
            'call_id': call_id,
            'guid': uuid.uuid4(),
            'customer': Customer.objects.find_customer(pexip_tenant_id=tenant),
            'organization_unit': organization_unit or None,
        })
        return cospace_id

    def sync_single_conference(self, conference_id: Union[str, int] = None, data: dict = None):
        from datastore.utils.pexip import sync_single_conference_full
        return sync_single_conference_full(self, conference_id=conference_id, data=data)

    def delete_alias(self, alias_id):
        response = self.delete('configuration/v1/conference_alias/{}/'.format(alias_id))

        if response.status_code != 204:
            raise self.error('Error deleting alias ({})'.format(response.status_code), response)

        return True

    def update_alias(self, alias_id, data):
        response = self.patch('configuration/v1/conference_alias/{}/'.format(alias_id), data)

        if response.status_code != 202:
            raise self.error('Error updating alias ({})'.format(response.status_code), response)

        return True

    def add_alias(self, data, try_increase_data=False):

        if try_increase_data:
            alias, inc_data = self.find_free_number_request('configuration/v1/conference_alias/', data, ['alias'])

        response = self.post('configuration/v1/conference_alias/', data)

        if response.status_code != 201:
            raise self.error('Invalid status for new alias ({})'.format(response.status_code), response)

        return response.headers.get('Location').strip('/').split('/')[-1]

    def set_layout(self, meeting, new_layout):

        data = {
            'conference_id': meeting.provider_ref2,
        }
        return self.patch('command/v1/conference/transform_layout/', data)

    def get_conference_alias(self, conference):
        if isinstance(conference, (int, str)):
            conference = self.get_cospace(conference)
        return sorted(conference['aliases'], key=lambda x: -len(x['alias']))[0]['alias']

    def dialout(self, meeting, dialout):

        call_leg_id = self.add_call_leg(self.get_conference_alias(meeting.provider_ref2), dialout.uri)

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
            response = self.delete('callLegs/%s/' % dialout.provider_ref)
        except NotFound as e:
            response = e.response
        dialout.deactivate()
        return response

    def get_info(self, meeting):

        if not meeting.backend_active:
            return

        return self.get_cospace(meeting.provider_ref2)

    def get_cospace(self, conference_id):

        if self.use_cache_for_single_objects:
            cospaces, count = self.find_cospaces_cached(cospace_id=conference_id)
            if cospaces:
                return cospaces[0]

        response = self.get('configuration/v1/conference/%s/' % conference_id)

        if response.status_code != 200:
            if response.status_code == 404:
                ds.Conference.objects.filter(provider=self.cluster, cid=conference_id, is_active=True).update(is_active=False)
            raise self.error('status not ok: %s' % response.text, response)

        conference = response.json()

        if not self.is_syncing:
            synced = self.sync_single_conference(conference_id=conference_id, data=conference)
            if self.allow_cached_values:
                return synced.to_dict()

        return {
            **conference,
            'tenant': self.get_tenant(conference['name'], conference, conference_id=conference['id']),
        }

    def get_calls_cached(self, include_legs=False, include_participants=False, filter=None, cospace=None, call_id=None, limit=None, tenant=None, offset=0):
        from statistics.models import Call
        calls = Call.objects.distinct().filter(server__cluster=self.cluster,
                                               ts_start__gt=now() - timedelta(days=30),  # use index
                                               ts_stop__isnull=True)\
            .filter(legs__ts_stop__isnull=True, legs__should_count_stats=True)

        if tenant is not None:
            calls = calls.filter(tenant=tenant)

        if filter:
            calls = calls.filter(cospace__icontains=filter)

        if cospace is not None:
            calls = calls.filter(cospace=cospace)

        if call_id is not None:
            calls = calls.filter(guid=call_id)

        cols = ['id', 'name', 'cospace', 'call_id', 'start_time', 'tenant']
        result = [dict(zip(cols, v)) for v in calls.values_list('guid', 'cospace', 'cospace', 'id', 'ts_start', 'tenant')[offset:offset + limit if limit else None]]
        for c in result:
            call_id = c.pop('call_id')
            c['ts_start'] = c['start_time']
            c['pexip'] = True  # TODO other way to distinguish?
            if not c.get('id'):
                c['id'] = '{}{}'.format(LOOKUP_CALL_CONFERENCE_PREFIX, call_id)
            else:
                cdr_state = Call.get_cdr_state_info(self.cluster.pk, c['id'])
                c.update({**cdr_state, **c})

            self.populate_call_participants(c, include_legs=include_legs, include_participants=include_participants)

        return result, calls.count()

    def get_calls(self, include_legs=False, include_participants=False, filter=None, cospace=None, limit=None, tenant=None, offset=0):

        if self.use_call_cache:
            return self.get_calls_cached(include_legs=include_legs, include_participants=include_participants,
                                         filter=filter, cospace=cospace, limit=limit, tenant=tenant, offset=offset)

    #     "filtering": { "name": 1, "service_type": 1, "start_time": 1, "tag": 1 },

        params = {
            k: v
            for k, v in list(
                {
                    'limit': limit,
                    'name__istartswith': filter if filter and cospace is None else None,
                    'name': cospace or '-----' if cospace is not None else None,
                    'offset': offset,
                }.items()
            )
            if v is not None
        }

        calls, count = self._iter_pages_with_count('status/v1/conference/', params, limit=limit, match_tenant=False)

        result = []

        local_call_tenants = self._get_local_call_tenant_map([c['name'] for c in calls])

        for call in calls:

            cur = self.transform_status_call(call,
                                      include_legs=include_legs,
                                      include_participants=include_participants,
                                      local_call_tenants=local_call_tenants
                                      )

            if tenant is not None and cur.get('tenant') != tenant:
                count -= 1
                continue

            result.append(cur)

        return result, count

    def _get_local_call_tenant_map(self, cospaces):
        """already matched in statistics parsing"""
        from statistics.models import Call
        local_calls = Call.objects.filter(server__cluster=self.cluster, cospace__in=cospaces,
                                          ts_start__gte=now() - timedelta(days=1), ts_stop__isnull=True) \
                                  .exclude(tenant='').values_list('cospace', 'tenant')

        return dict(local_calls)

    def get_call_tenant_from_participants(self, call, participants=None):
        if participants is None:
            participants = self.get_participants(call['id'], cospace=call.get('name'))[0]

        for p in participants:
            from customer.models import CustomerMatch
            match = CustomerMatch.objects.get_match_from_text(p['local_alias'], cluster=self.cluster)
            if match:
                cur_tenant = match.customer.get_pexip_tenant_id() if match.customer_id else match.tenant_id
                if cur_tenant is not None:
                    return cur_tenant
        return None

    def transform_status_call(self, call, include_legs=False, include_participants=False, local_call_tenants=None):

        if local_call_tenants is None:
            local_call_tenants = self._get_local_call_tenant_map([call['name']])

        cur_tenant = self.get_tenant(call.get('name'))

        if cur_tenant is None:
            cur_tenant = local_call_tenants.get(call['name'])

        participants = None

        if cur_tenant is None:
            # not enough data. Fetch from participant local_alias
            participants = self.get_participants(call['id'], cospace=call.get('name'))[0]
            cur_tenant = self.get_call_tenant_from_participants(call, participants=participants)

        start = self.parse_timestamp(call['start_time'])

        result = {
            **call,
            'id': call.get('id'),
            'name': call.get('name', ''),
            'start_time': call.get('start_time'),
            'ts_start': start,
            'duration': int((now() - start).total_seconds()),
            'pexip': True,  # TODO other way to distinguish?
            'tenant': cur_tenant or '',
        }
        self.populate_call_participants(result, include_legs=include_legs,
                                        include_participants=include_participants,
                                        participants=participants)
        return result

    def populate_call_participants(self, call, include_legs=False, include_participants=False, participants=None):

        if include_legs or include_participants:
            if participants is None:
                participants, count = self.get_participants(call['id'], cospace=call.get('name'))
            if include_legs:
                call['legs'] = participants
            else:
                call['participants'] = participants

        return call

    def add_call(self, cospace, name=None):

        return ds.Conference.objects.match(cospace).to_dict()['name']  # TODO ?

    def lookup_cached_call(self, call_id):
        self.validate_call_id(call_id)

        lookup = self.get_lookup_cospace(call_id)
        if lookup:
            try:
                return self.get_calls_cached(cospace=lookup)[0][0]
            except IndexError:
                raise NotFound('Call not found')

    def lookup_call_id(self, call_id):
        self.validate_call_id(call_id)

        call = self.lookup_cached_call(call_id)
        if not call:
            return call_id  # treat as real id

        if call['id'] and not self.is_lookup_call_id(call['id']):
            return call['id']

        with self.disable_cache():
            live_call = self.get_call(call_id)

            from statistics.models import Call

            Call.objects.filter(
                server__cluster=self.cluster, guid=call_id[len(LOOKUP_CALL_CONFERENCE_PREFIX) :]
            ).update(guid=live_call['id'])
            return live_call['id']

    @classmethod
    def validate_call_id(cls, call_id) -> bool:
        if cls.is_lookup_call_id(call_id):
            return True
        if re.match(r'^[0-9a-f-]+$', str(call_id)):
            return True
        raise NotFound('Call ID not valid')

    def get_call(self, call_id, cospace=None, include_legs=False, include_participants=False):

        self.validate_call_id(call_id)

        def _populate_cached(result):
            return self.populate_call_participants(result, include_legs=include_legs, include_participants=include_participants)

        call = self.lookup_cached_call(call_id)
        if call:
            if self.use_call_cache:
                return _populate_cached(call)
            call_id, cospace = call['id'], call['cospace']
        elif (call_id or cospace) and self.use_call_cache:
            try:
                call = self.get_calls_cached(call_id=call_id, cospace=cospace)[0][0]
                return _populate_cached(call)
            except IndexError:
                pass

        if not call_id and not cospace:
            raise NotFound('No ids specified')
        elif call_id and not self.is_lookup_call_id(call_id):
            response = self.get('status/v1/conference/{}/'.format(call_id))
            if response.status_code != 200:
                raise self.error('Invalid status', response)
            call = response.json()
        elif cospace:
            try:
                with self.disable_cache():
                    calls, count = self.get_calls(cospace=cospace, include_legs=include_legs, include_participants=include_participants)
                    return calls[0]
            except IndexError:
                raise NotFound('Call not found')

        return self.transform_status_call(call, include_legs=include_legs, include_participants=include_participants)

    def get_call_legs(self, call_id=None, cospace=None, filter=None, tenant=None, limit=None):
        return self.get_participants(call_id=call_id, cospace=cospace, filter=filter, tenant=tenant, limit=limit)

    def get_call_leg(self, call_leg_id):

        self.validate_call_id(call_leg_id)

        if self.use_call_cache:
            participants, count = self.get_participants_cached(guid=call_leg_id)
            if participants:
                return participants[0]

        response = self.get('status/v1/participant/{}/'.format(call_leg_id))
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        leg = response.json()

        return self.convert_status_participant(leg)

    def start_stream(self, call_id, remote, remote_presentation=None, **data):
        extra = data.pop('presentation_url', None)
        if extra and not remote_presentation:
            remote_presentation = extra
        if remote_presentation:
            data['presentation_url'] = remote_presentation

        data['streaming'] = True
        if remote.startswith('rtmp:') or remote.startswith('rtmps:'):
            data['protocol'] = 'RTMP'  # needed for presentation_url

        data.setdefault('keep_conference_alive', 'keep_conference_alive_if_multiple')

        return self.add_call_leg(call_id, remote, **data)

    def add_call_leg(self, call_id, remote, **data):

        if self.is_lookup_call_id(call_id):
            alias = ds.Conference.objects.match(self.get_lookup_cospace(call_id)).to_dict()[
                'full_uri'
            ]
        elif '@' in call_id:
            try:  # TODO check permission
                alias = ds.Conference.objects.match({'local_alias': call_id}).to_dict()['full_uri']
            except AttributeError:
                raise NotFound('Conference matching alias not found')
        else:
            try:
                call = self.get_call(call_id, include_participants=True)
            except NotFound:
                raise  # TODO
            else:
                try:
                    alias = ds.Conference.objects.match(call).to_dict()['full_uri']
                except AttributeError:
                    if not call.get('participants') or not call['participants'][0]['local_alias']:
                        raise NotFound('Could not find local alias')
                    alias = call['participants'][0]['local_alias']

        data.setdefault('role', 'chair')
        data.setdefault('routing', 'routing_rule')

        if not data.get('system_location'):
            dial_out_location = (
                self.get_settings().get_dial_out_location()
            )  # TODO use customer or default?
            if dial_out_location:
                data['system_location'] = dial_out_location

        data = {
            'conference_alias': alias,
            'destination': remote,
            **data,
        }

        response = self.post('command/v1/participant/dial/', data)

        if response.status_code != 202:
            raise self.error('status not ok: %s' % response.text, response)

        participant_id = response.json().get('data', {}).get('participant_id')
        if response.json().get('status') != 'success' or participant_id is None:
            msg = response.json().get('message')
            if not msg:
                msg = 'missing participant id in response. Keys {}, data {}'.format(
                    response.json().keys(), response.json().get('data', {}).keys()
                )
            raise self.error('Could not dial participant: {}'.format(msg), response)

        return participant_id

    def update_call_leg(self, leg_id, data):

        response = self.patch('callLegs/{}/'.format(leg_id), data)
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        return response

    def hangup_call_leg(self, leg_id):
        return self.hangup_participant(leg_id)

    def update_call(self, call_id, data):

        response = self.patch('calls/{}/'.format(call_id), data)
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        return response

    @classmethod
    def is_lookup_call_id(cls, call_id):
        return str(call_id).startswith(LOOKUP_CALL_CONFERENCE_PREFIX)

    @classmethod
    def get_lookup_cospace(cls, call_id):
        if not call_id or not cls.is_lookup_call_id(call_id):
            return None

        from statistics.models import Call
        try:
            return Call.objects.filter(id=call_id.split('.')[1]).values_list('cospace', flat=True)[0]
        except (ValueError, IndexError):
            raise NotFound()

    def get_participants_cached(self, call_id=None, guid=None, cospace=None, filter=None, tenant=None, only_internal=True, limit=None):
        from statistics.models import Leg
        legs = Leg.objects.filter(server__cluster=self.cluster,
                                  ts_start__gte=now() - timedelta(days=30),  # use db index
                                  ts_stop__isnull=True)

        if only_internal:
            legs = legs.filter(should_count_stats=True)

        if guid is not None:
            if not guid:
                raise ValueError('Cant filter on empty id')
            legs = legs.filter(
                Q(guid=guid) | Q(guid2=guid)
            )  # TODO swap guid/guid2 in pexip stats/policy

        if tenant is not None:
            legs = legs.filter(tenant=tenant)

        lookup_cospace = self.get_lookup_cospace(call_id)
        if lookup_cospace:
            legs = legs.filter(call__cospace=lookup_cospace)
        elif call_id:
            legs = legs.filter(call__guid=call_id)
        elif cospace:
            legs = legs.filter(call__cospace=cospace)

        cols = [
            'id',
            'id2',  # replaces id if set. temporary workaround for participant id
            'display_name',
            'call',
            'local_alias',
            'remote_alias',
            'tenant',
            'connect_time',
            'conference',
        ]
        result = [
            dict(zip(cols, v))
            for v in legs.values_list(
                'guid',
                'guid2',
                'name',
                'call__guid',
                'local',
                'remote',
                'tenant',
                'ts_start',
                'call__cospace',
            )[:limit]
        ]

        for leg in result:
            id2 = leg.pop('id2')
            if id2:
                leg['id'] = id2
            leg['ts_start'] = leg['connect_time']

            cdr_state = Leg.get_cdr_state_info(self.cluster.pk, leg['id'])
            leg.update({**cdr_state, **leg})

        return result, legs.count()

    def get_participants(self, call_id=None, cospace=None, filter=None, tenant=None, only_internal=True, limit=None):

        if self.use_call_cache:
            return self.get_participants_cached(call_id=call_id, cospace=cospace, filter=filter, tenant=tenant, only_internal=only_internal, limit=limit)

        filter_kwargs = {}

        if self.is_lookup_call_id(call_id):
            cospace = self.get_lookup_cospace(call_id)
            call_id = None
            if not cospace:
                raise NotFound('Cached ID not found')

        if cospace:
            filter_kwargs['conference'] = cospace
        elif call_id:
            call = self.get_call(call_id, cospace=cospace)
            filter_kwargs['conference'] = call['name']

        if only_internal and not (call_id or cospace):
            # exclude mssip/teams using one api call
            filter_kwargs['protocol__regex'] = r'^(?!MSSIP|TEAMS)'
            participants, count = self._iter_pages_with_count('status/v1/participant/', filter_kwargs, limit=limit, match_tenant=False)

            # include incoming participants only
            filter_kwargs['protocol__regex'] = r'(MSSIP|TEAMS)'
            filter_kwargs['call_direction'] = 'in'

            skype_limit = 1 if not limit or count >= limit else limit - count
            participants2, count2 = self._iter_pages_with_count('status/v1/participant/', filter_kwargs, limit=skype_limit, match_tenant=False)

            count += count2

            if not limit or count < limit:  # add teams/skype ingoing.
                ids = {p['id'] for p in participants}
                conflicts = {p['id'] for p in participants2} & ids
                unique_participants = [p for p in participants2 if p['id'] not in ids]

                if conflicts:
                    count -= len(conflicts)

                    if not settings.TEST_MODE:  # not enough mock for filter
                        # raise ValueError('Duplicate IDS', list(conflicts))  # TODO dropped regex-filter or a real error?
                        with sentry_sdk.push_scope() as scope:
                            scope.set_extra('cluster_id', self.cluster.pk)
                            scope.set_extra('conflicts', conflicts)
                            capture_message('Duplicate IDS')

                participants.extend(unique_participants)
        else:
            participants, count = self._iter_pages_with_count('status/v1/participant/', filter_kwargs, limit=limit, match_tenant=False)

        result = [self.convert_status_participant(p) for p in participants]
        result_count = len(result)

        if only_internal:
            result = [r for r in result if not r.get('external')]
        if tenant is not None:
            result = [r for r in result if r.get('tenant') == tenant]

        count -= result_count - len(result)

        return result, count

    def convert_status_participant(self, participant):
        if participant['call_direction'] == 'in':
            local, remote = participant['destination_alias'], participant['source_alias']
        else:
            remote, local = participant['source_alias'], participant['destination_alias']

        if participant.get('protocol') == 'WebRTC' and '@' not in remote:
            remote = 'webrtc'

        if participant.get('connect_time'):
            participant['ts_start'] = self.parse_timestamp(participant['connect_time'])

        participant.update({
            'local_alias': clean_target(local),
            'remote_alias': clean_target(remote),
        })
        participant['tenant'] = self.get_tenant(participant['conference'], participant, default='')

        if participant['protocol'] in {'MSSIP', 'TEAMS', 'GMS'} and participant['call_direction'] == 'out':
            participant['external'] = True

        return participant

    def get_tenant(self, conference_name=None, obj=None, conference_id=None, default=None):
        if obj and obj.get('tenant'):
            return obj['tenant']

        if conference_id:
            overridden_space = PexipSpace.objects.filter(cluster=self.cluster,
                                                         external_id=conference_id) \
                .select_related('customer').first()

            if overridden_space and overridden_space.customer_id:
                return overridden_space.customer.get_pexip_tenant_id()

        from customer.models import CustomerMatch
        match = CustomerMatch.objects.get_match_for_pexip(conference_name, obj, cluster=self.cluster)

        if not match and obj:
            match = CustomerMatch.objects.get_match(obj=obj, cluster=self.cluster)

        if match and match.customer_id:
            return match.customer.get_pexip_tenant_id()
        elif match and match.tenant_id is not None:
            return match.tenant_id

        return default

    def add_participant(self, call_id, remote, layout=None, call_leg_profile=None):

        return self.add_call_leg(call_id, remote)

    def update_call_participants(self, call_id, data):
        response = self.patch('calls/{}/participants/*'.format(call_id), data)
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)
        return response

    def hangup_participant(self, participant_id):

        response = self.post('command/v1/participant/disconnect/', {'participant_id': participant_id})
        return response.status_code == 200

    def hangup_call(self, call_id):

        call_id = self.lookup_call_id(call_id)
        response = self.post('command/v1/conference/disconnect/', {'conference_id': call_id})
        return response.status_code == 200

    def set_participant_moderator(self, leg_id, value=True):
        role = 'chair' if value else 'guest'
        response = self.post('command/v1/participant/role/', {'participant_id': leg_id, 'role': role})
        return response.status_code == 202

    def set_all_participant_mute(self, call_id, value=True, participants=None):
        """Mutes all guests"""
        call_id = self.lookup_call_id(call_id)

        value = bool(value)
        err = None

        if participants is None:
            participants, _count = self.get_participants(call_id)
            for p in participants:
                if p.get('is_muted') != value:
                    try:
                        self.set_participant_mute(p['id'], value)
                    except NotFound:
                        pass
                    except Exception as e:
                        err = e

        if err:
            raise err
        return True

    def set_participant_mute(self, leg_id, value=True):
        action = 'mute' if value else 'unmute'
        response = self.post('command/v1/participant/{}/'.format(action), {'participant_id': leg_id})
        return response.status_code == 202

    def set_call_lock(self, call_id, value=True):
        call_id = self.lookup_call_id(call_id)

        action = 'lock' if value else 'unlock'
        response = self.post('command/v1/conference/{}/'.format(action), {'conference_id': call_id})
        return response.status_code == 202

    def webinar(self, meeting):
        from meeting.models import MeetingWebinar

        return MeetingWebinar.objects.update_or_create(
            meeting=meeting,
            provider_ref=meeting.provider_ref,
            defaults={
                'password': meeting.moderator_password
                or meeting.get_webinar_info().get('moderator_pin'),
            },
        )[0]

    def unbook(self, meeting):
        if not meeting.backend_active:
            return

        if meeting.existing_ref:  # don't delete
            meeting.deactivate()
            return

        if meeting.provider_ref == '':
            if not settings.TEST_MODE:
                raise ValueError('Empty ID for meeting')
            return

        try:
            result = self.delete('configuration/v1/conference/{}/'.format(meeting.provider_ref2))
        except NotFound:
            result = None

        meeting.ts_deprovisioned = now()
        meeting.deactivate()
        ds.Conference.objects.filter(provider=self.cluster, cid=meeting.provider_ref2 or None).update(is_active=False)
        return result

    def delete_cospace(self, cospace_provider_ref):

        from meeting.models import Meeting

        meetings = Meeting.objects.filter(
            provider=self.cluster, provider_ref2=cospace_provider_ref, backend_active=True
        )

        if meetings:
            return self.unbook(meetings[0])

        result = self.delete('configuration/v1/conference/{}/'.format(cospace_provider_ref))

        if result.status_code in (204, 404):
            ds.Conference.objects.filter(provider=self.cluster, cid=cospace_provider_ref).update(is_active=False)
            return True
        return False

    def unbook_cached_values(self):
        pass

    def find_cospaces_cached(self, q=None, cospace_id=None, offset=0, limit=10, tenant=None, org_unit=None):
        from datastore.models.pexip import Conference

        result = Conference.objects.search_active(self.cluster, q, tenant=tenant, org_unit=org_unit)

        if cospace_id is not None:
            result = result.filter(cid=cospace_id)

        return [u.to_dict() for u in result[offset:offset + limit if limit else None]], result.count()

    def find_cospaces(self, q, offset=0, limit=10, tenant=None, org_unit=None, timeout=None):
        # cospaces are really named conferences in pexip. as are live calls (?)

        if self.use_cached_values or org_unit:
            return self.find_cospaces_cached(q, offset=offset, limit=limit, tenant=tenant, org_unit=org_unit)

        if isinstance(q, str):
            filters = {'name__icontains': q}
        else:  # TODO filter valid filter keys
            filters = q if q else {}

        cospaces, count = self._iter_pages_with_count('configuration/v1/conference/',
                                                      {**filters, 'offset': offset or 0, 'tenant': tenant},
                                                      limit=limit if limit else None,
                                                      timeout=timeout,
                                                      )
        result = []
        for cospace in cospaces:
            try:
                call_id = [x['alias'] for x in cospace['aliases'] if x['alias'].isdigit()][0]
            except IndexError:
                call_id = ''

            result.append({
                **cospace,
                'call_id': call_id,
            })

        if not self.is_syncing:
            for conference in result:
                self.sync_single_conference(data=conference)

        return result, count

    def find_users_cached(self, q=None, user_id=None, offset=0, limit=10, tenant=None, org_unit=None, include_user_data=False):
        from datastore.models.pexip import EndUser

        result = EndUser.objects.search_active(self.cluster, q=q, tenant=tenant, org_unit=org_unit)

        if user_id is not None:
            result = result.filter(uid=user_id)

        return [u.to_dict() for u in result[offset:offset + limit if limit else None]], result.count()

    def find_users(self, q, offset=0, limit=10, tenant=None, org_unit=None, include_user_data=False):

        if self.use_cached_values or org_unit:
            return self.find_users_cached(q, offset=offset, limit=limit, tenant=tenant, org_unit=org_unit, include_user_data=include_user_data)

        users, count = self._iter_pages_with_count('configuration/v1/end_user/',
            {'display_name__icontains': q, 'offset': offset or 0},
            limit=limit if limit else None)

        if not self.is_syncing:
            from datastore.utils.pexip import sync_single_user_full

            for u in users:
                sync_single_user_full(self, u['id'], data=u)

        return users, count

    def find_user(self, user_email, tenant=None):

        if not user_email:
            raise NotFound('User {} not found'.format(user_email))

        if self.use_cached_values:
            users, count = self.find_users_cached(user_email, tenant=tenant, include_user_data=True)
        else:
            users, count = self._iter_pages_with_count('configuration/v1/end_user/',
                                                       {'primary_email_address': user_email,
                                                        'tenant': tenant})

        for user in users:
            if user['primary_email_address'] == user_email:
                if self.allow_cached_values:
                    from datastore.utils.pexip import sync_single_user_full
                    return sync_single_user_full(self, data=user).to_dict()
                return user

        raise NotFound('User {} not found'.format(user_email))

    def get_tenants(self):

        return datastore.models.customer.Tenant.objects.filter(provider=self.cluster).values(
            'id', 'name'
        )

    def get_gateway_rules(self):

        response = self.get('configuration/v1/gateway_routing_rule/?limit=9999')
        if response.status_code != 200:
            raise self.error('Could not get gateway rules, status {}'.format(response.status_code), response)
        return response.json()['objects']

    def create_gateway_rule(self, data):

        response = self.post('configuration/v1/gateway_routing_rule/', data)
        if response.status_code != 201 or not response.headers.get('Location'):
            raise self.error('Could not create gateway rules, status {}'.format(response.status_code), response)

        return int(response.headers['Location'].strip('/').split('/')[-1])

    def update_gateway_rule(self, rule_id, data):

        response = self.patch('configuration/v1/gateway_routing_rule/{}/'.format(rule_id), json=data)
        if response.status_code != 202:
            raise self.error('Could not update gateway rules, status {}'.format(response.status_code), response)
        return True

    def delete_gateway_rule(self, rule_id):

        response = self.delete('configuration/v1/gateway_routing_rule/{}/'.format(rule_id))
        if response.status_code != 204:
            raise self.error('Could not delete gateway rules, status {}'.format(response.status_code), response)
        return True

    def get_systemprofiles(self):

        return {}

    def save_tenant(self, name, callbranding=None, ivrbranding=None, id=None, enable_recording=False, enable_streaming=False):

        tenant = datastore.models.customer.Tenant.objects.create(
            provider=self.cluster, tid=id or str(uuid.uuid4())
        )

        return tenant.id

    def save_ldapsource(self, filter, base_dn=None, tenant_id=None, id=None):

        raise NotImplementedError()

    def get_members(self, cospace_id, include_permissions=True, include_user_data=False, tenant=None):

        # TODO local user database?
        result = []

        users = ds.EndUser.objects.filter(provider=self.cluster, email__conference__cid=cospace_id)
        if tenant == '':
            users = users.filter(tenant__isnull=True)
        elif tenant is not None:
            users = users.filter(tenant__tid=tenant)

        for user in users:

            cur = user.to_dict_compact()
            cur.update({
                'user_id': cur['id'],
                'auto_generated': False,
                'permissions': [],
            })
            result.append(cur)

        return result

    def get_user_cospaces(self, user_id, include_cospace_data=False):
        if '@' in str(user_id):
            email = user_id
        else:
            email = self.get_user(user_id)['primary_email_address']

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

        if self.use_cached_values:
            conferences = ds.Conference.objects.search_active(
                self.cluster,
                email__email=email,
                tenant=self.tenant_id,
            ).exclude(
                is_scheduled=True,
            )
            return _remove_scheduled([c.to_dict_compact() for c in conferences])

        cospaces, count = self.find_cospaces(
            {'primary_owner_email_address': email}, tenant=self.tenant_id
        )
        return _remove_scheduled(cospaces)

    def get_user_private_cospace(self, user_id):
        try:
            cospaces = self.get_user_cospaces(user_id, include_cospace_data=True)
            for cospace in cospaces:
                if 'ldap' not in (cospace.get('sync_tag') or ''):
                    continue
                if cospace.get('primary_owner_email_address') != user_id:
                    continue
                return cospace
        except IndexError:
            return None

    def get_conference_aliases(self, conference_id=None, **filters):

        if conference_id:
            filters['conference'] = conference_id
        return self._iter_all_pages('configuration/v1/conference_alias/', {'limit': 2500, **filters})

    def get_cospace_accessmethods(self, cospace_id):
        return self.get_conference_aliases(conference_id=cospace_id)

    def get_automatic_participants(self, conference_id=None, **filters):

        if conference_id:
            filters['conference'] = conference_id

        return self._iter_all_pages('configuration/v1/automatic_participant/', {'limit': 2500, **filters})

    def get_themes(self, **filters):
        return self._iter_all_pages('configuration/v1/ivr_theme/', params=filters)

    def add_member(
        self,
        cospace_id,
        user_jid,
        can_add_remove_members=False,
        can_remove_self=False,
        can_destroy=False,
        can_delete_messages=False,
        call_leg_profile=None,
        is_moderator=False,
    ):

        raise NotImplementedError()
        relation, created = ds.CoSpaceMember.objects.get_or_create(
            provider=self.cluster, user=ds.User.objects.get_user(self, user_jid)
        )

        return relation

    def remove_member(self, cospace_id, member_id):
        raise NotImplementedError()

    def update_member(self, cospace_id, member_id, **kwargs):
        raise NotImplementedError()

    def get_user(self, user_id):

        if self.use_cache_for_single_objects:
            users, count = self.find_users_cached(user_id=user_id)
            if users:
                return users[0]

        response = self.get('configuration/v1/end_user/%s/' % user_id)

        if response.status_code != 200:
            if response.status_code == 404:
                ds.EndUser.objects.filter(provider=self.cluster, uid=user_id, is_active=True).update(is_active=False)
            raise self.error('Invalid status ({})'.format(response.status_code), response)

        user = response.json()

        # TODO use user.uuid?
        result = {
            **user,
            'uid': user['id'],
            'jid': '',  # TODO?
            'name': user['display_name'] or ' '.join([user['first_name'], user['last_name']]).strip(),
            'email': user['primary_email_address'],
            'tenant': ds.EndUser.objects.filter(provider=self.cluster, uid=user['id'])
            .values_list('tenant__tid', flat=True)
            .first(),
        }

        if not self.is_syncing:
            from datastore.utils.pexip import sync_single_user_full
            synced = sync_single_user_full(self, data=result)
            if self.allow_cached_values:
                return synced.to_dict()

        return result

    def clear_chat(self, cospace_id, date_from=None, date_to=None):
        pass

    def get_status(self, timeout=None):

        licenses = self.get_licenses()

        result = {
            'licenses': {
                'audio': licenses.get('audio'),
                'ports': licenses.get('port'),
                'systems': licenses.get('system'),
            },
            'worker_nodes': [],  # TODO change to license usage for latency self.get_worker_nodes(timeout=timeout),
            'errors': None,
        }
        return result

    def get_version(self):
        ignore_not_upgraded_nodes = 2  # allow x not upgrades nodes with
        response = self.get('status/v1/worker_vm/', params={
            'order_by': 'version',
            'limit': ignore_not_upgraded_nodes + 1,
        }, timeout=10)

        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        objects = response.json()['objects']
        return objects[-1]['version'] if objects else ''

    def get_worker_nodes(self, timeout=None):

        response = self.get('status/v1/worker_vm/', timeout=timeout, params=dict(limit=3000))
        if response.status_code != 200:
            raise self.error('status not ok: %s' % response.text, response)

        result = []
        for vm in response.json()['objects']:
            cur = {
                k: vm[k]
                for k in {'name', 'system_location', 'media_load', 'media_tokens_used', 'max_media_tokens', 'boot_time', 'node_type'}
                if k in vm
            }
            if cur.get('boot_time'):
                uptime = now().replace(microsecond=0) - self.parse_timestamp(cur['boot_time'])
                cur['uptime'] = uptime
                cur['uptime_text'] = str(uptime)
            result.append(cur)

        return result

    def get_licenses(self):
        "return {license: [current, total]}"

        response = self.get('status/v1/licensing/', timeout=3)

        if not response.status_code == 200:
            raise self.error('status not ok: %s' % response.text, response)

        try:
            data = response.json()['objects'][0]
        except Exception:
            raise self.error('Invalid license data structure', response)

        result = defaultdict(lambda: {'current': 0, 'total': 0})
        for k, v in data.items():
            if '_' not in k:
                continue

            license, item = k.split('_', 1)
            if item == 'total':
                result[license]['total'] = v
            elif item == 'count':
                result[license]['current'] = v

        return {k: v for k, v in result.items() if v['total']}

    def get_alarms(self):
        response = self.get('status/v1/alarm/')

        if not response.status_code == 200:
            raise self.error('status not ok: %s' % response.text, response)

        result = []
        for alarm in response.json()['objects']:
            start = self.parse_timestamp(alarm['time_raised']).replace(microsecond=0)
            cur = {
                'name': alarm.get('name', '') or '',
                'details': alarm.get('details', '') or '',
                'instance': alarm.get('instance', '') or '',
                'node': alarm.get('node', '') or '',
                'start': start,
                'timesince': str(now().replace(microsecond=0) - start),
                'id': alarm.get('id'),
            }
            result.append(cur)

        result.sort(key=lambda x: x['start'], reverse=True)
        return result

    def _iter_all_pages(self, url, params=None, yield_root=False, match_tenant=True, timeout=None):

        params = (params or {}).copy()

        params.setdefault('limit', 300)
        count = params.get('offset') or 0
        tenant = params.pop('tenantFilter', None)

        timeout_end = time.monotonic() + timeout if timeout else None
        timeout_kwargs = {}

        while 1:
            params.update({'offset': count})

            if timeout:
                timeout_kwargs = {'timeout': max(0.1, timeout_end - time.monotonic())}
            response = self.get(url, params=params, **timeout_kwargs)

            if response.status_code != 200:
                raise self.error('Invalid status {}'.format(response.status_code), response)

            data = response.json()

            if yield_root:
                yield_root = False
                yield data['meta']

            total_count = data['meta']['total_count']

            for item in data['objects']:

                if match_tenant or tenant:
                    if url == 'configuration/v1/conference/':
                        cur_tenant = self.get_tenant(item['name'], obj=item, conference_id=item['id']) or ''
                    else:
                        cur_tenant = self.get_tenant(obj=item) or ''
                    item['tenant'] = cur_tenant
                else:
                    cur_tenant = None

                if tenant is None or cur_tenant == tenant:
                    yield item

                count += 1

            if count >= total_count or not data['objects'] or not data['meta']['next']:
                break

    def _iter_pages_with_count(self, url, params, limit=None, match_tenant=True, timeout=None):

        i = 0
        result = []
        count = None

        if limit and params.get('limit') is not None and params['limit'] != limit:
            raise ValueError('Missmatching limit in kwarg ')

        params = (params or {}).copy()
        if limit:
            params['limit'] = limit

        for item in self._iter_all_pages(url, params, yield_root=True, match_tenant=match_tenant, timeout=timeout):
            if count is None:
                count = int(item.get('total_count'))
                continue
            result.append(item)
            i += 1

            if limit is not None and i >= limit:
                break

        return result, count

    def _iter_all_cospaces(self, tenant_id=None, **filter):

        if tenant_id:
            filter['tenant'] = tenant_id

        for item in self._iter_all_pages('configuration/v1/conference/', {'limit': 2500, **filter}):
            yield item

    def _iter_all_users(self, **filter):

        for item in self._iter_all_pages('configuration/v1/end_user/', {'limit': 2500, **filter}):
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

            correct_url = get_key_callback(cospace_node.get('uri', cospace_node.get('callId', '')))

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
            data['conference_sync_template_id'] = ldap_id

        response = self.post('command/v1/conference/sync/', data)
        if response.status_code not in (200, 201, 204):
            raise self.error('Invalid status code on sync', response)

        from provider import tasks

        tasks.cache_single_cluster_data.apply_async(
            [self.cluster.pk], {'incremental': True}, countdown=30
        )

        return response

    def get_internal_domains(self, clear=False) -> List[str]:
        """
        Try to determinate domains from call rules regexps
        """
        result = []
        for rule in self.get_gateway_rules():
            if '@' not in rule['match_string']:
                continue

            cur = self._get_domains_from_regex(rule['match_string'])
            if cur:
                result.extend(cur)

        return result

    @staticmethod
    def _get_domains_from_regex(regex):

        result = []
        try:
            domain_part = regex.split('@', 1)[1]
            if r'(\.' in domain_part:  # @test(\.com|\.se)
                subs, tlds = domain_part.split(r'(\.')
                tlds = '(\.' + tlds
            elif r'\.' in domain_part:  # @test\.com
                subs, tlds = domain_part.rsplit(r'\.', 1)
            else:  # @test.com
                subs, tlds = domain_part.rsplit(r'.', 1)
        except (IndexError, ValueError):
            return

        for domain in re.sub(r'[\\(){}$]', '', subs).split('|'):
            for tld in re.sub(r'[\\(){}$]', '', tlds).split('|'):
                cur = '{}.{}'.format(domain, tld)
                if re.match(r'^[A-z0-9-]+\.[A-z0-9-]+$', cur):
                    result.append(cur)

        return result

    def parse_timestamp(self, ts):
        if not ts:
            return None
        if isinstance(ts, (float, int)):
            result = datetime.utcfromtimestamp(ts)
            return result.replace(tzinfo=utc).replace(microsecond=0)
        elif isinstance(ts, datetime):
            return ts
        return make_aware(parse_datetime(ts), timezone=utc).replace(microsecond=0)

    HISTORY_PAGE_SIZE = 1000

    def get_history_conference(self, incremental=True, offset=0, last_end=None):
        from debuglog.models import PexipHistoryLog

        if incremental and not last_end:
            last_end = self.cluster.get_option('stats_conference_last_end')

        if last_end:
            response = self.get(
                'history/v1/conference/?limit={}&offset={}&order_by=end_time&end_time__gt={}'.format(
                    self.HISTORY_PAGE_SIZE, offset or 0, last_end
                )
            )
        else:
            response = self.get(
                'history/v1/conference/?limit={}&order_by=end_time&end_time__gte=2019-01-01T00:00:00&offset={}'.format(
                    self.HISTORY_PAGE_SIZE, offset or 0
                )
            )

        if response.status_code != 200:
            raise self.error('Invalid status code when fetching conferences ({})'.format(response.status_code), response)

        result = []
        first_start, last_start = None, None
        history_log = None
        try:
            result = response.json()['objects']
        finally:
            try:
                times = sorted(l['start_time'] for l in result if l.get('start_time'))
                first_start, last_start = self.parse_timestamp(times[0]), self.parse_timestamp(times[-1])
            except IndexError:
                pass

            history_log = PexipHistoryLog.objects.store(content=response.content, type='conference',
                                          count=len(result), cluster_id=self.cluster.pk,
                                          first_start=first_start, last_start=last_start)
        return result, history_log

    def get_history_participants(self, incremental=True, offset=0, last_end=None):
        from debuglog.models import PexipHistoryLog

        if incremental and not last_end:
            last_end = self.cluster.get_option('stats_participant_last_end')

        if last_end:
            response = self.get(
                'history/v1/participant/?limit={}&offset={}&order_by=end_time&end_time__gt={}'.format(
                    self.HISTORY_PAGE_SIZE, offset or 0, last_end
                )
            )
        else:
            response = self.get(
                'history/v1/participant/?limit={}&order_by=end_time&end_time__gte=2019-01-01T00:00:00&offset={}'.format(
                    self.HISTORY_PAGE_SIZE, offset or 0
                )
            )

        if response.status_code != 200:
            raise self.error('Invalid status code when fetching participants ({})'.format(response.status_code), response)

        result = []
        first_start, last_start = None, None

        history_log = None
        try:
            result = response.json()['objects']
        finally:
            try:
                times = sorted(l['start_time'] for l in result if l.get('start_time'))
                first_start, last_start = self.parse_timestamp(times[0]), self.parse_timestamp(times[-1])
            except IndexError:
                pass

            history_log = PexipHistoryLog.objects.store(content=response.content, type='participant',
                                          count=len(result), cluster_id=self.cluster.pk,
                                          first_start=first_start, last_start=last_start)
        return result, history_log

    def create_event_sink(self):
        return self.post(
            'configuration/v1/event_sink/',
            {
                'name': 'Mividas Core {}'.format(settings.HOSTNAME),
                'url': self.cluster.get_statistics_server().get_cdr_url(),
                'version': 1,
            },
        )

    def create_external_policy_server(self):
        from policy.models import ClusterPolicy

        return self.post(
            'configuration/v1/policy_server/',
            {
                'name': 'Mividas Core {}'.format(settings.HOSTNAME),
                'url': ClusterPolicy.objects.get_or_create(cluster=self.cluster)[
                    0
                ].get_absolute_url(),
                'version': 1,
            },
        )

    def get_related_policy_objects(self, force=False):
        objects = ['system_location', 'sip_proxy', 'teams_proxy', 'gms_access_token', 'h323_gatekeeper',
                   'mssip_proxy', 'stun_server', 'turn_server', 'ivr_theme']

        valid_fields = ['id', 'name', 'description', 'address', 'port', 'transport']

        cluster = self.cluster.pexip
        if not force and not cluster.should_refresh_system_objects():
            return cluster.system_objects_data

        result = {}
        for k in objects:
            response = self.get('configuration/v1/{}/?limit=9999'.format(k))
            if response.status_code != 200:
                raise self.error('Invalid status when getting {}'.format(k), response)
            result[k] = [
                {k: v for k, v in obj.items() if k in valid_fields}
                for obj in response.json()['objects']
            ]

        cluster.update_system_objects(result)

        return result

    def update_stats(self, incremental=True):
        last_conference_end = last_participant_end = None  # TODO loop one after the other
        conference_offset = participant_offset = 0

        last_conference_end, conference_offset = self.update_stats_conferences(
            initial_last_end=last_conference_end,
            offset=conference_offset,
            incremental=incremental,
        )
        last_participant_end, participant_offset = self.update_stats_participants(
            initial_last_end=last_participant_end,
            offset=participant_offset,
            incremental=incremental,
        )

        return min(last_conference_end or '', last_participant_end or '')

    def _try_and_log_stats_data(
        self, fn, incremental=True, offset=0, last_end: str = None
    ) -> Tuple[List[dict], Union[None, 'PexipHistoryLog']]:
        from debuglog.models import PexipHistoryLog

        try:
            result = fn(incremental=incremental, offset=offset, last_end=last_end)
            if result:
                return result
        except AuthenticationError as e:
            PexipHistoryLog.objects.store(
                content=b'{}', error=str(e), ip=self.ip, server_id=self.cluster.pk
            )
        except (ResponseConnectionError, ResponseTimeoutError):
            pass
        except Exception as e:
            PexipHistoryLog.objects.store(
                content=b'{}', error=str(e), ip=self.ip, server_id=self.cluster.pk
            )
            if settings.DEBUG or settings.TEST_MODE:
                raise
            capture_exception()
        return [], None

    @staticmethod
    def _get_stats_format_limit_ts():
        """Allow clock skew and out of order events"""
        return (now() - timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S')

    def update_stats_conferences(
        self, incremental=True, initial_last_end: str = None, offset=0, limit: int = None
    ):
        from statistics.parser.pexip import PexipParser

        parser = PexipParser(self.cluster.get_statistics_server())
        last_end = initial_last_end

        if not limit:
            # Max 10 000 stored conferences
            limit = 10000

        for i in range(ceil(limit / self.HISTORY_PAGE_SIZE)):
            calls, history_log = self._try_and_log_stats_data(
                self.get_history_conference, incremental, offset, last_end
            )
            if not calls:
                break
            c = 0
            for call in calls:
                parser.parse_call(call, history_log=history_log)
                c += 1
                if c % 20 == 0:
                    time.sleep(0)  # catch signals

            try:
                new_last_end = max(call['end_time'] for call in calls if call.get('end_time'))
                if new_last_end == last_end:
                    offset += self.HISTORY_PAGE_SIZE
                else:
                    offset = 0
                    last_end = new_last_end
            except ValueError:
                if calls:
                    capture_exception()
                break
            else:
                ts_end_skew_limit = self._get_stats_format_limit_ts()

                if last_end and last_end >= ts_end_skew_limit:
                    self.cluster.set_option('stats_conference_last_end', ts_end_skew_limit)
                else:
                    self.cluster.set_option('stats_conference_last_end', last_end)

            if len(calls) < self.HISTORY_PAGE_SIZE - 50:
                break

            if limit and (i + 1) * self.HISTORY_PAGE_SIZE > limit:
                break

        return last_end, offset

    def update_stats_participants(
        self, incremental=True, initial_last_end: str = None, offset=0, limit: int = None
    ):
        from statistics.parser.pexip import PexipParser

        parser = PexipParser(self.cluster.get_statistics_server())

        last_end = initial_last_end
        total_count = None

        if not limit:
            # All participants for max 10 000 conferences
            limit = 100000

        for i in range(ceil(limit / self.HISTORY_PAGE_SIZE)):
            participants, history_log = self._try_and_log_stats_data(
                self.get_history_participants, incremental, offset, last_end
            )
            if not participants:
                break

            if total_count is None:
                if history_log.content_json:
                    total_count = history_log.content_json.get('total_count')

            p = 0
            for participant in participants:
                parser.parse_participant(participant, history_log=history_log)
                p += 1
                if p % 20 == 0:
                    time.sleep(0)  # catch signals

            try:
                new_last_end = max(
                    participant['end_time']
                    for participant in participants
                    if participant.get('end_time')
                )
                if new_last_end == last_end:
                    offset += self.HISTORY_PAGE_SIZE
                else:
                    offset = 0
                    last_end = new_last_end
            except ValueError:
                if participants:
                    capture_exception()
                break
            else:
                ts_end_skew_limit = self._get_stats_format_limit_ts()

                if last_end and last_end >= ts_end_skew_limit:
                    self.cluster.set_option('stats_participant_last_end', ts_end_skew_limit)
                else:
                    self.cluster.set_option('stats_participant_last_end', last_end)

            if len(participants) < self.HISTORY_PAGE_SIZE - 50:
                break

            if total_count and (i + 1) * self.HISTORY_PAGE_SIZE > total_count:
                break

            if limit and (i + 1) * self.HISTORY_PAGE_SIZE > limit:
                break

        return last_end, offset

    def register_device_endpoint(self, dial_info, description=None, username=None, password=None):

        sip = dial_info.get('sip') or dial_info.get('sip_uri')
        h323, h323_e164 = dial_info.get('h323'), dial_info.get('h323_e164')

        missing = set()

        for alias in {uri for uri in (sip, h323, h323_e164) if uri}:
            response = self.get('configuration/v1/device/', params={'alias': alias})
            if not response.json().get('objects'):
                missing.add(alias)

        for alias in missing:
            data = {
                'alias': alias,
                'enable_sip': sip == alias,
                'enable_h323': h323 == alias or h323_e164 == alias,
            }
            if description:
                data['description'] = str(description)
            if username and password:
                data['username'] = username
                data['password'] = password

            response = self.post('configuration/v1/device/', data)
            if response.status_code != 201:
                raise self.error(response)

        return missing

    @staticmethod
    def update_all_pexip_stats(incremental=True):
        from provider.models.provider import Provider
        from customer.models import Customer

        done = set()
        exceptions = []

        try:
            customer = Customer.objects.all()[0]
        except IndexError:
            return

        for provider in Provider.objects.all():
            if not provider.is_pexip or provider.pk in done:
                continue

            if provider.is_cluster and not provider.get_clustered():
                continue

            if not provider.enabled:
                continue

            api = PexipAPI(provider, customer)
            if not api.cluster.auto_update_statistics:
                continue

            try:
                if api.update_stats(incremental=incremental):

                    done.add(provider.cluster_id)
                    for p in provider.get_clustered():
                        done.add(p.pk)
            except Exception as e:
                exceptions.append(e)

        if exceptions:
            raise exceptions[0]
