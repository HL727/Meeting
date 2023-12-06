import re
from datetime import timedelta, datetime
from random import randint
from typing import Union, TYPE_CHECKING

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now

from shared.utils import maybe_update, partial_update
from ..models import Call, Leg, InvalidCallStats, PossibleSpamLeg, tenant_obj, Server

try:
    import ujson as json  # noqa
except ImportError:
    import json
from urllib.parse import parse_qsl

from django.db.models import Max, Min, Sum, F

from defusedxml import cElementTree as ET

from collections import Counter
from django.conf import settings
from sentry_sdk import capture_exception
from .utils import get_owner, get_ou, is_phone, get_org_unit, get_ou_from_members, \
    rewrite_internal_domains, clean_target

from django.core.cache import cache

if TYPE_CHECKING:
    from debuglog.models import AcanoCDRLog

RERAISE_ERRORS = settings.DEBUG or getattr(settings, 'TEST_MODE', False)
LEG_LOWER_BOUND = 7


def _check_cache_enabled():
    key  = 'test_stat_start{}'.format(randint(1000000, 9999999))
    try:
        cache.set(key, 'test', )
        return cache.get(key) == 'test' and 'LocMemCache' not in cache.get.__self__.__class__.__name__
    except Exception:
        return False


CACHE_ACTIVE = _check_cache_enabled()


def _text(node):
    if node is not None:
        return node.text or ''
    return ''


class Parser:

    def __init__(self, server: Server, debug=False, cdr_log: 'AcanoCDRLog' = None):
        self.tenants = None
        self.server = server
        self.debug = debug
        self.cdr_log = cdr_log

    def parse_xml(self, xmlstring):

        if isinstance(xmlstring, str):
            xmlstring = xmlstring.encode('utf-8')

        records = ET.fromstring(xmlstring)

        for record in records:
            self.parse_record(record)

    def parse_record(self, record):

        from recording import cdr as recording

        assert record.tag == 'record'

        if record.get('type') in ('recordingStart', 'recordingEnd', 'streamingStart', 'streamingEnd'):
            return recording.parse_cdr(record)

        for cur in record:
            if cur.tag == 'callLeg':
                self.parse_call_leg(cur, record)
            elif cur.tag == 'call':
                self.parse_call(cur, record)
            else:
                continue

    def _timestamp(self, s: Union[str, datetime, None]) -> Union[datetime, None]:
        if isinstance(s, datetime):
            return s
        if s:
            return parse_datetime(s)
        return None

    def get_call(self, guid, update_data=None):

        tenant_fallback = update_data.pop('tenant_fallback', None)

        with transaction.atomic():
            try:
                obj = Call.objects.select_for_update(of=('self',)).get(server=self.server, guid=guid)
                created = False
            except Call.DoesNotExist:
                create_data = update_data.copy()
                if tenant_fallback and not update_data.get('tenant'):
                    create_data['tenant'] = tenant_fallback
                obj, created = Call.objects.select_for_update(of=('self',)).get_or_create(server=self.server, guid=guid, defaults=create_data or {})

            if not created and update_data:
                maybe_update(obj, update_data)

            if self.debug:
                print('call', guid, update_data.get('cospace', '') if update_data else '')

        if self.cdr_log:
            obj.acano_cdr_event_logs.add(self.cdr_log)

        return obj

    def get_call_leg(self, guid, call, update_data=None, fallback_data=None):

        if call:
            call = self.get_call(call, update_data={'tenant_fallback': update_data.get('tenant')})
            if call.tenant:
                update_data['tenant'] = call.tenant
        else:
            call = None

        update_data = update_data or {}
        if call:
            update_data['call'] = call

        with transaction.atomic():
            if self.debug:
                print('leg', guid, update_data.get('target', '') if update_data else '')

            legs = Leg.objects.all()

            try:
                obj = legs.select_for_update(of=('self',)).get(server=self.server, guid=guid)
                created = False
            except Leg.DoesNotExist:
                self.server.acquire_lock('leg')  # until unique constraint on Leg.server|guid
                obj, created = legs.select_for_update(of=('self',)).get_or_create(
                    server=self.server,
                    guid=guid,
                    defaults={
                        **update_data,
                        **fallback_data,
                    },
                )

            if not created and update_data:
                maybe_update(obj, update_data)

        if self.cdr_log:
            obj.acano_cdr_event_logs.add(self.cdr_log)

        return obj

    def parse_call(self, call, record):

        cur_call = {}

        if record.get('type') == 'callStart':
            cur_call['ts_start'] = record.get('time')
            if call.find('./name') is not None:
                cur_call['cospace'] = call.find('./name').text
            if call.find('./tenant') is not None:
                cur_call['tenant'] = call.find('./tenant').text
            if call.find('./coSpace') is not None:
                cur_call['cospace_id'] = call.findtext('./coSpace') or ''
                cur_call['org_unit'] = get_org_unit(cur_call['cospace_id'])
            else:
                cur_call['cospace_id'] = 'AdHoc'
            if call.find('./cdrTag') is not None:
                cur_call['cdr_tag'] = call.find('./cdrTag').text
        elif record.get('type') == 'callEnd':
            cur_call['duration'] = float(call.find('durationSeconds').text)
            cur_call['leg_count'] = int(call.find('callLegsMaxActive').text)
            cur_call['ts_stop'] = self._timestamp(record.get('time'))

        correlator = call.findtext('./callCorrelator', '')
        if correlator:
            cur_call['correlator_guid'] = correlator

        if cur_call.get('tenant'):
            cur_call['tenant_fk'] = tenant_obj(cur_call['tenant'])

        existing = self.get_call(call.get('id'), update_data=cur_call)

        from policy.models import CustomerPolicyState
        guid = existing.cospace_id if existing.cospace_id != 'AdHoc' else existing.guid
        if record.get('type') == 'callStart' and not existing.ts_stop and existing.ts_start > now() - timedelta(hours=1):
            if self.server.set_call_active(guid, record.get('callBridge') or ''):
                CustomerPolicyState.objects.change_calls(
                    1, acano_tenant_id=existing.tenant, name=guid
                )
        elif (
            record.get('type') == 'callEnd'
            and existing.ts_stop
            and existing.ts_stop > now() - timedelta(hours=1)
        ):
            if self.server.remove_active_call_node(guid, record.get('callBridge') or ''):
                CustomerPolicyState.objects.change_calls(
                    -1, acano_tenant_id=existing.tenant, name=guid
                )

        if record.get('type') == 'callEnd':
            self.finalize_call(existing, commit=True)
        else:
            existing.save()

    def parse_call_leg(self, leg, record):

        cur_leg = {}
        fallback_data = {}

        cache_key = 'possible_spam:{}:{}'.format(self.server.id, leg.get('id'))

        if record.get('type') == 'callLegStart':
            if set(leg.findtext(k, '') for k in ('./remoteParty', './remoteAddress', './call')) == {
                ''
            }:
                return
            self.populate_call_leg_start_data(leg, cur_leg, record)

        elif record.get('type') == 'callLegEnd':

            if leg.find('./reason').text in ('unknownDestination', 'ringingTimeout'):
                self.log_spam(leg, cache_key, record)

            self.populate_call_leg_end_data(leg, cur_leg, record)

        elif record.get('type') == 'callLegUpdate':
            if leg.find('./displayName') is not None:
                cur_leg['name'] = leg.findtext('./displayName') or ''
            if leg.find('./remoteAddress') is not None:
                fallback_data['target'] = leg.findtext('./remoteAddress') or ''
            if leg.find('./sipCallId') is not None:
                fallback_data['protocol'] = Leg.SIP

        if cur_leg or fallback_data:
            fallback_data.setdefault('ts_start', self._timestamp(record.get('time')))

        call_guid = _text(leg.find('./call'))

        # temporary store possible spam legs in separate table until connected to a real call
        if record.get('type') == 'callLegStart' and not call_guid:
            self.store_possible_spam_leg(leg, cur_leg, cache_key)
            return

        # load any possible spam leg data to get a complete picture before save
        cur_leg = self.load_possible_spam_leg(leg, cur_leg, cache_key, record, fallback_data)
        if not cur_leg:
            return

        if cur_leg.get('target'):
            cur_leg['target'] = clean_target(cur_leg['target'])

        existing = self.get_call_leg(
            leg.get('id'), call_guid, update_data=cur_leg, fallback_data=fallback_data
        )

        from policy.models import CustomerPolicyState

        ignore = False

        if not existing.ts_start or max(existing.ts_start, existing.ts_stop or existing.ts_start) < now() - timedelta(hours=2):
            ignore = True  # old event. ignore
        elif record.get('type') == 'callLegStart':
            CustomerPolicyState.objects.change_participants(1, cluster=self.server.cluster, acano_tenant_id=existing.tenant, guid=leg.get('id'), name=leg.findtext('./displayName', ''), source='cdr')
        elif record.get('type') == 'callLegEnd':
            CustomerPolicyState.objects.change_participants(-1, cluster=self.server.cluster, acano_tenant_id=existing.tenant, guid=leg.get('id'), name=leg.findtext('./displayName', ''), source='cdr')

        if record.get('type') == 'callLegEnd':
            self.finalize_call_leg(existing, commit=True)
        elif not ignore and call_guid and existing.call.cospace_id:
            self.server.set_call_active(existing.call.cospace_id, record.get('callBridge') or '')

        try:
            from cdrhooks.models import Hook
            if existing.call_id:
                Hook.objects.handle_tag(record.get('type'), existing)
        except Exception:
            if RERAISE_ERRORS:
                raise
            capture_exception()

    def log_spam(self, leg, cache_key, record):
        if leg.find('./reason').text == 'unknownDestination':
            spam_type = 'unknown_destination'
        else:
            spam_type = 'other'
        cache.delete(cache_key)
        PossibleSpamLeg.objects.filter(server=self.server, guid=leg.get('id')).delete()
        try:
            cur_date = self._timestamp(record.get('time')).date()
        except (ValueError, AttributeError):
            cur_date = now().date()
        self.add_spam(cur_date, spam_type)

    def populate_call_leg_start_data(self, leg, cur_leg, record):
        if leg.find('./localAddress') is not None:
            cur_leg['local'] = leg.find('./localAddress').text
        if leg.findtext('./subType', '') == 'lync':
            if leg.findtext('./lyncSubType', '') in ('', 'audioVideo'):
                cur_leg['protocol'] = Leg.LYNC
            else:
                cur_leg['protocol'] = Leg.LYNC_SUB
        elif leg.findtext('./subType', '') == 'distributionLink':
            cur_leg['protocol'] = Leg.CLUSTER
            cur_leg['should_count_stats'] = False
        elif leg.findtext('./type', '') == 'acano':
            cur_leg['protocol'] = Leg.CMS
        elif leg.findtext('./type', '') == 'sip':
            cur_leg['protocol'] = Leg.SIP
        cur_leg['remote'] = leg.findtext('./remoteParty') or leg.findtext('./remoteAddress') or ''
        cur_leg['ts_start'] = record.get('time') or str(now())
        if leg.find('./direction') is not None and leg.find('./direction').text:
            cur_leg['direction'] = leg.find('./direction').text
        guest = leg.find('./guestConnection')
        name = leg.find('./displayName')
        if name is not None:
            cur_leg['name'] = re.sub(r'\s\s+', ' ', name.text or '', re.DOTALL).strip()[:300]
        if guest is not None and guest.text == 'true':
            cur_leg['target'] = 'guest'
            cur_leg['is_guest'] = True
        elif cur_leg['direction'] == 'outgoing':
            cur_leg['target'] = cur_leg.get('remote', '')
        elif leg.findtext('./recording') == 'true':
            cur_leg['target'] = 'recording'
            cur_leg['is_guest'] = True
            cur_leg['protocol'] = Leg.STREAM
        elif leg.findtext('./streaming') == 'true':
            cur_leg['target'] = 'stream'
            cur_leg['is_guest'] = True
            cur_leg['protocol'] = Leg.STREAM
        elif cur_leg['direction'] == 'incoming' and is_phone(cur_leg.get('remote') or cur_leg.get('local')):
            cur_leg['target'] = is_phone(cur_leg.get('remote') or cur_leg.get('local'))
        elif cur_leg['direction'] == 'incoming' and leg.find('./ivr') is not None:
            cur_leg['target'] = 'IVR'
            cur_leg['is_guest'] = True
        else:
            cur_leg['target'] = cur_leg.get('remote', '')
        if not cur_leg['target']:
            cur_leg['target'] = cur_leg['remote'] or cur_leg['local']
        cur_leg['target'] = rewrite_internal_domains(cur_leg['target'],
                                                     default_domain=self.server.default_domain)
        from endpoint.models import Endpoint
        endpoint = Endpoint.objects.get_from_uri(cur_leg['target'])
        if endpoint:
            cur_leg['endpoint'] = endpoint

    def populate_call_leg_end_data(self, leg, cur_leg, record):
        cur_leg['ts_stop'] = record.get('time')

        if leg.find('durationSeconds') is not None:
            cur_leg['duration'] = float(leg.findtext('./durationSeconds', '0'))
            if cur_leg['ts_stop']:
                cur_leg['ts_start'] = self._timestamp(cur_leg['ts_stop']) - timedelta(
                    seconds=cur_leg['duration']
                )

        def _set_percentage(key, node):
            if node is not None:
                cur_leg[key] = int(float(node.text) * 10)

        media = leg.find('./mediaUsagePercentages')
        if media is not None:
            _set_percentage('viewer_percent', media.find('./mainVideoViewer'))
            _set_percentage('contribution_percent', media.find('./mainVideoContributor'))
            _set_percentage('presentation_contribution_percent', media.find('./presentationContributor'))
        for alarm in leg.findall('./alarm'):
            if alarm.get('type') == 'packetLoss':
                cur_leg['packetloss_percent'] = int(float(alarm.get('durationPercentage')) * 10)
            elif alarm.get('type') == 'excessiveJitter':
                cur_leg['jitter_percent'] = int(float(alarm.get('durationPercentage')) * 10)
            elif alarm.get('type') == 'highRoundTripTime':
                cur_leg['high_roundtrip_percent'] = int(float(alarm.get('durationPercentage')) * 10)

    def store_possible_spam_leg(self, leg, cur_leg, cache_key):
        if cur_leg.get('endpoint'):
            cur_leg['endpoint'] = cur_leg['endpoint'].pk
        if CACHE_ACTIVE:
            cache.set(cache_key, DjangoJSONEncoder().encode(cur_leg), 24 * 60 * 60)
        else:
            PossibleSpamLeg.objects.get_or_create(guid=leg.get('id'), server=self.server,
                                                  defaults=dict(ts_start=cur_leg['ts_start'],
                                                                data_json=DjangoJSONEncoder().encode(
                                                                    cur_leg)))

    def load_possible_spam_leg(self, leg, cur_leg, cache_key, record, fallback_data=None):
        data_json = cache.get(cache_key)
        if data_json is not None:
            cache.delete(cache_key)
        else:  # not in cache, try load from db to be safe
            possible_legs = PossibleSpamLeg.objects.filter(server=self.server, guid=leg.get('id'))
            try:
                data_json = possible_legs.values_list('data_json', flat=True)[0]
            except IndexError:
                return cur_leg or fallback_data or {}  # no extra data found
            possible_legs.delete()

        cur_leg = {**json.loads(data_json), **cur_leg}  # merge old and new data

        duration = None
        if cur_leg.get('ts_start') and cur_leg.get('ts_stop'):
            duration = (self._timestamp(cur_leg['ts_start']) - self._timestamp(cur_leg['ts_stop'])).total_seconds()

        if record.get('type') == 'callLegEnd' and not cur_leg.get('call'):
            # spam after all -  lazy bot, disconnect before answer
            if duration is not None and duration <= 2:
                self.add_spam(self._timestamp(cur_leg['ts_start']).date(), 'unknown_destination')
                return None

        # load related models from pks
        if isinstance(cur_leg.get('endpoint'), int):
            from endpoint.models import Endpoint
            cur_leg['endpoint'] = Endpoint.objects.filter(pk=cur_leg['endpoint']).first()
        return cur_leg

    def finalize_call_leg(self, leg, commit=None):

        cur_leg = {}

        leg.load_dates()

        if not leg.duration and leg.ts_start and leg.ts_stop:
            leg.duration = cur_leg['duration'] = (leg.ts_stop - leg.ts_start).total_seconds()

        if (leg.duration or cur_leg.get('duration') or 0) <= 60:
            cur_leg['should_count_stats'] = False

        if leg.protocol == Leg.LYNC_SUB:
            cur_leg['should_count_stats'] = False

        if not leg.call_id and leg.protocol == Leg.LYNC:
            cur_leg['call'] = self.get_call(leg.guid, update_data={
                'ts_start': leg.ts_start,
                'ts_stop': leg.ts_stop,
                'tenant_fallback': leg.tenant,
                'cospace': 'Lync'
            })

        if not leg.ou and leg.target not in ('streaming', 'recording'):
            ou = get_ou(leg.target)
            if ou:
                leg.ou = cur_leg['ou'] = ou

        if not leg.org_unit:
            org_unit = get_org_unit(leg.target)
            if org_unit and org_unit.customer.acano_tenant_id != leg.tenant:
                org_unit = None

            if not org_unit and leg.call and leg.call.org_unit:
                org_unit = leg.call.org_unit
            if org_unit:
                leg.org_unit = cur_leg['org_unit'] = org_unit

        if not leg.org_unit and leg.call and leg.call.cospace_id:
            org_unit = get_org_unit(leg.call.cospace_id)
            if org_unit:
                leg.org_unit = cur_leg['org_unit'] = org_unit

        if leg.tenant and not leg.tenant_fk_id:
            cur_leg['tenant_fk'] = tenant_obj(leg.tenant)

        if cur_leg:  # updated

            Leg.objects.filter(pk=leg.pk).update(**cur_leg)

            for k, v in list(cur_leg.items()):
                setattr(leg, k, v)

            if commit or commit is None:
                leg.save()
        else:
            if commit:
                leg.save()

    def finalize_call(self, call, commit=None):
        from customer.models import CustomerMatch

        cur_call = {}

        legs = Leg.objects.filter(call=call)

        agg = legs.aggregate(min=Min('ts_start'), max=Max('ts_stop'))
        ts_start, ts_stop = agg['min'], agg['max']

        self.call_end_set_legs_stop(call)

        try:
            # clustered by correlator
            if call.correlator_guid:
                clustered = Call.objects.exclude(pk=call.pk).filter(
                    ts_start__gte=ts_start - timedelta(days=LEG_LOWER_BOUND),
                    ts_start__lt=ts_stop,
                    ts_stop__gt=ts_start,
                    correlator_guid=call.correlator_guid)
            else:
                clustered = []

            # high resiliant, cluster by cospace id
            clustered = list(clustered) + list(
                Call.objects.exclude(pk=call.pk)
                .exclude(correlator_guid=call.correlator_guid or '-')
                .filter(
                    ts_start__lt=ts_stop,
                    ts_start__gte=ts_start - timedelta(days=LEG_LOWER_BOUND),
                    ts_stop__gt=ts_start,
                    cospace_id=call.cospace_id,
                )
            )
        except Exception:  # e.g. correlator does not exist
            pass
        else:
            for c in clustered:  # merge clustered calls
                Leg.objects.filter(call=c).update(call=call, orig_call=c)

            agg = legs.aggregate(min=Min('ts_start'), max=Max('ts_stop'))

            ts_start, ts_stop = agg['min'], agg['max']

        total = legs.filter(duration__gte=60, should_count_stats=True).aggregate(total=Sum('duration'))
        cur_call['total_duration'] = total['total'] or 0

        if ts_start:
            cur_call['ts_start'] = ts_start

        if ts_stop:
            cur_call['ts_stop'] = ts_stop

        call_ou = call.ou
        call_tenant = call.tenant
        call_unit = call.org_unit if call.org_unit_id else None

        tag_data = dict(parse_qsl(call.cdr_tag)) or {} if call.cdr_tag else {}
        creator = tag_data.get('creator') or tag_data.get('username')
        owner = creator or get_owner(call.cospace_id) or ''

        if call.cospace_id:
            call_ou = call_ou or get_ou(call.cospace_id)
            call_unit = call_unit or get_org_unit(call.cospace_id) or get_org_unit(owner)

        if not call_ou:
            if tag_data.get('ou'):
                call_ou = tag_data['ou']
            if creator:
                call_ou = get_ou(creator)
            if not call_ou and call.cospace_id:
                call_ou = get_ou(owner)
                if not call_ou:
                    call_ou = get_ou_from_members(call.cospace_id)

        if not call_tenant:
            match_customer = CustomerMatch.objects.match_text(creator, cluster=self.server.cluster)
            if match_customer:
                call_tenant = match_customer.acano_tenant_id

        legs = list(legs)
        if all(l.is_guest for l in legs):
            if owner:
                try:
                    longest_leg = sorted(legs, key=lambda x: x.duration)[-1]
                except IndexError:
                    pass
                else:
                    longest_leg.target = owner
                    longest_leg.save()

        update_ou = []
        update_tenant = []

        # set default ou and tenant
        for l in legs:

            cur_ou = l.ou
            if not cur_ou:
                update_ou.append(l.pk)

            if not l.tenant:
                cur_customer = CustomerMatch.objects.match_text(l.remote, cluster=self.server.cluster)
                if cur_customer:
                    cur_tenant_fk = tenant_obj(cur_customer.acano_tenant_id)
                    Leg.objects.filter(pk=l.pk).update(tenant=cur_customer.acano_tenant_id, tenant_fk=cur_tenant_fk)
                else:
                    update_tenant.append(l.pk)

        call_ous = Counter(l.ou for l in legs if l.ou and l.duration > 60 and l.should_count_stats)
        if not call_ou and call_ous:
            call_ou = call_ous.most_common()[0][0]
            cur_call['ou'] = call_ou

        call_units = Counter(l.org_unit_id for l in legs if l.org_unit_id and l.should_count_stats)
        if not call_unit and call_units:
            from organization.models import OrganizationUnit
            call_unit = OrganizationUnit.objects.filter(pk=call_units.most_common()[0][0]).first()
            cur_call['org_unit'] = call_unit

        # change leg data
        if update_ou and call_ou:
            Leg.objects.filter(call=call, pk__in=update_ou).update(ou=call_ou)

        if update_tenant and call_tenant:
            call_tenant_fk = tenant_obj(call_tenant)
            Leg.objects.filter(call=call, pk__in=update_tenant).update(tenant=call_tenant, tenant_fk=call_tenant_fk)

        # apply changes
        if call_ou != call.ou:
            cur_call['ou'] = call_ou or ''
        if call_tenant != call.tenant:
            cur_call['tenant_fk'] = tenant_obj(call_tenant) if call_tenant else None
            cur_call['tenant'] = call_tenant or ''

        if call_unit and call_unit.id != call.org_unit_id:
            cur_call['org_unit'] = call_unit

        if cur_call:  # updated
            Call.objects.filter(pk=call.pk).update(**cur_call)

            for k, v in list(cur_call.items()):
                setattr(call, k, v)

            if commit or commit is None:
                call.save()
        else:
            if commit:
                call.save()

    def call_end_set_legs_stop(self, call):
        # TODO update should_count_stats as well, or better to keep only including verified
        # call time?

        with transaction.atomic():
            legs = Leg.objects.filter(call=call, ts_stop__isnull=True).select_for_update(
                of=('self',), skip_locked=True
            )
            list(legs.only('id'))
            legs.update(ts_stop=self._timestamp(call.ts_stop))

    def add_spam(self, date, spam_types, count=1):
        if isinstance(spam_types, str):
            spam_types = [spam_types]

        update_kwargs = {k: F(k) + count for k in spam_types}

        if not InvalidCallStats.objects.filter(day=date, server=self.server).update(**update_kwargs):
            InvalidCallStats.objects.get_or_create(day=date, server=self.server, defaults={k: count for k in spam_types})

