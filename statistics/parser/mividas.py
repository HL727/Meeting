import logging
import re
from datetime import timedelta, datetime
from typing import Iterator, Tuple, List, Dict

from cacheout import fifo_memoize, memoize, FIFOCache
from django.conf import settings
from django.db import transaction, models
from django.db.models import Q
from django.utils.dateparse import parse_datetime

from shared.utils import maybe_update
from statistics.parser.utils import is_phone, rewrite_internal_domains, \
    get_internal_domains, clean_target
from ..models import Leg, Call, Tenant, LegConversation, Server, tenant_obj, lock_tenant

LIMIT = 2 * 60

logger = logging.getLogger(__name__)


@fifo_memoize(100, ttl=10)
def org_unit_obj(org_unit_path: str, customer_id: int):
    if not org_unit_path:
        return None
    from organization.models import OrganizationUnit
    return OrganizationUnit.objects.get_or_create_by_full_name(org_unit_path, customer_id)


class MividasCSVImportExport:
    """
    Handler for importing and exporting Leg and Call-data
    """

    def __init__(self, server: Server, debug=False):
        self.server = server
        self.internal_domains = get_internal_domains()
        self.fallback_customer_id = self.server.customer_id
        from customer.models import Customer

        self.call_cache = FIFOCache(maxsize=100)
        self.leg_cache = FIFOCache(maxsize=100)

        self.merge_calls_queue: Dict[int, int] = {}

        if not self.fallback_customer_id and Customer.objects.all().count() == 1:
            self.fallback_customer_id = Customer.objects.all().first().pk

        self.protocol_maps = self.get_protocol_maps()

    def _parse_times(self, data):
        ts_start = parse_datetime(data.get('ts_start')).replace(microsecond=0)
        if data.get('ts_stop'):
            ts_stop = parse_datetime(data['ts_stop']).replace(microsecond=0)
        else:
            ts_stop = None

        return ts_start, ts_stop

    def _rewrite_domain(self, target):
        return rewrite_internal_domains(target, default_domain=self.server.default_domain, internal_domains=self.internal_domains)

    def get_protocol_maps(self):

        map = (
            ('SIP', Leg.SIP,),
            ('CLUSTER', Leg.CLUSTER,),
            ('CMS', Leg.CMS,),
            ('WEBRTC', Leg.WEBRTC,),
            ('H323', Leg.H323,),
            ('TEAMS', Leg.TEAMS,),
            ('STREAM', Leg.STREAM,),
            ('LYNC', Leg.LYNC,),
            ('LYNC_SUB', Leg.LYNC_SUB,),
        )

        from_text_map = {x[0]: x[1] for x in map}
        to_text_map = {x[1]: x[0] for x in map}
        return from_text_map, to_text_map

    def parse_target_data(self, target) -> Tuple[str, dict]:

        target = self._rewrite_domain(clean_target(target))

        from endpoint.models import Endpoint
        endpoint = Endpoint.objects.get_from_uri(target, only='id')
        if endpoint:
            endpoint_kwargs = {'endpoint': endpoint}
        else:
            endpoint_kwargs = {}

        if is_phone(target):
            target = is_phone(target)

        return target, endpoint_kwargs

    def get_call_for_time(self, guid: str, ts_start=None, **kwargs):
        """
        Find call for time using guid and time information
        """

        cached = self.call_cache.get(guid)
        if cached and guid:
            return cached

        ts_start_fallback = kwargs.pop('ts_start_fallback', None)
        ts_stop_fallback = kwargs.pop('ts_stop_fallback', None)

        if ts_start:
            ts_start_fallback = ts_start

        ts_stop_fallback = kwargs.get('ts_stop') or ts_stop_fallback or ts_start_fallback + timedelta(minutes=15)

        calls = Call.objects.filter(server=self.server,
                                    ts_start__lte=ts_stop_fallback,
                                    guid=guid).filter(
            Q(ts_stop__isnull=True) | Q(ts_stop__gte=ts_start_fallback)
        )

        tenant_fallback = kwargs.pop('tenant_fallback', None)

        with transaction.atomic():
            lock_tenant(kwargs.get('tenant') or tenant_fallback or '')

            create_kwargs = kwargs.copy()
            create_kwargs['ts_start'] = ts_start_fallback
            if tenant_fallback:
                kwargs['tenant'] = kwargs.get('tenant') or tenant_fallback

            call, created = calls.get_or_create(server=self.server, guid=guid, defaults=create_kwargs)
            if created:
                logger.debug('Created call %s for ts_start=%s, ts_stop=%s with guid %s',
                             call.pk, ts_start, kwargs.get('ts_stop'), guid)
            else:
                logger.debug('Matched existing call %s, ts_start=%s, ts_stop=%s for space %s',
                             call.pk, ts_start, kwargs.get('ts_stop'), guid)

        if tenant_fallback and not call.tenant and not created:
            kwargs['tenant'] = tenant_fallback

        if ts_start:
            kwargs['ts_start'] = ts_start

        if not created:
            maybe_update(call, kwargs)

        self.merge_calls_queue[call.pk] = call.pk
        self.call_cache.set(guid, call)

        return call

    def get_or_create_leg(self, call, guid, leg_data, conversation=None):
        """
        get existing leg object, or lock call/conversation while creating it
        """

        cached = self.leg_cache.get(guid)
        if cached and guid:
            return cached, False

        leg_qs = Leg.objects.filter(ts_start__gt=leg_data['ts_start'] - timedelta(days=3)) \
            .select_for_update(of=('self',))

        if conversation:
            LegConversation.objects.select_for_update(of=('self',)).get(pk=conversation.pk)
        else:
            Call.objects.select_for_update(of=('self',)).get(pk=call.pk)
        leg, created = leg_qs.get_or_create(server=self.server, guid=guid, defaults=leg_data)

        self.leg_cache.set(guid, leg)
        return leg, created

    call_fields = [
        # 'id',
        # 'server',
        'guid',
        'tenant',
        # 'tenant_fk',
        'cospace',
        'cospace_id',
        'ou',
        'correlator_guid',
        'org_unit',  # -> full path
        # 'meeting',
        'cdr_tag',
        'leg_count',
        'duration',
        'total_duration',
        'ts_start', # -> isoformat
        'ts_stop', # -> isoformat
        'licenses_json'
    ]
    call_int_fields = ['leg_count', 'duration', 'total_duration']

    def export_calls(self, ts_start: datetime, ts_stop: datetime):

        @memoize(200)
        def _org_unit(org_unit_id):
            from organization.models import OrganizationUnit
            return OrganizationUnit.objects.get(pk=org_unit_id).full_name

        def _iter(it: Iterator[dict]) -> Iterator[list]:
            for cur in it:
                cur['ts_start'] = cur['ts_start'].isoformat() if cur['ts_start'] else None
                cur['ts_stop'] = cur['ts_stop'].isoformat() if cur['ts_stop'] else None

                if cur['org_unit']:
                    cur['org_unit'] = _org_unit(cur['org_unit'])
                yield [cur[f] if cur[f] is not None else '' for f in self.call_fields]

        qs = Call.objects\
            .filter(server=self.server, ts_start__lt=ts_stop)\
            .filter(Q(ts_stop__gt=ts_start) | Q(ts_stop__isnull=True)).order_by('ts_start', 'guid')

        if not settings.TEST_MODE and 'direct' in settings.DATABASES:
            qs = qs.using('direct')

        return self.call_fields, _iter(qs.values(*self.call_fields).iterator())

    def load_call_data(self, call_data: dict):

        REQUIRED = ['ts_start', 'guid']

        missing = [r for r in REQUIRED if not call_data.get(r)]
        if missing:
            logger.info('Missing call fields %s. Ignoring', missing)
            return

        org_unit_path = call_data.pop('org_unit', None)
        org_unit = None
        customer_id = self.fallback_customer_id  # TODO or Customer.objects.find(call_data.get('tenant')
        if org_unit_path and customer_id:
            org_unit = org_unit_obj(call_data.pop('org_unit', None), customer_id)

        fields = {f.name: f for f in Call._meta.fields}
        db_fields = {k: fields[k].to_python(v if v not in ('', None) else None)
                     for k, v in call_data.items()
                     if k in fields and k in self.call_fields}

        db_fields['org_unit'] = org_unit

        for f in fields.values():
            if isinstance(f, models.CharField) and db_fields.get(f.name, '') is None:
                db_fields[f.name] = ''

        return db_fields

    def import_calls(self, input_data_list: List[dict]):
        parsed = [self.load_call_data(dct) for dct in input_data_list if dct]

        # warm up cache
        for call in Call.objects.filter(server=self.server, guid__in={dct['guid'] for dct in parsed if dct} or ['-']):
            self.call_cache.set(call.guid, call)

        return [self.handle_call(dct) if dct else None for dct in parsed]

    def import_call(self, input_data: dict):

        parsed = self.load_call_data(input_data)
        if not parsed:
            return

        return self.handle_call(parsed)

    def handle_call(self, call_data: dict):

        if not call_data['ts_start']:
            return

        call = self.get_call_for_time(
            guid=call_data.pop('guid'),
            **call_data,
        )

        return call

    leg_fields = [
        # 'id',
        #'server',
        'call__guid',  # -> guid
        'call__cospace',
        'call__cospace_id',
        # 'orig_call',
        'tenant',
        # 'tenant_fk',
        'guid',
        'guid2',
        'conversation__guid',  # -> guid
        'name',
        'protocol',
        'should_count_stats',
        'direction',
        'remote',
        'local',
        'target',
        # 'domain',
        'endpoint__sip',  # -> sip
        'ts_start',  # -> isoformat
        'ts_stop',  # -> isoformat
        'duration',
        'head_count',
        'presence',
        'is_guest',
        'ou',
        'org_unit',  # -> full path
        'tx_pixels',
        'rx_pixels',
        'bandwidth',
        'packetloss_percent',
        'jitter_percent',
        'high_roundtrip_percent',
        'jitter',
        'jitter_peak',
        'role',
        'service_type',
        'license_count',
        'license_type',
        'contribution_percent',
        'presentation_contribution_percent',
        'viewer_percent',
    ]

    def export_legs(self, ts_start: datetime, ts_stop: datetime):

        @memoize(200)
        def _org_unit(org_unit_id):
            from organization.models import OrganizationUnit
            return OrganizationUnit.objects.get(pk=org_unit_id).full_name

        def _iter(it: Iterator[dict]) -> Iterator[list]:
            for cur in it:
                cur['ts_start'] = cur['ts_start'].isoformat() if cur['ts_start'] else None
                cur['ts_stop'] = cur['ts_stop'].isoformat() if cur['ts_stop'] else None

                if cur['protocol']:
                    cur['protocol'] = self.protocol_maps[1][cur['protocol']]

                if cur['org_unit']:
                    cur['org_unit'] = _org_unit(cur['org_unit'])

                if self.server.is_vcs and not cur['guid']:  # try to generate vcs leg guid
                    if cur['local'] == cur['target']:
                        cur['guid'] = cur['call__guid'] + 's'
                    else:
                        cur['guid'] = cur['call__guid'] + 'd'

                yield [cur[f] if cur[f] is not None else '' for f in self.leg_fields]

        qs = Leg.objects\
            .filter(server=self.server, ts_start__lt=ts_stop)\
            .filter(Q(ts_stop__gt=ts_start) | Q(ts_stop__isnull=True)).order_by('ts_start', 'guid')

        if not settings.TEST_MODE and 'direct' in settings.DATABASES:
            qs = qs.using('direct')
        return self.leg_fields, _iter(qs.values(*self.leg_fields).iterator())

    def load_leg_data(self, leg_data: dict):

        REQUIRED = ['ts_start', 'guid', 'target', 'call__guid']

        missing = [r for r in REQUIRED if not leg_data.get(r)]

        if missing:
            logger.info('Missing leg data %s. Ignoring', missing)
            return

        extra = {k: leg_data[k]
                 for k in ('conversation__guid', 'endpoint__sip', 'call__guid', 'call__cospace', 'call__cospace_id')
                 if leg_data.get(k)}

        if leg_data.get('protocol'):
            leg_data['protocol'] = self.protocol_maps[0].get(leg_data['protocol']) or Leg.SIP

        org_unit_path = leg_data.pop('org_unit', None)
        org_unit = None

        customer_id = self.fallback_customer_id  # TODO or Customer.objects.find(leg_data.get('tenant')
        if org_unit_path and customer_id:
            org_unit = org_unit_obj(leg_data.pop('org_unit', None), customer_id)

        fields = {f.name: f for f in Leg._meta.fields}
        db_fields = {k: fields[k].to_python(v if v not in ('', None) else None)
                     for k, v in leg_data.items()
                     if k in fields and k in self.leg_fields}

        db_fields['org_unit'] = org_unit

        for f in fields.values():
            if isinstance(f, models.CharField) and db_fields.get(f.name, '') is None:
                db_fields[f.name] = ''

        return db_fields, extra

    def import_legs(self, input_data_list: Iterator[dict]):
        parsed = [self.load_leg_data(dct) for dct in input_data_list]

        # warm up cache
        for leg in Leg.objects.filter(server=self.server, guid__in={cur[0]['guid'] for cur in parsed if cur} or ['-']):
            self.leg_cache.set(leg.guid, leg)
        for call in Call.objects.filter(server=self.server, guid__in={cur[1]['call__guid'] for cur in parsed if cur and cur[1].get('call__guid')} or ['-']):
            self.call_cache.set(call.guid, call)

        return [self.handle_leg(cur[0], cur[1]) if cur else None for cur in parsed]

    def import_leg(self, input_data: dict):
        parsed = self.load_leg_data(input_data)
        if not parsed:
            return
        return self.handle_leg(parsed[0], parsed[1])

    def handle_leg(self, leg_data: dict, extra: dict):

        leg_data['local'] = leg_data['local'].replace('sip:', '')
        leg_data['remote'] = leg_data['remote'].replace('sip:', '')

        if leg_data['ts_start'] and leg_data.get('ts_stop'):
            leg_data['duration'] = int((leg_data['ts_stop'] - leg_data['ts_start']).total_seconds())

        target, endpoint_kwargs = self.parse_target_data(extra.get('endpoint__sip') or leg_data['target'])
        leg_data.update(endpoint_kwargs)

        call_kwargs = {}
        if leg_data.get('call__cospace'):
            call_kwargs['cospace'] = extra.get('call__cospace')
        if leg_data.get('call__cospace_id'):
            call_kwargs['cospace_id'] = extra.get('call__cospace_id')

        call = self.get_call_for_time(
            extra['call__guid'],
            ts_start_fallback=leg_data['ts_start'],
            ts_stop_fallback=leg_data.get('ts_stop'),
            tenant_fallback=leg_data['tenant'],
            **call_kwargs,
        )

        conversation = None
        conversation_id = extra.get('conversation__guid')

        if conversation_id and conversation_id != leg_data['guid']:
            # make sure conversation exists so it can be locked later
            conversation = LegConversation.objects.get_or_create(server=self.server, guid=conversation_id,
                                                                 defaults=dict(first_leg_guid='')
                                                                 )[0]

        leg_data.update({
            'call': call,
            'tenant_fk': tenant_obj(leg_data['tenant']),
            'name': re.sub(r'\s\s+', ' ', (leg_data.get('name') or '').split('|')[0], re.DOTALL).strip()[:300],
        })

        with transaction.atomic():

            leg, created = self.get_or_create_leg(call, leg_data['guid'], leg_data, conversation=conversation)

            if not created:
                maybe_update(leg, leg_data)

        return leg

    def merge_calls(self):
        calls = Call.objects.filter(server=self.server).in_bulk(self.merge_calls_queue)
        for call_id in self.merge_calls_queue:
            if call_id in calls:
                calls[call_id].merge_calls('cospace_id')
