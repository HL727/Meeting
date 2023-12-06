import hashlib
import typing
from datetime import timedelta
from typing import Sequence, Union, Literal

from cacheout import fifo_memoize
from django.contrib.postgres.indexes import BrinIndex
from django.core.cache import cache
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_datetime
from django.db import models, transaction
from django.db.models.aggregates import Sum, Count
import json
from django.conf import settings
import requests
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ngettext, ugettext_lazy as _
import logging

from provider.exceptions import NotFound
from shared.utils import partial_update_or_create, partial_update

if typing.TYPE_CHECKING:
    from customer.models import Customer

'''
Warning
========

These tables can grow very large. Always use null=True for new columns and
tests thoroughly (with 5GB+ tables) before making migration or index changes.

Structure:
==========

Server:
-------
Container for statistics.

Multitenant clusters (Pexip, Acano) are separated by Leg.tenant, and single tenant
(e.g. Endpoint) uses Server.customer

Tenant: ID of customer tenant in MCU. Connected to servers using ServerTenant
so that whole table is not required to be scanned to determinate belongings

Call:
------
A single instance of (part of) a call

Acano uses separate guid for each calls on each clustered node. Mividas merges
distibuted calls when they are finished. Pexip sends no guid for live events
and group calls on clustered nodes using 'name'. Mividas merges distributed
live calls directly.

Leg | ActiveLeg:
----
Part of a connected participant.

The same participant can use multiple legs, e.g. one for presentation, one
for audio etc. Only one is counted using 'should_count_stats'.

ActiveLeg model is used up until the leg is finished, and data is then moved
to Leg. This due to lots of events which changes content and wreaks havoc
on table disk space and indexes.
'''


logger = logging.getLogger(__name__)

Q = models.Q


def new_key():
    import uuid
    return uuid.uuid4().hex


@fifo_memoize(128, ttl=10)
def tenant_obj(tenant_guid: str) -> 'Tenant':
    return Tenant.objects.get_or_create(guid=tenant_guid)[0]


def lock_tenant(tenant_guid: str) -> 'Tenant':
    obj = tenant_obj(tenant_guid)
    return Tenant.objects.select_for_update(of=('self',)).get(pk=obj.pk)


@fifo_memoize(128, ttl=10)
def tenant_server(tenant_guid: str, server_id: int) -> 'ServerTenant':
    tenant = tenant_obj(tenant_guid)
    return ServerTenant.objects.get_or_create(tenant=tenant, server=Server(pk=server_id))[0]


class ServerManager(models.Manager):

    def filter_for_customer(self, customer, **kwargs):
        return self.filter_for_customers([customer], **kwargs)

    def filter_for_customers(self, customers, **kwargs):

        empty_customers = set()
        empty_tenant_clusters = {}

        tenant_ids = set()
        for customer in customers:
            if not customer:
                continue

            guids = {customer.pexip_tenant_id, customer.acano_tenant_id}
            add_cluster_without_tenant = None

            try:
                cluster = customer.get_api().cluster
            except (AttributeError, NotFound):
                pass
            else:
                if cluster.is_acano and not customer.acano_tenant_id:
                    add_cluster_without_tenant = cluster
                if cluster.is_pexip and not customer.get_pexip_tenant_id():
                    add_cluster_without_tenant = cluster

            if add_cluster_without_tenant:
                empty_tenant_clusters[add_cluster_without_tenant] = True
                empty_customers.add(customer.pk)

            tenant_ids.update(guids - {''})

        if tenant_ids or empty_customers:
            server_ids = set(
                Server.objects.filter(
                    customer__isnull=True, tenants__guid__in=tenant_ids
                ).values_list('id', flat=True)
            )
            server_ids.update(
                Server.objects.filter(
                    Q(customer__in=empty_customers)
                    | Q(cluster__in=empty_tenant_clusters, tenants__guid='')
                ).values_list('id', flat=True)
            )

            tenant_filter = {'pk__in': server_ids}
        else:
            tenant_filter = {}

        qs = self.distinct().filter(Q(customer__isnull=True, **tenant_filter) | Q(customer__in=customers))
        if kwargs:
            return qs.filter(**kwargs)
        return qs

    def filter_for_user(self, user, customer=None, **kwargs):
        from customer.models import Customer
        from customer.utils import user_has_all_customers

        if user_has_all_customers(user):
            if customer:
                return self.filter_for_customer(customer)
            return self.all()

        customers = Customer.objects.get_for_user(user)

        if customer:
            return self.filter_for_customer(customers.filter(pk=customer.pk))
        return self.filter_for_customers(customers)

    def get_for_customer(self, customer, create=None, **kwargs):

        def _result(qs):
            if kwargs:
                qs = qs.filter(**kwargs)

            result = qs.first()
            if result:
                return result

            if create:
                with transaction.atomic():
                    from customer.models import Customer
                    Customer.objects.filter(pk=customer.pk if customer else None).select_for_update()
                    result = qs.get_or_create(customer=customer, defaults=create)[0]
                return result
            return result

        return _result(self.filter_for_customer(customer))

    def get_endpoint_server(self, customer: 'Customer'):
        return self.get_for_customer(
            customer,
            type=Server.ENDPOINTS,
            create=dict(name=ngettext('System', 'System', 2), type=Server.ENDPOINTS),
        )


class Server(models.Model):
    """Statistics container for a single cluster or customers endpoints"""

    ACANO = 0
    VCS = 1
    ENDPOINTS = 2
    COMBINE = 3
    PEXIP = 4
    ROOM = 5

    TYPES = (
        (ACANO, 'Cisco Meeting Server'),
        (PEXIP, 'Pexip'),
        (VCS, 'Cisco VCS'),
        (ENDPOINTS, 'Endpoints'),
        (COMBINE, 'Combine'),
    )

    name = models.CharField(max_length=255)
    default_domain = models.CharField(max_length=200, blank=True)
    secret_key = models.CharField(max_length=100, default=new_key, editable=False, blank=True, db_index=True)
    customer = models.ForeignKey('provider.Customer', null=True, blank=True, on_delete=models.SET_NULL)
    type = models.SmallIntegerField(_('Typ'), default=0, choices=TYPES)

    cluster = models.ForeignKey('provider.Cluster', null=True, blank=True, on_delete=models.SET_NULL)

    combine_servers = models.ManyToManyField('self', symmetrical=False, blank=True)

    keep_external_participants = models.BooleanField(_('Inkludera externa deltagare'), null=True, default=False,
                                                         help_text=_(
                                                             'Ex. övriga teamsdeltagare i Pexip gateway-'
                                                             'samtal som vanligtvis bör filtreras bort'
                                                         ))

    objects = ServerManager()

    @property
    def is_combined(self):
        return self.type == self.COMBINE

    @property
    def is_pexip(self):
        return self.type == self.PEXIP

    @property
    def is_endpoint(self):
        return self.type == self.ENDPOINTS

    @property
    def is_acano(self):
        return self.type == self.ACANO

    @property
    def is_vcs(self):
        return self.type == self.VCS

    @cached_property
    def latest_calls(self):
        """
        Return tuple with distance value to latest call, and number
        of calls within timeframe
        """
        cache_key = 'server.latest_calls.{}'.format(self.pk)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        result = self._get_latest_calls()
        cache.set(cache_key, result, 10 * 60)
        return result

    def _get_latest_calls(self):
        calls = Call.objects.filter(server=self, ts_start__gt=now() - timedelta(hours=24)).order_by(
            '-ts_start'
        )
        try:
            if calls[0].ts_start > now() - timedelta(hours=2):
                return (
                    2,
                    Call.objects.filter(
                        server=self, ts_start__gt=now() - timedelta(hours=2)
                    ).count(),
                )
        except IndexError:
            return 99, 0
        return 24, 0

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if (self.name.split() or [''])[0] == 'VCS' and self.type == 0:
            self.type = 1
        if not self.secret_key:
            self.secret_key = new_key()
        super().save(*args, **kwargs)

    def get_cdr_path(self):
        url = ''
        if self.type == self.ACANO:
            url = '/cdr/cms/{}/'.format(self.secret_key or '')
        elif self.type == self.VCS:
            url = '/cdr/vcs/{}/'.format(self.secret_key or '')
        elif self.type == self.PEXIP:
            url = '/cdr/pexip/{}/'.format(self.secret_key or '')
        return url

    def get_export_path(self, data_type: str):
        return '/cdr/csv/{}/{}/export/'.format(self.secret_key or '', data_type)

    def get_import_path(self, data_type: str):
        return '/cdr/csv/{}/{}/import/'.format(self.secret_key or '', data_type)

    def get_cdr_url(self):
        url = self.get_cdr_path()
        if not url:
            return ''
        return '{}{}'.format(settings.BASE_URL.rstrip('/'), url.replace('//', '/'))

    def clean_duplicates(self, ts_start=None, ts_stop=None):

        from statistics.utils.leg_collection import clean_duplicates
        legs = Leg.objects.filter(server=self).order_by('ts_start').select_related('call')

        if ts_stop:
            legs = legs.filter(ts_start__lte=ts_stop)
        if ts_start:
            legs = legs.filter(ts_start__gte=ts_stop)

        return clean_duplicates(self, legs, default_domain=self.default_domain)

    def acquire_lock(self, type: 'StatisticsLock.TYPES'):
        return StatisticsLock.acquire(self, type)

    @transaction.atomic
    def set_call_active(self, guid: str, node: str):
        """Mark call as active. return True if this is a new call"""
        self.acquire_lock('active_call')
        call, created = partial_update_or_create(
            ActiveCall, server=self, guid=guid, node=node, defaults={'ts_last_update': now()}
        )
        if not created:
            return False
        return ActiveCall.objects.filter(server=self, guid=guid).exclude(node=node).exists()

    @transaction.atomic
    def remove_active_call_node(self, guid: str, node: str):
        """Remove node from call list. return True if this was the last active node for the call"""
        self.acquire_lock('active_call')
        ActiveCall.objects.filter(server=self, guid=guid, node=node).delete()
        return not self.check_call_active(guid)

    def remove_active_call(self, guid: str):
        """Remove all nodes from call list. return True if call did exist"""
        count = ActiveCall.objects.filter(server=self, guid=guid).delete()
        return bool(count[0])

    def check_call_active(self, guid: str):
        return set(ActiveCall.objects.filter(server=self, guid=guid).values_list('node', flat=True))


class StatisticsLock(models.Model):
    """Separate class to lock statistics for each event type"""

    TYPES = Literal['call', 'active_call', 'server', 'tenant', 'leg']

    server = models.ForeignKey(Server, db_index=True, on_delete=models.CASCADE)
    type = models.CharField(max_length=20)

    @staticmethod
    def acquire(server: Union['Server', int], type: TYPES):
        if isinstance(server, int):
            server = Server(id=server)
        lock, created = StatisticsLock.objects.select_for_update(of=('self',)).get_or_create(
            server=server, type=type
        )
        return lock

    class Meta:
        unique_together = (('type', 'server'),)


class Tenant(models.Model):
    """Tenant id in remote system"""

    guid = models.CharField(max_length=64, db_index=True, unique=True)
    servers = models.ManyToManyField(Server, through='ServerTenant', related_name='tenants', blank=True)


class ServerTenant(models.Model):
    """Tenant which reside on a server"""

    server = models.ForeignKey(Server, db_index=False, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, db_index=False, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('server', 'tenant')


@fifo_memoize(100, ttl=10)
def _get_domain_object(domain):
    if not domain:
        return None
    return Domain.objects.get_or_create(domain=domain)[0]


class Domain(models.Model):
    """Domain of leg target"""
    domain = models.CharField('only domain', max_length=200, db_index=True, unique=True)


class CallManager(models.Manager):

    pass


class Call(models.Model):
    """Single instance of a distributed call. May have siblings on multiple nodes"""

    server = models.ForeignKey(Server, db_index=False, on_delete=models.CASCADE)
    guid = models.CharField(max_length=64, db_index=False, null=True)

    tenant = models.CharField(max_length=64, db_index=True)
    tenant_fk = models.ForeignKey(Tenant, null=True, on_delete=models.SET_NULL)
    cospace = models.CharField(max_length=300)
    cospace_id = models.CharField(max_length=100)
    ou = models.CharField(max_length=200)

    correlator_guid = models.CharField(max_length=100, null=True)

    org_unit = models.ForeignKey('organization.OrganizationUnit', null=True, db_index=False, on_delete=models.SET_NULL)
    meeting = models.ForeignKey('meeting.Meeting', db_constraint=False, null=True, blank=True, on_delete=models.SET_NULL)

    cdr_tag = models.CharField(max_length=200)

    leg_count = models.IntegerField(default=0)
    duration = models.IntegerField(default=0)
    total_duration = models.IntegerField(default=0)

    ts_start = models.DateTimeField(null=True)
    ts_stop = models.DateTimeField(null=True)
    ts_finalized = models.DateTimeField(null=True)

    should_count_stats = models.BooleanField(null=True)

    licenses_json = models.TextField(blank=True, null=True)

    pexip_history_logs = models.ManyToManyField('debuglog.PexipHistoryLog', db_constraint=False, related_name='statistics_calls')
    pexip_cdr_event_logs = models.ManyToManyField('debuglog.PexipEventLog', db_constraint=False, related_name='statistics_calls')

    acano_cdr_event_logs = models.ManyToManyField('debuglog.AcanoCDRLog', db_constraint=False, related_name='statistics_calls')

    objects = CallManager()

    class Meta:
        unique_together = ('guid', 'server')

        indexes = [
            models.Index(name='call_org_unit', fields=['org_unit'], condition=Q(org_unit__isnull=False)),
            models.Index(name='correlator_guid', fields=['correlator_guid'], condition=Q(correlator_guid__isnull=False) & ~Q(correlator_guid='')),
            models.Index(name='cospace_id', fields=['cospace_id'], condition=~Q(cospace_id='')),
            models.Index(fields=['ts_start', 'ts_stop']),
            models.Index(fields=['cospace', 'server', 'ts_start', 'ts_stop']),  # pexip
            models.Index(name='call_meeting', fields=['meeting'],
                         condition=Q(meeting__isnull=False)),
        ]

    def save(self, *args, **kwargs):

        self.load_dates()

        if self.ts_start and self.ts_stop:
            self.duration = (self.ts_stop - self.ts_start).total_seconds()

        if not self.meeting_id:
            self.populate_meeting()

        if self.cospace and len(self.cospace) > 300:
            self.cospace = self.cospace[:300]

        if self.pk:
            self.leg_count = Leg.objects.filter(call=self).count()
            if (
                not self.should_count_stats
                and Leg.objects.filter(call=self, should_count_stats=True).exists()
            ):
                self.should_count_stats = True

        if self.tenant:
            if not self.tenant_fk_id:
                self.tenant_fk = tenant_obj(self.tenant)
        tenant_server(self.tenant, self.server_id)

        super().save(*args, **kwargs)

    def load_dates(self):
        if self.ts_start and isinstance(self.ts_start, str):
            self.ts_start = parse_datetime(self.ts_start)
        if self.ts_stop and isinstance(self.ts_stop, str):
            self.ts_stop = parse_datetime(self.ts_stop)

    @property
    def licenses(self):
        return json.loads(self.licenses_json or '{}')

    @licenses.setter
    def licenses(self, value):
        if isinstance(value, str) and value.startswith('{'):
            pass
        else:
            value = json.dumps(value or {})

        self.licenses_json = value

    def get_debug_url(self):
        return reverse('stats_debug', args=('call', self.guid))

    def merge_calls(self, meeting_id_field):

        if not self.ts_start or not self.ts_stop:
            return self, []

        if not meeting_id_field:
            raise ValueError('Meeting ID field must be specified')

        IGNORE = {'AdHoc', 'adhoc'}

        if not getattr(self, meeting_id_field) or getattr(self, meeting_id_field) in IGNORE:
            return self, []

        calls = Call.objects.filter(server=self.server,
                                    ts_start__lt=self.ts_stop,
                                    ts_stop__gt=self.ts_start,
                                    **{meeting_id_field: getattr(self, meeting_id_field)}
                                    )

        with transaction.atomic():

            calls = list(calls.only('id', 'guid', 'duration', 'ts_start').select_for_update(of=('self',)))
            if len(calls) <= 1:
                return self, []

            target = sorted(calls, key=lambda x: (bool(x.guid), x.duration or 0))[-1]
            Leg.objects.filter(call__in=[c for c in calls if c != target]).update(call=target, orig_call=F('call'))

            call_list = ','.join('{} ({})'.format(call.id, call.ts_start.isoformat()) for call in calls)
            logger.info('Merged duplicate calls %s into %s for cospace %s=%s',
                        call_list, target.pk, meeting_id_field, getattr(self, meeting_id_field))

        return target, calls

    def populate_meeting(self):
        if not self.cospace_id:
            return

        if not self.ts_stop and self.ts_start < now() - timedelta(hours=4):
            return

        from meeting.models import Meeting
        matching_meeting = Meeting.objects.filter(
            ts_start__lte=self.ts_stop or now(),
            ts_stop__gte=self.ts_start,
            provider_ref2=self.cospace_id,
            provider=self.server.cluster,
            is_superseded=False,
        ).first()

        if matching_meeting:
            self.meeting = matching_meeting
        return matching_meeting

    @staticmethod
    def cdr_state_cache_key(cluster_id: int, name: str):
        return 'stats.call.{}.{}'.format(
            cluster_id or '_', hashlib.md5(name.encode('utf-8')).hexdigest()
        )

    @classmethod
    def get_cdr_state_info(cls, cluster_id: int, name: str):
        if not name:
            return {}
        return cache.get(cls.cdr_state_cache_key(cluster_id, name)) or {}

    @property
    def cdr_state_info(self):
        return self.get_cdr_state_info(self.server.cluster_id, self.cospace)

    @cdr_state_info.setter
    def cdr_state_info(self, value: dict):
        if not self.cospace:
            return
        cache_key = self.cdr_state_cache_key(self.server.cluster_id, self.cospace)
        if value is None or not isinstance(value, dict):
            cache.delete(cache_key)
            return

        cache.set(cache_key, value, 2 * 60 * 60)


class ActiveCall(models.Model):

    server = models.ForeignKey(Server, db_index=False, on_delete=models.CASCADE)
    guid = models.CharField(max_length=500)
    node = models.CharField(max_length=500)
    ts_last_update = models.DateTimeField(default=now)

    class Meta:
        unique_together = (('guid', 'node', 'server'),)


class LegManager(models.Manager):
    def aggregate_total_call_seconds_for_user(self, user_jid):
        return self.filter(target=user_jid, should_count_stats=True).aggregate(seconds=Sum('duration'))['seconds']

    def aggregate_total_call_seconds_for_users(self, user_jids: Sequence[str]):
        user_jids = set(user_jids)

        if user_jids:
            values = dict(self.filter(target__in=user_jids, should_count_stats=True).order_by().values_list('target').annotate(seconds=Sum('duration')))
        else:
            values = {}

        empty = {u: 0 for u in user_jids}

        return {**empty, **dict(values)}

    def get_first_call_date_for_user(self, user_jid):
        first_leg = self.filter(target=user_jid).order_by('ts_start').first()

        return first_leg and first_leg.ts_start

    def get_last_call_date_for_user(self, user_jid):
        last_leg = self.filter(target=user_jid).order_by('-ts_start').first()

        return last_leg and last_leg.ts_start

    def get_stats_for_users(self, domain):

        users = self.filter(target__endswith=domain).annotate(seconds=Sum('duration'), calls=Count('call')).order_by().values_list('target', 'seconds', 'calls')

        return {u[0]: u[1:] for u in users}

    def send_stat_summaries(self, urls=None):
        from provider.models.provider import Provider

        if urls is None:
            urls = getattr(settings, 'SEND_USER_STATS_URLS', ())

        if not urls:
            return

        result = {}
        for p in Provider.objects.all():
            result.update(self.get_stats_for_users(p.hostname))

        for url in urls:
            requests.post(url, json.dumps(result), timeout=120)
        return result


class LegConversation(models.Model):
    """Group of Legs"""

    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    ts_start = models.DateTimeField(default=now)
    guid = models.CharField(max_length=500)
    first_leg_guid = models.CharField(max_length=300)

    class Meta:
        unique_together = ('server', 'guid')


class Leg(models.Model):
    """Single leg of a call participant"""

    SIP = 0
    H323 = 1
    CMS = 2
    WEBRTC = 7
    LYNC = 3
    CLUSTER = 4
    STREAM = 5
    LYNC_SUB = 6
    TEAMS = 8
    GMS = 9
    SPARK = 10

    PROTOCOLS = (
        (SIP, 'SIP'),
        (H323, 'H323'),
        (CMS, 'CMS'),
        (LYNC, 'Lync'),
        (CLUSTER, 'Cluster'),
        (STREAM, 'Stream/recording'),
        (LYNC_SUB, 'Lync SubConnection'),
        (WEBRTC, 'WebRTC'),
        (TEAMS, 'Teams'),
        (GMS, 'GMS'),  # Google?
        (SPARK, 'Spark'),
    )

    objects = LegManager()

    server = models.ForeignKey(Server, related_name='legs', db_index=False, on_delete=models.CASCADE)

    call = models.ForeignKey(Call, related_name='legs', null=True, on_delete=models.CASCADE)
    orig_call = models.ForeignKey(Call, related_name='+', null=True, on_delete=models.DO_NOTHING, db_index=False, db_constraint=False)  # clustered

    tenant = models.CharField(max_length=64)
    tenant_fk = models.ForeignKey(Tenant, db_index=False, null=True, on_delete=models.SET_NULL)

    guid = models.CharField(max_length=128, blank=True, null=True)
    guid2 = models.CharField(max_length=128, null=True)  # history id in pexip

    conversation = models.ForeignKey(LegConversation, db_constraint=False, null=True, db_index=False, on_delete=models.DO_NOTHING)

    name = models.CharField(max_length=300)

    protocol = models.SmallIntegerField(choices=PROTOCOLS, null=True)

    should_count_stats = models.BooleanField(default=True)

    direction = models.CharField(max_length=20)

    remote = models.CharField(max_length=300)
    local = models.CharField(max_length=300)
    target = models.CharField(max_length=300)
    domain = models.ForeignKey('Domain', db_constraint=False, null=True, blank=True, on_delete=models.DO_NOTHING)

    endpoint = models.ForeignKey('endpoint.Endpoint', db_constraint=False, db_index=False, null=True, blank=True, on_delete=models.DO_NOTHING)

    ts_start = models.DateTimeField(null=True)
    ts_stop = models.DateTimeField(null=True)

    duration = models.IntegerField(default=0)

    head_count = models.IntegerField(null=True, blank=True)
    air_quality = models.SmallIntegerField(null=True, blank=True)
    presence = models.BooleanField(null=True)

    is_guest = models.BooleanField(default=False)
    ou = models.CharField(max_length=200)

    org_unit = models.ForeignKey('organization.OrganizationUnit', null=True, db_index=False, on_delete=models.SET_NULL)

    tx_pixels = models.IntegerField(null=True)
    rx_pixels = models.IntegerField(null=True)
    bandwidth = models.IntegerField(null=True)

    packetloss_percent = models.SmallIntegerField(null=True)
    jitter_percent = models.SmallIntegerField(null=True)
    high_roundtrip_percent = models.SmallIntegerField(null=True)

    jitter = models.SmallIntegerField(null=True)
    jitter_peak = models.SmallIntegerField(null=True)

    role = models.CharField(max_length=100, null=True)
    service_type = models.CharField(max_length=100, null=True)

    license_count = models.SmallIntegerField(null=True)
    license_type = models.CharField(max_length=100, null=True)

    contribution_percent = models.SmallIntegerField(null=True)
    presentation_contribution_percent = models.SmallIntegerField(null=True)
    viewer_percent = models.SmallIntegerField(null=True)

    pexip_history_logs = models.ManyToManyField('debuglog.PexipHistoryLog', db_constraint=False, related_name='statistics_legs')
    pexip_cdr_event_logs = models.ManyToManyField('debuglog.PexipEventLog', db_constraint=False, related_name='statistics_legs')

    acano_cdr_event_logs = models.ManyToManyField('debuglog.AcanoCDRLog', db_constraint=False, related_name='statistics_legs')

    def save(self, *args, **kwargs):

        if not self.domain_id and self.target and '@' in self.target:
            from .parser.utils import get_domain
            self.domain = _get_domain_object(get_domain(self.target))

        self.load_dates()
        if self.ts_start and self.ts_stop:
            self.duration = (self.ts_stop - self.ts_start).total_seconds()

        self.populate_head_count()
        self.populate_air_quality()
        self.populate_presence()
        self.update_endpoint_meeting_stats()

        if self.ts_stop and self.duration < 60:
            self.should_count_stats = False

        if self.should_count_stats and self.call_id:
            partial_update(self.call, {'should_count_stats': True})

        if self.tenant:
            if not self.tenant_fk_id:
                self.tenant_fk = tenant_obj(self.tenant)
        tenant_server(self.tenant, self.server_id)

        super().save(*args, **kwargs)

    def populate_head_count(self):
        if not self.endpoint_id or not self.ts_start:
            return

        from room_analytics.models import EndpointHeadCount

        new_head_count = EndpointHeadCount.objects.get_for_time(self.endpoint, self.ts_start, self.ts_stop or now())
        if new_head_count is not None:
            self.head_count = new_head_count
            return new_head_count

    def populate_air_quality(self):
        if not self.endpoint_id or not self.ts_start:
            return

        from room_analytics.models import EndpointAirQuality

        new_air_quality = EndpointAirQuality.objects.get_for_time(
            self.endpoint, self.ts_start, self.ts_stop or now()
        )
        if new_air_quality is not None:
            self.air_quality = new_air_quality
            return new_air_quality

    def populate_presence(self):
        if not self.endpoint_id or not self.ts_start:
            return

        from room_analytics.models import EndpointRoomPresence

        presence = EndpointRoomPresence.objects.get_for_time(self.endpoint, self.ts_start, self.ts_stop or now())
        if presence is not None:
            self.presence = presence
            return presence

    def update_endpoint_meeting_stats(self):

        if not self.head_count or not self.presence:
            return

        if not self.endpoint_id or not self.call_id or not self.call.meeting_id:
            return

        from endpoint.models import EndpointMeetingParticipant
        EndpointMeetingParticipant.objects \
            .filter(endpoint=self.endpoint, meeting=self.call.meeting_id) \
            .update(
                ts_connected=Coalesce(F('ts_connected'), self.ts_start),
                head_count=self.head_count,
                presence=self.presence,
            )

    @staticmethod
    def cdr_state_cache_key(cluster_id: int, guid: str):
        return 'stats.leg.{}.{}'.format(cluster_id or '_', guid)

    @classmethod
    def get_cdr_state_info(cls, cluster_id: int, guid: str):
        if not guid:
            return {}
        return cache.get(cls.cdr_state_cache_key(cluster_id, guid)) or {}

    @property
    def cdr_state_info(self):
        guid = self.guid2 or self.guid  # TODO Temp Pexip ID-fix
        return self.get_cdr_state_info(self.server.cluster_id, guid)

    @cdr_state_info.setter
    def cdr_state_info(self, value: dict):
        if not self.guid:
            return
        guid = self.guid2 or self.guid  # TODO Temp Pexip ID-fix
        cache_key = self.cdr_state_cache_key(self.server.cluster_id, guid)
        if value is None or not isinstance(value, dict):
            cache.delete(cache_key)
            return

        cache.set(cache_key, value, 2 * 60 * 60)

    @property
    def protocol_str(self):
        return dict(self.PROTOCOLS).get(self.protocol, '')

    def load_dates(self):
        if self.ts_start and isinstance(self.ts_start, str):
            self.ts_start = parse_datetime(self.ts_start)
        if self.ts_stop and isinstance(self.ts_stop, str):
            self.ts_stop = parse_datetime(self.ts_stop)

    class Meta:
        # # TODO (only for ActiveLeg when splitting to Leg and ActiveLeg)
        # unique_together = ('guid', 'server)
        ordering = ('ts_start',)

        # TODO add ts_start to most indexes when starting to use timescale
        indexes = [
            models.Index(fields=['target']),  # no need for like index with db_index=True
            models.Index(fields=['guid', 'server']),  # acano/pexip
            models.Index(
                name='leg_server_tenant',
                fields=['server', 'tenant'],
                condition=Q(should_count_stats=True),
            ),  # report
            *(
                [
                    BrinIndex(
                        name="leg_times",
                        fields=["ts_start", "ts_stop"],
                        autosummarize=True,
                    )
                ]
                if settings.IS_POSTGRES
                else []
            ),
            models.Index(name='leg_guid2', fields=['guid2', 'server'],
                         condition=Q(guid2__isnull=False) & ~Q(guid2='')),
            models.Index(name='leg_endpoint', fields=['endpoint'],
                         condition=Q(endpoint__isnull=False)),
            models.Index(name='leg_conversation', fields=['conversation'],
                         condition=Q(conversation__isnull=False)),
            models.Index(name='org_unit', fields=['org_unit'],
                         condition=Q(org_unit__isnull=False)),
        ]

    def get_debug_url(self):
        return reverse('stats_debug', args=('leg', self.guid))

    def to_leg_data(self):
        from statistics.types import LegData

        return LegData(self.id, self.ts_start, self.ts_stop,
                       self.duration, self.target, self.tenant, self.ou, self.call.cospace_id,
                       self.guid, self.call.cospace, self.call_id, self.is_guest, self.org_unit_id, self.local,
                       self.remote, *LegData.non_db_values())


class PossibleSpamLeg(models.Model):
    """Acano leg which probably is port scanner. Separate from real data"""

    server = models.ForeignKey(Server, on_delete=models.CASCADE, db_index=False, db_constraint=False)
    guid = models.CharField(max_length=200)
    ts_start = models.DateTimeField()
    data_json = models.TextField()


class InvalidCallStats(models.Model):
    """Statistics of removed acano spam legs"""

    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    day = models.DateField()
    unknown_destination = models.IntegerField(default=0)
    other = models.IntegerField(default=0)

    class Meta:
        unique_together = ('server', 'day')


class DayStat(models.Model):
    """Aggregated statistics"""
    # FIXME not used

    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    day = models.DateField()
    ou = models.CharField(max_length=200, db_index=True)

    calls = models.IntegerField()
    users = models.IntegerField()
    max_users = models.IntegerField()

    minutes = models.IntegerField()


class DomainTransform(models.Model):
    """
    Rewrite domains of call legs (e.g. VCS default domain/ip for internal calls) and connect to ou/org unit
    """

    domain = models.CharField(_('Domän'), max_length=30)
    ou = models.CharField(_('OU-grupp i AD'), max_length=30, blank=True)
    org_unit = models.ForeignKey('organization.OrganizationUnit', verbose_name=_('Organisationsenhet'), null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return '%s - %s' % (self.domain, self.ou)


class DomainRewrite(models.Model):
    """
    Rewrite alias_domain to self.transform.domain
    """

    transform = models.ForeignKey(DomainTransform, null=True, blank=True, on_delete=models.CASCADE)
    alias_domain = models.CharField(_('Domän som ska skrivas om'), max_length=200)

    def __str__(self):
        return self.alias_domain

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('stats.internal_domains')


def clear_cache(sender=None, *args, **kwargs):

    _get_domain_object.cache.clear()
    tenant_obj.cache.clear()
