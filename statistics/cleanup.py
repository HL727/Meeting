from collections import defaultdict
from datetime import timedelta

from cacheout import fifo_memoize
from django.conf import settings
from django.db import connection, connections, transaction
from django.db.models import QuerySet
from django.utils.timezone import now

from customer.models import CustomerMatch
from provider.models.provider import Cluster
from statistics.models import Call, Leg, Tenant, Server, Domain
from endpoint.models import Endpoint
from statistics.parser.utils import is_phone, get_ou, get_domain, rewrite_internal_domains, get_org_unit, \
    get_internal_domains, clean_target

try:
    from psycopg2.extras import execute_batch
except ImportError:
    execute_batch = None


def LegDirect() -> QuerySet[Leg]:

    qs = Leg.objects.all()
    if 'direct' in settings.DATABASES:
        return qs.using('direct')
    return qs


def _get_leg_chunks(ts_start=None, ts_stop=None, extra_filters=None):

    legs = Leg.objects.filter(ts_start__isnull=False).values_list('ts_start', flat=True)

    if extra_filters:
        legs = legs.filter(**extra_filters)

    if not ts_stop:
        ts_stop = now()

    if not ts_start:
        ts_start = legs.order_by('ts_start').first() or ts_stop

    cur_stop = ts_stop
    while cur_stop >= ts_start:
        cur_stop = legs.filter(ts_start__lte=cur_stop).order_by('-ts_start').first()

        if not cur_stop:
            return

        cur_start = cur_stop - timedelta(days=5)

        yield cur_start, cur_stop

        cur_stop = cur_start - timedelta(seconds=1)


def rewrite_history_chunks(recluster=False, verbose=False, ts_start=None, ts_stop=None, force_rematch=False, extra_filters=None, server=None):

    if server:
        extra_filters = extra_filters or {}
        extra_filters['server'] = server

    for cur_start, cur_stop in _get_leg_chunks(ts_start, ts_stop):
        if verbose:
            print('{} - {}'.format(cur_start, cur_stop))

        rewrite_history(recluster=recluster, verbose=verbose, ts_start=cur_start, ts_stop=cur_stop,
                        force_rematch=force_rematch, extra_filters=extra_filters)


def rewrite_pexip_chunks(verbose=False, ts_start=None, ts_stop=None, force_rematch=False, extra_filters=None, server=None):

    if server:
        extra_filters = extra_filters or {}
        extra_filters['server'] = server
    else:
        extra_filters = extra_filters or {}
        extra_filters['server__type'] = Server.PEXIP

    for cur_start, cur_stop in _get_leg_chunks(ts_start, ts_stop, extra_filters=extra_filters):
        if verbose:
            print('{} - {}'.format(cur_start, cur_stop))

        ts_kwargs = {
            'ts_start__lte': cur_stop,
            'ts_start__gte': cur_start,
        }
        rewrite_pexip(verbose=verbose, ts_kwargs=ts_kwargs, force_rematch=force_rematch)


def rewrite_history(recluster=False, verbose=False, ts_start=None, ts_stop=None, force_rematch=False, extra_filters=None, server=None):

    ts_kwargs = {}
    if ts_stop:
        ts_kwargs['ts_start__lte'] = ts_stop
    if ts_start:
        ts_kwargs['ts_start__gte'] = ts_start

    if server:
        extra_filters = extra_filters or {}
        extra_filters['server'] = server

    if extra_filters:
        ts_kwargs.update(extra_filters)

    rewrite_basic_data(ts_kwargs=ts_kwargs, force_rematch=force_rematch, verbose=verbose)
    rewrite_pexip(ts_kwargs=ts_kwargs, force_rematch=force_rematch, verbose=verbose)

    if recluster:
        connection.cursor().execute('CLUSTER statistics_leg USING statistics_leg_pkey')
        connection.cursor().execute('REINDEX TABLE statistics_leg')


def rewrite_basic_data(verbose=False, ts_kwargs=None, force_rematch=False):

    ts_kwargs = ts_kwargs or {}
    script_start = now()

    i = 0

    tenants = {}
    targets = {}

    target_cache = defaultdict(dict)

    default_domains = {s.pk: s.default_domain for s in Server.objects.all()}
    internal_domains = get_internal_domains()
    units = {}
    domains = {d.pk: d for d in Domain.objects.all()}

    def _rewrite(target, server_id):
        return rewrite_internal_domains(target, default_domain=default_domains.get(server_id),
                                              internal_domains=internal_domains)

    @transaction.atomic
    def _iter(leg):
        nonlocal i

        if verbose and i == 0: print('first')

        target = clean_target(leg.target)

        leg_ou = leg.ou
        if not leg_ou and target != 'guest':
            if 'ou' not in target_cache[target]:
                target_cache[target]['ou'] = get_ou(target)

            if target_cache[target]['ou']:
                Leg.objects.filter(target=target, ou='').update(ou=target_cache[target]['ou'])
                leg_ou = target_cache[target]['ou']

        if leg.target not in targets and target != 'guest':
            leg_change = {}

            if target == 'phone' or is_phone(target):
                target = is_phone(target) or target
                if '@' not in target:
                    temp = Leg.objects.filter(id=leg.id, target=leg.target).values_list('local', 'remote', named=True).first()
                    if temp:
                        target = is_phone(temp.remote) or is_phone(temp.local) or target
                leg_change['is_guest'] = True

            if 'endpoint' not in target_cache[target]:
                endpoint = target_cache[target]['endpoint'] = Endpoint.objects.get_from_uri(target, only='id')
                if endpoint:
                    Leg.objects.filter(target=leg.target, endpoint__isnull=True).update(endpoint=endpoint)

            target = _rewrite(target, leg.server)

            if target != leg.target:
                leg_change['target'] = target

            if not leg.domain and '@' in target:
                cur_domain = get_domain(target)
                domain_obj = domains.get(cur_domain) or Domain.objects.get_or_create(domain=cur_domain)[0]
                domains[cur_domain] = domain_obj
                leg_change['domain'] = domain_obj

            if leg_change:
                Leg.objects.filter(target=leg.target, **ts_kwargs).update(**leg_change)

        if leg.tenant not in tenants:
            tenants[leg.tenant] = Tenant.objects.get_or_create(guid=leg.tenant)[0].pk
            Leg.objects.filter(tenant=leg.tenant, tenant_fk__isnull=True, **ts_kwargs).update(tenant_fk=tenants[leg.tenant])

        if leg.org_unit and not force_rematch:
            pass
        elif target not in units and target != 'guest':
            unit = get_org_unit(target)
            if unit:
                units[target] = target
                Leg.objects.filter(target=target, org_unit__isnull=True, **ts_kwargs).update(org_unit=unit)

        i += 1
        if verbose and i % 5000 == 0:
            print(i, now() - script_start)

    # update duration
    if 'postgre' in settings.DATABASES['default']['ENGINE']:
        connection.cursor().execute('UPDATE statistics_leg SET duration=EXTRACT(EPOCH FROM (ts_stop - ts_start)) where '
                                    'duration is null or duration=0 and ts_start is not null and ts_stop is not null')
        connection.cursor().execute('UPDATE statistics_leg SET should_count_stats=\'f\' WHERE ts_stop is not null and duration < 60')

    # update relations and basic data
    columns = ('id', 'tenant', 'target', 'ou', 'org_unit', 'call__cospace_id', 'protocol', 'server', 'endpoint', 'domain')

    for leg in LegDirect().filter(**ts_kwargs).order_by().values_list(*columns, named=True).iterator():

        _iter(leg)

    # lync fixes
    Leg.objects.filter(protocol=Leg.LYNC, remote__contains=';', should_count_stats=True, **ts_kwargs).exclude(remote__contains='audio-video').update(protocol=Leg.LYNC_SUB, should_count_stats=False)

    for leg in LegDirect().filter(protocol=Leg.LYNC, call__isnull=True, **ts_kwargs).iterator():
        if ';' in leg.remote and 'audio-video' not in leg.remote:
            Leg.objects.filter(target=leg.target, remote=leg.remote).update(protocol=Leg.LYNC_SUB, should_count_stats=False)
            continue

        Leg.objects.filter(id=leg.id).update(call=Call.objects.update_or_create(server=leg.server, guid=leg.guid, defaults=dict(
            ts_start=leg.ts_start, ts_stop=leg.ts_stop,
            duration=leg.duration, total_duration=leg.duration,
            ou=leg.ou, org_unit=leg.org_unit))[0]
       )


def merge_duplicate_calls(server, ts_start=None, ts_stop=None, use_cospace_id=False):
    try:
        if 'direct' in settings.DATABASES:
            cursor = connections['direct'].cursor()
        else:
            cursor = connection.cursor()
    except Exception:
        cursor = connection.cursor()

    sql = '''
    create temporary table _calls as
        select substr(s.cospace, 0, 15), s.id, s2.id as s2id, s.ts_start, s.ts_stop, s2.ts_start as s2start, s2.ts_stop as s2ts_stop, s.server_id, s.guid, s2.guid as s2guid
        from statistics_call s
        inner join statistics_call s2
            on s.cospace{id_suffix}=s2.cospace{id_suffix} and s2.ts_stop >= s.ts_start and s2.ts_start <= s.ts_start and s2.server_id=s.server_id and s.id!=s2.id
        where s.server_id=%s and s.ts_start >= %s and s.ts_start < %s;
    '''.format(id_suffix='_id' if use_cospace_id else '')

    with transaction.atomic():
        cursor.execute(sql, (server.pk, ts_start or now().replace(year=2000), ts_stop or now()))

        cursor.execute('''
        select c.*,
            (select count(*) from statistics_leg where call_id=c.id) as s1count,
            (select count(*) from statistics_leg where call_id=s2id) as s2count
        from _calls c order by ts_start;
        ''')
        cols = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        cursor.execute('drop table _calls')

    result = defaultdict(list)
    moved = {}

    for row in rows:
        row = dict(zip(cols, row))

        if row['id'] in result or row['id'] in moved:
            continue  # already processed. multijoin

        if (row['s2guid'] or not row['guid']) and (row['s2count'] > row['s1count'] or not row['ts_stop']):
            new_id, old_id = row['s2id'], row['id']
        else:
            new_id, old_id = row['id'], row['s2id']

        if new_id in moved:
            if old_id not in moved:
                new_id, old_id = old_id, new_id
            else:
                raise ValueError('Loop')

        cursor.execute('UPDATE statistics_leg SET call_id=%s WHERE call_id=%s', (new_id, old_id))
        cursor.execute('DELETE FROM statistics_call WHERE id=%s', (old_id,))
        result[new_id].append(old_id)
        result[new_id].extend(result.pop(old_id, []))

        moved[old_id] = new_id

    cursor.close()

    return dict(result)


# FIXME remove. temp bug
def rewrite_pexip_temp(verbose=False, ts_kwargs=None, force_rematch=False):

    internal_domains = get_internal_domains()

    default_domains = {s.pk: s.default_domain for s in Server.objects.all()}

    def _rewrite(target, server_id):
        return rewrite_internal_domains(target, default_domain=default_domains.get(server_id),
                                        internal_domains=internal_domains)

    for leg in LegDirect().filter(server__type=Server.PEXIP, **ts_kwargs).values_list('call', 'server', 'remote', 'protocol', 'ts_start', 'ts_stop', 'should_count_stats', 'local', 'target', 'direction', named=True).iterator():
        local = _rewrite(leg.local, leg.server)
        remote = _rewrite(leg.remote, leg.server)

        if leg.direction == 'in' and leg.target == local:
            Leg.objects.filter(call=leg.call, target=leg.target, local=leg.local, direction='in', **ts_kwargs).update(target=remote)
        if leg.direction == 'out' and leg.target == local:
            Leg.objects.filter(call=leg.call, target=leg.target, remote=leg.remote, direction='out', **ts_kwargs).update(target=remote)

        if leg.protocol == Leg.TEAMS and '@' in leg.remote and '@' not in leg.local:
            Leg.objects.filter(target=leg.target, local=leg.local, remote=leg.remote, **ts_kwargs).update(local=leg.remote, remote=leg.local, target=local)

    for server in Server.objects.filter(type=Server.PEXIP):
        merge_duplicate_calls(server)


    Leg.objects.filter(server__type=Server.PEXIP, protocol__in=(Leg.LYNC, Leg.LYNC_SUB, Leg.TEAMS), direction='out', **ts_kwargs).update(should_count_stats=False)
    Leg.objects.filter(server__type=Server.PEXIP, protocol__in=(Leg.LYNC, Leg.LYNC_SUB, Leg.TEAMS), direction='', **ts_kwargs).update(should_count_stats=False)
    Leg.objects.filter(server__type=Server.PEXIP, duration__gt=60, **ts_kwargs).exclude(protocol__in=(Leg.LYNC, Leg.LYNC_SUB, Leg.TEAMS), direction='out').update(should_count_stats=True)

# /FIXME


def rewrite_pexip(verbose=False, ts_kwargs=None, force_rematch=False):

    if force_rematch:
        tenant_kwargs = {}
    else:
        tenant_kwargs = {'tenant': ''}

    clusters = {c.pk: c for c in Cluster.objects.all()}

    call_tenant_queue = defaultdict(list)
    leg_tenant_queue = defaultdict(list)

    @fifo_memoize(100, ttl=60)
    def _tenant(tenant_id):
        return Tenant.objects.get_or_create(guid=tenant_id)[0]

    def _exec():
        for tenant_id, ids in leg_tenant_queue.items():
            Leg.objects.filter(pk__in=ids).update(tenant=tenant_id, tenant_fk=_tenant(tenant_id) if tenant_id else None)
        leg_tenant_queue.clear()

        for tenant_id, ids in call_tenant_queue.items():
            Call.objects.filter(pk__in=ids).update(tenant=tenant_id, tenant_fk=_tenant(tenant_id) if tenant_id else None)
        call_tenant_queue.clear()

    cols = ('leg_id', 'conference', 'call_tenant', 'call_id', 'local_alias', 'remote_alias', 'tenant', 'cluster')

    @fifo_memoize(2000, ttl=60)
    def _conference_tenant(name, local_alias, cluster_id):
        cluster = clusters[cluster_id] if cluster_id else None
        customer = CustomerMatch.objects.get_customer_for_pexip(conference_name=name,
                                                                obj={'local_alias': local_alias},
                                                                cluster=cluster)
        if customer:
            return customer.get_pexip_tenant_id()

    @fifo_memoize(100, ttl=60)
    def _alias_tenant(local_alias, cluster_id):
        customer = CustomerMatch.objects.match_text(local_alias, cluster=cluster_id)
        if customer:
            return customer.get_pexip_tenant_id()

    for leg_data in LegDirect().filter(server__type=Server.PEXIP, **tenant_kwargs, **ts_kwargs)\
      .values_list('id', 'call__cospace', 'call__tenant', 'call_id', 'local', 'remote', 'tenant', 'server__cluster').iterator():

        leg = dict(zip(cols, leg_data))

        local_alias = clean_target(leg['local_alias'])
        tenant_id = _conference_tenant(leg['conference'], local_alias, leg['cluster'])

        if tenant_id and leg['call_tenant'] != tenant_id:
            call_tenant_queue[tenant_id].append(leg['call_id'])

        if not tenant_id:
            tenant_id = _alias_tenant(local_alias, leg['cluster']) or _alias_tenant(clean_target(leg['remote_alias']), leg['cluster'])

        if tenant_id and tenant_id != leg['tenant']:
            leg_tenant_queue[tenant_id].append(leg['leg_id'])
            if len(leg_tenant_queue[tenant_id]) > 200:
                _exec()
    _exec()


if __name__ == '__main__':
    print('start')
    rewrite_history()




