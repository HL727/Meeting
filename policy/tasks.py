import logging
from datetime import timedelta

from billiard.exceptions import SoftTimeLimitExceeded
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from sentry_sdk import capture_exception

from conferencecenter.celery import app
from provider.exceptions import ResponseConnectionError, AuthenticationError

"""
Policy state is error prone. Call events may come in the wrong order,
stop sending from some nodes (but not necessarily all) and may not
contain all information.

Asking the MCU may also lock their local state and can take 20+ seconds
before the data is received, all the while more events have been processed.
"""

logger = logging.getLogger(__name__)


class Encoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, set):
            return list(o)
        return super().default(o)


@app.task(bind=True, time_limit=4 * 60, soft_time_limit=4 * 60 - 10)
def recheck_policy_states(self):

    from provider.models.provider import Cluster

    for cluster in Cluster.objects.filter(type__in=[Cluster.TYPES.pexip_cluster, Cluster.TYPES.acano_cluster]):
        if not cluster.get_clustered(include_self=True):
            continue  # empty cluster

        try:
            recheck_policy_state_cluster(cluster)
        except SoftTimeLimitExceeded:
            break
        except Exception:
            capture_exception()
            return


@app.task(bind=True)
def recheck_policy_state_cluster(self, cluster):
    from provider.models.provider import Cluster
    from policy.models import CustomerPolicyState, PolicyLog

    encoder = Encoder()

    if isinstance(cluster, int):
        cluster = Cluster.objects.get(pk=cluster)

    try:
        diff, remote_participants = CustomerPolicyState.objects.compare_cluster_state(cluster=cluster)
    except (ResponseConnectionError, AuthenticationError):
        return

    if remote_participants:
        reset_missing_leg_stop_time.apply_async([cluster.pk, remote_participants, now() - timedelta(minutes=3)], countdown=5 * 60)

    if not diff:
        return  # everything is OK

    call_diff = {tenant_id or '': d[0] for tenant_id, d in diff.items() if any(d[0])}
    participant_diff = {tenant_id or '': d[1] for tenant_id, d in diff.items() if any(d[1])}

    # log
    if call_diff:
        message = 'Call state differs for cluster %s (%s): %s'
        log_args = cluster.pk, cluster, encoder.encode(call_diff)
        logger.info(message, *log_args)
        PolicyLog.objects.create(message=message % log_args,
                                 guid=str(cluster.pk), type=PolicyLog.DIFF or 0, level=3,
                                 source=PolicyLog.PolicyLogSource.CHECK)
    if participant_diff:
        message = 'Participant state differs for cluster %s (%s): %s'
        log_args = cluster.pk, cluster, encoder.encode(participant_diff)
        logger.info(message, *log_args)
        PolicyLog.objects.create(message=message % log_args,
                                 guid=str(cluster.pk), type=PolicyLog.DIFF or 0, level=3,
                                 source=PolicyLog.PolicyLogSource.CHECK)

    # fix state after the fact
    message = 'Starting full state count rebuild for cluster %s (%s)'
    log_args = cluster.pk, cluster
    logger.info(message, *log_args)

    changed = CustomerPolicyState.objects.rebuild_cluster_counts(cluster)
    if changed:
        PolicyLog.objects.create(message='Reset values for cluster {}: '
                                         '{}'.format(cluster.pk, encoder.encode(changed)),
                                 guid=str(cluster.pk), type=PolicyLog.RESET, level=3,
                                 source=PolicyLog.PolicyLogSource.CHECK)

    if cluster.is_pexip:  # only pexip has all information needed to add participants
        add_missing_policy_state_items.apply_async([cluster.pk, diff])
    remove_disconnected_policy_state_items.apply_async([cluster.pk, diff], countdown=2)


@app.task(bind=True)
def add_missing_policy_state_items(self, cluster_id, cluster_diff):
    from provider.models.provider import Cluster
    from policy.models import CustomerPolicyState

    cluster = Cluster.objects.filter(pk=cluster_id).first()
    if cluster:
        CustomerPolicyState.objects.add_missing(cluster, cluster_diff)


@app.task(bind=True)
def remove_disconnected_policy_state_items(self, cluster_id, cluster_diff):
    from provider.models.provider import Cluster
    from policy.models import CustomerPolicyState

    cluster = Cluster.objects.filter(pk=cluster_id).first()
    if cluster:
        CustomerPolicyState.objects.remove_disconnected(cluster, cluster_diff)


@app.task(bind=True)
def reset_missing_leg_stop_time(self, cluster_id, remote_participants=None, ts=None):
    from provider.models.provider import Cluster
    from customer.models import Customer

    cluster = Cluster.objects.filter(pk=cluster_id).first()
    if not cluster:
        return

    if ts and isinstance(ts, str):
        ts = parse_datetime(ts)

    api = cluster.get_api(Customer.objects.first())
    removed_guids = None
    if remote_participants is not None:
        guids = {guid for p in remote_participants for guid in {p.get('call_uuid'), p.get('id')} if guid}
        removed_guids = api.get_active_legs(only_should_count_stats=False).exclude(guid__in=guids).values_list('guid', flat=True)

        if not removed_guids:
            return

    api.reset_stopped_statistics_legs(removed_guids, ts)
