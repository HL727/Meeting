import uuid
from collections import defaultdict, Counter, namedtuple
from datetime import timedelta
from enum import IntEnum
from time import sleep
from typing import Union, Dict, List, Tuple
from urllib.parse import urlunparse, urlparse, parse_qs, urlencode

from django.db.models import UniqueConstraint, Q
from django.utils.translation import gettext_lazy as _

from cacheout import fifo_memoize
from django.conf import settings
from django.db import models, transaction, IntegrityError
from django.utils.timezone import now
from jsonfield import JSONField

from compressed_store.models import FastCountManager
from customer.models import Customer, validate_regexp
import logging

from shared.utils import maybe_update, get_changed_fields, partial_update_or_create

logger = logging.getLogger(__name__)


def default_date():

    return (now() - timedelta(days=60)).replace(day=1).date()


def new_key():
    try:
        import secrets
        return secrets.token_urlsafe(20)
    except ImportError:
        return str(uuid.uuid4())


class ClusterPolicy(models.Model):

    IGNORE = 0
    LOG = 5
    AUDIO_ONLY = 20
    QUALITY_SD = 30
    QUALITY_720P = 35
    REJECT = 100

    ACTIONS = (
        (IGNORE, 'Ignore'),
        (LOG, 'Log'),
        (AUDIO_ONLY, 'Limit to audio only'),
        (QUALITY_SD, 'Lower quality to SD'),
        (QUALITY_720P, 'Lower quality to 720p'),
        (REJECT, 'Reject'),
    )

    cluster = models.ForeignKey('provider.Cluster', null=True, on_delete=models.CASCADE)
    soft_limit_action = models.SmallIntegerField(choices=ACTIONS, default=0)
    hard_limit_action = models.SmallIntegerField(choices=ACTIONS, default=0)

    enable_gateway_rules = models.BooleanField(
        _('Applicera gateway-regler'),
        default=False,
        blank=True,
        help_text=_('Annars räknas bara träffar'),
    )

    secret_key = models.CharField(max_length=64, default=new_key, editable=False)

    def get_absolute_url(self):
        return 'https://{}/cdr/policy/{}/'.format(settings.HOSTNAME, self.secret_key)

    @property
    def external_policies(self):
        return self.get_external_policies(self.pk)

    # @lru
    @staticmethod
    def get_external_policies(cluster_policy_id):
        return ExternalPolicy.objects.filter(policy=cluster_policy_id)

    @staticmethod
    def get_policy_scripts(cluster_id: int):
        from policy_script.models import get_cluster_policy_scripts

        return get_cluster_policy_scripts(cluster_id)


class ExternalPolicy(models.Model):

    policy = models.ForeignKey(ClusterPolicy, on_delete=models.CASCADE)
    target_alias_match = models.CharField(
        _('Alias regexp-matchning'),
        max_length=500,
        blank=True,
        validators=[validate_regexp],
        help_text=_('Matchar från start (implicit ^)'),
    )

    priority = models.SmallIntegerField(default=5)

    remote_url = models.URLField(_('Fråga ytterligare extern policy server'), help_text=_('3 sek timeout'), blank=True)

    settings_override = JSONField(_('Override för rumsinställningar'), blank=True,
                                  help_text='Ändra inställningar för videomöte om ett svar med "result" kommer tillbaka')

    def build_request_url(self, params):
        parts = urlparse(self.remote_url)

        query = parse_qs(parts.query) if parts.query else {}

        parts_with_new_query = parts._replace(query=urlencode({**query, **params}, doseq=True))

        return urlunparse(parts_with_new_query)


class CustomerPolicyManager(models.Manager):

    def get_active(self, customer) -> 'CustomerPolicy':
        return CustomerPolicyManager._customer_active_policy(getattr(customer, 'pk', customer))

    @staticmethod
    @fifo_memoize(maxsize=200, ttl=5)
    def _customer_active_policy(customer_id):
        return CustomerPolicy.objects.filter(customer=customer_id,
                                             date_start__lte=now().date()) \
            .order_by('-date_start').first()


class CustomerPolicy(models.Model):

    OK = 0
    SOFT_LIMIT = 10
    HARD_LIMIT = 20

    ACTIONS = (
        (-1, _('Standardvärde')),
        (ClusterPolicy.IGNORE, 'Ignore'),
        (ClusterPolicy.LOG, 'Log'),
        (ClusterPolicy.REJECT, 'Reject'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    participant_limit = models.PositiveIntegerField(_('Total'), null=True, blank=True, editable=False)

    participant_normal_limit = models.PositiveIntegerField(null=True, blank=True)
    participant_gateway_limit = models.PositiveIntegerField(null=True, blank=True)
    participant_hard_limit = models.PositiveIntegerField(null=True, blank=True)

    date_start = models.DateField(_('Gäller fr.o.m.'), default=default_date)

    soft_limit_action = models.SmallIntegerField(choices=ACTIONS, default=-1)
    hard_limit_action = models.SmallIntegerField(choices=ACTIONS, default=-1)

    objects = CustomerPolicyManager()

    class Meta:
        unique_together = ('customer', 'date_start')

    def check_participant_count(self, participant_count):
        if self.participant_hard_limit and participant_count >= self.participant_hard_limit:
            return CustomerPolicyState.HARD_LIMIT
        if self.participant_limit and participant_count >= self.participant_limit:
            return CustomerPolicyState.SOFT_LIMIT
        return CustomerPolicyState.OK

    def __str__(self):
        return str(self.customer)

    def save(self, *args, **kwargs):
        self.participant_limit = max((self.participant_normal_limit or 0), (self.participant_gateway_limit or 0) * 2)
        super().save(*args, **kwargs)

    def get_state(self, cluster):
        return CustomerPolicyState.objects.filter(cluster=cluster, customer=self.customer).first()

    def get_status(self, cluster):
        state = self.get_state(cluster)
        return state.participant_status if state else CustomerPolicyState.OK


class CustomerPolicyStateManager(models.Manager) :

    def _change_counter(self, customer, cluster=None, active_calls=0, active_participants=0,
                       gateway=False):
        with transaction.atomic():
            state, created = CustomerPolicyState.objects \
                .select_for_update(of=('self',)) \
                .get_or_create(customer=customer,
                               cluster=cluster,
                               defaults=dict(
                                   active_calls=max(0, active_calls or 0),
                                   active_participants=max(0, active_participants or 0),
                                   active_participants_gateway=max(0, active_participants if gateway else 0),
                               ))
            if not created:
                if active_calls:
                    state.active_calls += active_calls
                if active_participants:
                    state.active_participants += active_participants
                    if gateway:
                        state.active_participants_gateway += active_participants
                state.save()
        return state

    def find_policy_customer(
        self,
        customer=None,
        acano_tenant_id=None,
        pexip_tenant_id=None,
        cluster=None,
        tenant_id=None,
    ):
        """
        Find customer for policy state. Probably deprecated and just a wrapper for ordinary
        Customer.objects.find_customer now days
        """
        if customer:
            return customer
        if cluster and tenant_id is not None:
            if cluster.is_acano:
                acano_tenant_id = tenant_id
            elif cluster.is_pexip:
                pexip_tenant_id = tenant_id

        return Customer.objects.find_customer(
            acano_tenant_id=acano_tenant_id, pexip_tenant_id=pexip_tenant_id, cluster=cluster
        )

    def change_calls(self, change=1, customer=None, gateway=False, cluster=None, acano_tenant_id=None, pexip_tenant_id=None,
                     name=None, fallback=False, source=None):
        customer = self.find_policy_customer(customer, acano_tenant_id, pexip_tenant_id, cluster)

        def _warn(*args):
            return self._warn(*args, guid=name, type='call', cluster=cluster, source=source)

        def _commit():
            state = self._change_counter(customer, cluster=cluster, active_calls=change, gateway=gateway)
            self._info('Add %s calls for name %s, preliminary customer %s, cluster=%s',
                       change, name or '', customer, cluster,
                       type=PolicyLog.CALL, customer=customer, guid=name, cluster=cluster, source=source)
            return state

        state = None

        if change and not name:
            _warn(
                'Try to change call but no name was provided. Customer %s', customer)

        if change > 0 and name:
            cur, created = partial_update_or_create(ActiveCall.direct_objects, cluster=cluster, name=name, defaults={'customer': customer})

            if created:
                state = _commit()
            elif not fallback:
                _warn('Call with name %s already in active list for customer %s. Created %s (%s ago)',
                      name, customer, cur.ts_created, now() - cur.ts_created)

            if fallback and created:
                _warn('Added call %s for customer %s after the fact. Missing live event?', name, customer)

        elif change < 0 and name:
            count = ActiveCall.direct_objects.filter(cluster=cluster, customer=customer, name=name).delete()[0]

            if count:
                state = _commit()

            if fallback and count:
                _warn(
                    'Deleted call %s for customer %s after the fact. Missing live event?',
                    name,
                    customer,
                )
                return state

            if not count:
                other = ActiveCall.direct_objects.filter(cluster=cluster, name=name).select_related('customer').first()
                if other:
                    _warn('Call %s active for other customer %s', name, other.customer)
                    return self.change_calls(
                        change=change,
                        customer=other.customer,
                        gateway=gateway,
                        cluster=cluster,
                        name=name,
                        fallback=fallback,
                        source=source,
                    )
                elif not fallback:
                    _warn(
                        'Could not delete active call with name %s for customer %s', name, customer
                    )

        return state

    def change_participants(self, change=1, gateway=False, customer=None, cluster=None,
                            acano_tenant_id=None, pexip_tenant_id=None, guid=None, name=None,
                            ignore_change=False, fallback=False, source=None):

        customer = self.find_policy_customer(customer, acano_tenant_id, pexip_tenant_id, cluster)

        def _warn(*args):
            return self._warn(*args, guid=guid, name=name, type='participant', cluster=cluster, source=source)

        def _commit():
            state = self._change_counter(customer, cluster=cluster, active_participants=change, gateway=gateway)
            if change:
                self._info('Add %s participants (new count %s) with guid %s (%s) for customer %s, gateway=%s',
                           change, state.active_participants if state else None, guid, name or '', customer, gateway,
                           type=PolicyLog.PARTICIPANT, customer=customer, guid=guid, cluster=cluster, source=source)
            return state

        if ignore_change:  # e.g. duplicate call, secondary leg in audio + video + chat etc
            existing = ActiveParticipant.objects.filter(cluster=cluster, guid=guid).first()
            if change > 0 and not existing:
                self._warn('Ignore increase for %s (%s), customer %s, but none exists', guid, name, customer,
                           type='participant', guid=guid, name=name, cluster=cluster, source=source)
            elif change > 0:
                self._info('Ignore increase for %s (%s), customer %s', guid, name, customer,
                           type='participant', guid=guid, name=name, cluster=cluster, source=source)
            else:
                self._info('Ignore decrease for %s (%s), customer %s', guid, name, customer,
                           type='participant', guid=guid, name=name, cluster=cluster, source=source)
            return

        state = None

        if not guid:
            _warn(
                'Try to change participant %s but no guid was provided. Customer %s, gateway=%s',
                name, customer, bool(gateway))

        if change > 0 and guid:
            cur, created = ActiveParticipant.direct_objects.get_or_create(cluster=cluster, guid=guid,
                                                                   defaults={'customer': customer, 'name': name or '', 'is_gateway': gateway})

            if created:
                state = _commit()

            if fallback:
                if created:
                    _warn('Added participant %s (%s) for customer %s after the fact. Missing live event?',
                          guid, name, customer)
                return state

            if not created:
                _warn('Participant with guid %s (%s) already in active list for customer %s. Gateway status %s. Created %s (%s ago)',
                            guid, name, customer, cur.is_gateway == bool(gateway), cur.ts_created, now() - cur.ts_created)
                self.update_participant(customer=customer, cluster=cluster, guid=guid, gateway=gateway)

        elif change < 0 and guid:
            count = ActiveParticipant.direct_objects.filter(cluster=cluster, customer=customer, guid=guid, is_gateway=bool(gateway)).delete()[0]

            if count:
                state = _commit()

            if fallback and count:
                _warn(
                    'Deleted participant %s (%s) for customer %s after the fact. Missing live event?',
                    guid,
                    name,
                    customer,
                )

            if not count:
                other = ActiveParticipant.direct_objects.filter(cluster=cluster, guid=guid).first()
                if other:
                    _warn(
                        'Participant %s (%s) active for other customer %s. Gateway == %s (this %s)',
                        guid,
                        name,
                        other.customer,
                        other.is_gateway,
                        bool(gateway),
                    )
                    return self.change_participants(
                        change=change,
                        gateway=other.is_gateway,
                        customer=other.customer,
                        cluster=cluster,
                        guid=guid,
                        name=name,
                        ignore_change=ignore_change,
                        fallback=fallback,
                        source=source,
                    )
                elif not fallback:
                    _warn('Could not delete active participant with guid %s (%s) for customer %s', guid, name, customer)

        return state

    @transaction.atomic()
    def update_call(self, customer=None, cluster=None, acano_tenant_id=None, pexip_tenant_id=None, name=None, source=None):
        customer = self.find_policy_customer(customer, acano_tenant_id, pexip_tenant_id, cluster)

        try:
            existing = ActiveCall.objects.select_for_update(of=('self',))\
                .exclude(customer=customer)\
                .get(cluster=cluster, name=name)
        except ActiveCall.DoesNotExist:
            return

        self._info('Change call %s from customer %s to %s', name, existing.customer, customer, guid=name, cluster=cluster, source=source)
        self.change_calls(-1, cluster=cluster,  name=name, customer=existing.customer, source=source)
        self.change_calls(1, cluster=cluster, name=name, customer=customer, source=source)

        return existing

    @transaction.atomic()
    def update_participant(self, gateway=False, customer=None, cluster=None,
                            acano_tenant_id=None, pexip_tenant_id=None, guid=None, name=None, source=None):

        customer = self.find_policy_customer(customer, acano_tenant_id, pexip_tenant_id, cluster)

        try:
            existing = ActiveParticipant.objects.select_for_update(of=('self',))\
                .exclude(customer=customer, is_gateway=gateway)\
                .get(cluster=cluster, guid=guid)
        except ActiveParticipant.DoesNotExist:
            return

        self._info('Change participant %s from customer %s to %s, gateway=%s', guid, existing.customer, customer, gateway, cluster=cluster, source=source)
        self.change_participants(-1, cluster=cluster, guid=guid, customer=existing.customer, gateway=existing.is_gateway, source=source)
        self.change_participants(1, cluster=cluster, guid=guid, customer=customer, gateway=gateway, source=source)

        return existing

    def _warn(self, message, *args, type=None, guid=None, name=None, customer=None, cluster=None, source=None):
        logger.warning(message, *args)
        PolicyLog.objects.create(message=message % args, guid=guid or name or '',
                                 type=PolicyLog.PARTICIPANT or 0, level=3, customer=customer, cluster=cluster,
                                 source=PolicyLog.PolicyLogSource.lookup(source))

    def _info(self, message, *args, type=None, guid=None, name=None, customer=None, cluster=None, source=None):
        if cluster:
            message += ', cluster=%s'
            args += (cluster,)
        if source:
            message += ', source=%s'
            args += (source,)
        logger.info(message, *args)
        PolicyLog.objects.create(message=message % args, guid=guid or name or '',
                                 type=PolicyLog.PARTICIPANT or 0, level=2, customer=customer, cluster=cluster,
                                 source=PolicyLog.PolicyLogSource.lookup(source))

    def recheck(self, commit=True):

        from provider.models.provider import Cluster

        all_changes = {}

        for cluster in Cluster.objects.distinct().filter(customerpolicystate__isnull=False):
            cur_changes = self.rebuild_cluster_counts(cluster, commit=commit)
            all_changes.update(cur_changes)

        return all_changes

    def get_remote_state(self, cluster):
        """
        Try to get all participants and calls from cluster.
        Grouping by participant (instead of each leg) is not supported by acano
        """
        calls_count = defaultdict(set)
        participant_count = Counter()
        participant_gateway_count = Counter()

        customer = Customer.objects.all().first()

        active_list = defaultdict(dict)

        conversations = set()

        participants: List[Dict] = []

        for p in cluster.get_api(customer).get_clustered_call_legs():
            tenant_id = p.get('tenant') or None

            call_id = p['conference'] if cluster.is_pexip else p['call']
            calls_count[tenant_id].add(call_id)

            if p.get('service_type') in ('ivr', 'two_stage_dialing'):
                continue

            if cluster.is_pexip and not p.get('connect_time'):
                continue

            participants.append(p)

            conversation_id = p.get('conversation_id') or p.get('call_uuid') or p['id']
            if conversation_id in conversations:  # unique leg of participant. not supported in acano
                continue
            conversations.add(conversation_id)

            participant_count[tenant_id] += 1

            if p.get('service_type') == 'gateway':
                participant_gateway_count[tenant_id] += 1

            active_list[tenant_id][(conversation_id, p.get('service_type') == 'gateway')] = p.get('display_name') or p.get('name') or ''

        result = {}

        for tenant_id in set(calls_count).union(participant_count).union(participant_gateway_count).union(active_list):
            result[tenant_id] = {
                'active_participants': participant_count.get(tenant_id, 0),
                'active_participants_gateway': participant_gateway_count.get(tenant_id, 0),
                'active_calls': len(calls_count.get(tenant_id, ())),

                'participant_list': active_list.get(tenant_id, {}),
                'call_list': set(calls_count.get(tenant_id, ())),
            }

        return result, participants

    class LocalState:
        def __init__(self, participant_list: Dict[str, Dict[Tuple[str, bool], str]], call_list: Dict[str, set]):
            self.participant_list = participant_list
            self.call_list = call_list

    def get_local_state(self, cluster):

        if cluster and cluster.is_pexip:
            tenant_field = 'customer__pexip_tenant_id'
        else:
            tenant_field = 'customer__acano_tenant_id'

        participant_list = defaultdict(dict)
        call_list = defaultdict(set)

        for tenant, guid, gateway, name in ActiveParticipant.objects.filter(cluster=cluster).values_list(tenant_field, 'guid', 'is_gateway', 'name'):
            cur = (guid, gateway)
            participant_list[tenant or None][cur] = name

        for tenant, name in ActiveCall.objects.filter(cluster=cluster).values_list(tenant_field, 'name'):
            call_list[tenant or None].add(name)

        return self.LocalState(participant_list, call_list)

    TenantDiff = namedtuple('TenantDiff', 'calls participants')
    Diff = namedtuple('Diff', 'extra_local extra_remote')

    def compare_cluster_state(self, cluster, delay=2):
        """
        Take snapshot of local state, fetch remote state and take a new local snapshot.
        Compare the three states to calculate the difference
        """
        local_state_initial = self.get_local_state(cluster)  # take snapshot before asking server
        cluster_state, cluster_participants = self.get_remote_state(cluster)

        if delay and not settings.TEST_MODE:  # give new events time to be processed
            sleep(delay)

        local_state_after = self.get_local_state(cluster)  # new snapshot after asking server

        result = defaultdict(lambda: self.TenantDiff(self.Diff([], []), self.Diff([], [])))

        # participants
        for tenant_id, values in cluster_state.items():

            remote_participants = set(values['participant_list'].keys())
            local_participants = set(local_state_initial.participant_list[tenant_id].keys())

            local_participants_after = set(local_state_after.participant_list[tenant_id].keys())

            if remote_participants != local_participants:
                extra_local = local_participants - remote_participants
                if extra_local:  # remove legs hungup after api calls
                    extra_local &= local_participants_after

                if extra_local:
                    result[tenant_id].participants.extra_local.extend(extra_local)
                    logger.warning('Extra local participants for tenant %s: %s', tenant_id,
                                   str(extra_local))

                extra_remote = remote_participants - local_participants
                if extra_remote:  # remove legs created after api calls
                    extra_remote -= local_participants_after

                if extra_remote:
                    result[tenant_id].participants.extra_remote.extend(extra_remote)
                    logger.warning('Missing remote participants for tenant %s: %s', tenant_id,
                                   str(extra_remote))

        # calls
        for tenant_id, values in cluster_state.items():
            remote_calls = values['call_list']
            local_calls = local_state_initial.call_list[tenant_id]

            local_calls_after = local_state_after.call_list[tenant_id]

            if remote_calls != local_calls:
                extra_local = local_calls - remote_calls
                if extra_local:  # remove calls hungup after api calls
                    extra_local &= local_calls_after

                if extra_local:
                    result[tenant_id].calls.extra_local.extend(extra_local)
                    logger.warning('Extra local calls for tenant %s: %s', tenant_id,
                                   str(extra_local))
                extra_remote = remote_calls - local_calls

                if extra_remote:  # remove calls created after api calls
                    extra_remote -= local_calls_after

                if extra_remote:
                    result[tenant_id].calls.extra_remote.extend(extra_remote)
                    logger.warning('Missing remote calls for tenant %s: %s', tenant_id,
                                   str(extra_remote))

        # tenants only present in local state
        for tenant_id in set(local_state_initial.participant_list.keys()).union(local_state_initial.call_list.keys()):

            if tenant_id in cluster_state:
                continue

            if not (local_state_after.participant_list.get(tenant_id) or local_state_after.call_list[tenant_id]):
                continue

            if local_state_initial.participant_list.get(tenant_id) and local_state_after.participant_list.get(tenant_id):
                result[tenant_id].participants.extra_local.extend(set(local_state_initial.participant_list[tenant_id].keys()))
                logger.warning('Extra local participant for missing tenant %s: %s', tenant_id, str(result[tenant_id].participants[0]))

            if local_state_initial.call_list.get(tenant_id) and local_state_after.call_list.get(tenant_id):
                result[tenant_id].calls.extra_local.extend(local_state_initial.call_list[tenant_id])
                logger.warning('Extra local calls for missing tenant %s: %s', tenant_id, str(result[tenant_id].calls[0]))

        return dict(result), cluster_participants

    def pretty_print_state_diff(self, cluster, result):
        customers = {c.acano_tenant_id: c for c in Customer.objects.all() if c.acano_tenant_id}
        customers.update({c.pexip_tenant_id: c for c in Customer.objects.all() if c.pexip_tenant_id})

        from pprint import pprint

        for tenant_id, values in result.items():
            customer = self.find_policy_customer(
                customers.get(tenant_id), cluster=cluster, tenant_id=tenant_id
            )
            print('Diff for customer {}'.format(customer or tenant_id or '-- default --'))
            if values.participants.extra_local:
                print('Extra local participants:')
                pprint(values.participants.extra_local)
            if values.participants.extra_remote:
                print('Missing remote participants:')
                pprint(values.participants.extra_remote)
            if values.calls.extra_local:
                print('Extra local calls:')
                pprint(values.calls.extra_local)
            if values.calls.extra_remote:
                print('Missing remote calls:')
                pprint(values.calls.extra_remote)

    def remove_disconnected(self, cluster, cluster_diff):
        customers = {c.acano_tenant_id: c for c in Customer.objects.all() if c.acano_tenant_id}
        customers.update({c.pexip_tenant_id: c for c in Customer.objects.all() if c.pexip_tenant_id})

        local_state = self.get_local_state(cluster)

        assert sum(1 for x in ['', 'null', None] if x in cluster_diff) <= 1

        if 'null' in cluster_diff:  # None key json-serialized becomes string null
            cluster_diff[None] = cluster_diff.pop('null')

        # may receive war list/tuples instead of Diff/TenantDiff
        for tenant_id in list(cluster_diff.keys()):
            values = cluster_diff.pop(tenant_id)
            cluster_diff[tenant_id or None] = self.TenantDiff(self.Diff(*values[0]), self.Diff(*values[1]))

        wrong_tenant_participants = {guid: tenant for tenant, tenant_diff in cluster_diff.items() for guid, gateway in tenant_diff.participants.extra_remote}
        wrong_tenant_calls = {name: tenant for tenant, tenant_diff in cluster_diff.items() for name in tenant_diff.calls.extra_remote}

        for tenant_id, tenant_diff in cluster_diff.items():
            customer = self.find_policy_customer(
                customers.get(tenant_id), cluster=cluster, tenant_id=tenant_id
            )

            for participant in tenant_diff.participants.extra_local:
                if tuple(participant) in local_state.participant_list.get(tenant_id, {}):
                    guid, gateway = participant
                    if guid not in wrong_tenant_participants:
                        CustomerPolicyState.objects.change_participants(-1, cluster=cluster, guid=guid, gateway=gateway, customer=customer, fallback=True, source='disconnected_check')

            for name in tenant_diff.calls.extra_local:
                if name in local_state.call_list.get(tenant_id, set()):
                    if name not in wrong_tenant_calls:
                        if CustomerPolicyState.objects.change_calls(
                            -1,
                            cluster=cluster,
                            name=name,
                            customer=customer,
                            fallback=True,
                            source='disconnected_check',
                        ):

                            if name and cluster.is_pexip:  # TODO move call reset som other place
                                from statistics.models import Call

                                server = cluster.get_statistics_server()

                                server.remove_active_call(name)
                                Call.objects.filter(
                                    server=server,
                                    ts_start__gt=now() - timedelta(hours=4),
                                    ts_start__lt=now() - timedelta(minutes=10),
                                    ts_stop__isnull=True,
                                    cospace=name,
                                ).update(ts_stop=now())

    def add_missing(self, cluster, cluster_diff):
        customers = {c.acano_tenant_id: c for c in Customer.objects.all() if c.acano_tenant_id}
        customers.update({c.pexip_tenant_id: c for c in Customer.objects.all() if c.pexip_tenant_id})

        local_state = self.get_local_state(cluster)

        assert sum(1 for x in ['', 'null', None] if x in cluster_diff) <= 1

        if 'null' in cluster_diff:  # None key json-serialized becomes string null
            cluster_diff[None] = cluster_diff.pop('null')

        # may receive war list/tuples instead of Diff/TenantDiff
        for tenant in list(cluster_diff.keys()):
            values = cluster_diff.pop(tenant)
            cluster_diff[tenant or None] = self.TenantDiff(self.Diff(*values[0]), self.Diff(*values[1]))

        wrong_tenant_participant = {guid: tenant_id for tenant_id, tenant_diff in cluster_diff.items() for guid, gateway in tenant_diff.participants.extra_local}
        wrong_tenant_calls = {name: tenant_id for tenant_id, tenant_diff in cluster_diff.items() for name in tenant_diff.calls.extra_local}

        for tenant_id, tenant_diff in cluster_diff.items():
            customer = customers.get(tenant_id or '')
            for guid, gateway in tenant_diff.participants.extra_remote:
                if not local_state.participant_list.get(tenant_id, {}).get((guid, gateway)):
                    if guid not in wrong_tenant_participant:
                        CustomerPolicyState.objects.change_participants(1, cluster=cluster, guid=guid, gateway=gateway, customer=customer, fallback=True, source='connect_check')
            for name in tenant_diff.calls.extra_remote:
                if name not in local_state.call_list.get(tenant_id, set()):
                    if name not in wrong_tenant_calls:
                        CustomerPolicyState.objects.change_calls(1, cluster=cluster, name=name, customer=customer, fallback=True, source='connect_check')

    def rebuild_cluster_counts(self, cluster, commit=True):

        state_changes = {}
        with transaction.atomic():
            states = CustomerPolicyState.objects.filter(cluster=cluster)
            if commit:
                states = states.select_for_update(of=('self',))

            for state in states:
                cur = {
                    'active_calls': ActiveCall.objects.filter(cluster=cluster, customer=state.customer).count(),
                    'active_participants': ActiveParticipant.objects.filter(cluster=cluster, customer=state.customer).count(),
                    'active_participants_gateway': ActiveParticipant.objects.filter(cluster=cluster, customer=state.customer, is_gateway=True).count(),
                }
                changes = {k: (getattr(state, k), cur[k]) for k in get_changed_fields(state, cur)}
                if commit:
                    maybe_update(state, cur)

                if changes:
                    state_changes[state.pk] = changes

        return state_changes


class CustomerPolicyState(models.Model):

    OK = 0
    SOFT_LIMIT = 10
    HARD_LIMIT = 20

    STATES = (
        (OK, 'OK'),
        (SOFT_LIMIT, 'Soft Limit'),
        (HARD_LIMIT, 'Hard Limit'),
    )

    cluster = models.ForeignKey('provider.Cluster', null=True, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, null=True, on_delete=models.CASCADE)

    active_calls = models.PositiveIntegerField(default=0)
    active_participants = models.PositiveIntegerField(default=0)
    active_participants_gateway = models.PositiveIntegerField(default=0)

    participant_status = models.SmallIntegerField(choices=STATES)

    last_check = models.DateTimeField(default=now)

    objects = CustomerPolicyStateManager()

    @property
    def participant_value(self):
        return self.active_participants + self.active_participants_gateway

    def _get_participant_status(self):
        policy = CustomerPolicy.objects.get_active(customer=self.customer)
        if not policy:
            return self.OK

        return policy.check_participant_count(self.participant_value)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['cluster', 'customer'],
                             name='unique_with_customer'),
            UniqueConstraint(fields=['cluster'],
                             condition=Q(customer=None),
                             name='unique_without_customer'),
        ]

    def save(self, *args, **kwargs):

        if self.active_calls < 0:
            self.active_calls = 0
        if self.active_participants < 0:
            self.active_participants = 0
            self.active_participants_gateway = 0
        if self.active_participants_gateway < 0:
            self.active_participants_gateway = 0

        self.participant_status = self._get_participant_status()
        CustomerPolicyManager._customer_active_policy.cache.clear()
        super().save(*args, **kwargs)


class NoDirectChangeQuerySet(models.QuerySet):

    def _error(self, *args, **kwargs):
        raise IntegrityError('No direct updates for model %s' % self.model)

    create = _error
    get_or_create = _error
    update_or_create = _error
    update = _error
    delete = _error


class NoDirectChangeManager(models.Manager):
    def get_queryset(self):
        return NoDirectChangeQuerySet(model=self.model, using=self._db, hints=self._hints)


class ActiveParticipant(models.Model):

    cluster = models.ForeignKey('provider.Cluster', null=True, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, null=True, on_delete=models.CASCADE)

    ts_created = models.DateTimeField(default=now)
    guid = models.CharField(max_length=500)
    name = models.CharField(max_length=300)
    is_gateway = models.BooleanField(default=False)

    objects = NoDirectChangeManager()
    direct_objects = models.Manager()

    class Meta:
        unique_together = ('cluster', 'guid')


class ActiveCall(models.Model):

    cluster = models.ForeignKey('provider.Cluster', null=True, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, null=True, on_delete=models.CASCADE)

    ts_created = models.DateTimeField(default=now)

    name = models.CharField(max_length=300)

    objects = NoDirectChangeManager()
    direct_objects = models.Manager()

    class Meta:
        unique_together = ('cluster', 'name')


class PolicyLog(models.Model):

    PARTICIPANT = 1
    CALL = 2

    DIFF = 10
    RESET = 11

    TYPES = (
        (0, _('Unknown')),
        (PARTICIPANT, 'Participant'),
        (CALL, 'Call'),
        (10, _('Diff')),
    )

    LEVELS = (
        (1, _('Debug')),
        (2, _('Warning')),
    )

    class PolicyLogSource(IntEnum):
        UNKNOWN = 0

        EVENT = 1
        HISTORY = 10
        REBUILD = 20
        CHECK = 30

        @classmethod
        def lookup(cls, key: Union[int, str]):
            """
            :rtype PolicyLogSource
            """
            if isinstance(key, int):
                if key in cls:
                    return PolicyLog.PolicyLogSource(key)
                return cls.UNKNOWN

            return {
                'eventsink': cls.EVENT,
                'cdr': cls.EVENT,
                'history': cls.HISTORY,
                'recheck': cls.REBUILD,
                'check': cls.CHECK,
                'connect_check': cls.CHECK,
                'disconnected_check': cls.CHECK,
            }.get(key, cls.UNKNOWN)

    ts = models.DateTimeField(default=now, db_index=True)
    cluster = models.ForeignKey('provider.Cluster', null=True, blank=True, on_delete=models.SET_NULL)
    customer = models.ForeignKey(Customer, null=True, on_delete=models.CASCADE)
    message = models.TextField()
    guid = models.CharField(max_length=500)
    source = models.SmallIntegerField(choices=[(int(member), name) for name, member in PolicyLogSource.__members__.items()], null=True, blank=True)
    level = models.SmallIntegerField(default=1, choices=LEVELS)
    type = models.SmallIntegerField(choices=TYPES)

    objects = FastCountManager()


class ExternalPolicyLog(models.Model):

    ts = models.DateTimeField(default=now, db_index=True)
    cluster = models.ForeignKey('provider.Cluster', null=True, blank=True, on_delete=models.SET_NULL)
    customer = models.ForeignKey(Customer, null=True, on_delete=models.CASCADE)
    message = models.TextField()
    limit = models.SmallIntegerField(choices=CustomerPolicyState.STATES)
    action = models.SmallIntegerField(default=0, choices=ClusterPolicy.ACTIONS)
    conference = models.CharField(max_length=300, null=True)
    gateway_rule = models.CharField(max_length=300, null=True)
    local_alias = models.CharField(max_length=300)
    remote_alias = models.CharField(max_length=300)
    needs_auth = models.BooleanField(null=True)

    objects = FastCountManager()

