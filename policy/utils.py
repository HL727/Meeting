from collections import defaultdict, Counter
from datetime import timedelta
from itertools import chain
from django.utils.translation import gettext as _

from django.utils.timezone import now

from policy.models import CustomerPolicy
from room_analytics.graph import get_graph
from statistics.graph import get_layout
from statistics.forms import StatsForm
from statistics.utils.leg_collection import LegCollection

DEFAULT_DAYS = 7


def create_from_statistics(user=None, **filters):

    filters.setdefault('ts_start', (now() - timedelta(days=DEFAULT_DAYS)).replace(hour=0, minute=0, second=0))
    filters.setdefault('ts_stop', now())
    filters['multitenant'] = True

    form = StatsForm(filters, user=user)
    legs = form.get_legs(populate=False)

    filters['only_gateway'] = True

    gateway_form = StatsForm(filters, user=user)
    if hasattr(legs, 'union'):
        legs = legs.order_by().union(gateway_form.get_legs(populate=False).order_by()).order_by('ts_start')
    else:
        legs += gateway_form.get_legs(populate=False)

    try:
        cluster_id = form.cleaned_data['server'].cluster_id
    except AttributeError:
        cluster_id = None

    resolution = 5

    leg_collection = LegCollection.from_legs(legs, trim_times=(filters['ts_start'], filters['ts_stop']))
    ou_data, unit_data, tenant_data, total_data = leg_collection.grouped_legs_count_for_chunks(resolution_seconds=resolution * 60)

    policies = CustomerPolicy.objects.filter(
        date_start__lte=form.cleaned_data['ts_stop'].date(),
    ).order_by('date_start')

    policy_map = defaultdict(list)
    cluster_default_tenants = defaultdict(list)

    for policy in policies:
        if policy.customer.acano_tenant_id:
            policy_map[policy.customer.acano_tenant_id].append(policy)
        if policy.customer.pexip_tenant_id:
            policy_map[policy.customer.pexip_tenant_id].append(policy)

        if not policy.customer.acano_tenant_id and not policy.customer.pexip_tenant_id:
            for ou in policy.customer.get_non_domain_keys():
                policy_map[ou].append(policy)

            if policy.customer.lifesize_provider_id:
                cluster_default_tenants[policy.customer.lifesize_provider_id].append(policy)

    soft_limit = defaultdict(Counter)
    soft_limit_30 = defaultdict(Counter)
    hard_limit = defaultdict(Counter)
    count_result = {
        'limits': {},
        'count': defaultdict(Counter),
    }

    customers = {}
    for tenant_id, counters in chain(tenant_data.items(), ou_data.items()):

        policies = policy_map.get(tenant_id)
        if not policies and not tenant_id and cluster_id:
            policies = cluster_default_tenants[cluster_id]

        if not policies:
            continue
        for ts, count in counters.items():

            policy = policies[0]

            ts_key = str(ts.date())

            customers.setdefault(policy.customer_id, policy.customer)

            if len(policies) > 1 and policies[1].date_start <= ts.date():
                policies.pop(0)

            state = policy.check_participant_count(count)

            if state >= policy.SOFT_LIMIT:
                soft_limit[policy.customer_id][ts_key] += resolution
                if count >= policy.participant_limit * 1.3:
                    soft_limit_30[policy.customer_id][ts_key] += resolution

                count_result['limits'][policy.customer_id] = {
                    'soft_limit': policy.participant_limit,
                    'hard_limit': policy.participant_hard_limit,
                }
                count_result['count'][policy.customer_id][ts.strftime('%Y-%m-%d %H:%M:%S')] = max(count, count_result['count'][policy.customer_id][ts.strftime('%Y-%m-%d %H:%M:%S')])

            if state == policy.HARD_LIMIT:
                hard_limit[policy.customer_id][ts_key] += resolution

    return soft_limit, soft_limit_30, hard_limit, count_result


def report_to_graphs(report_data):

    soft_limit, soft_limit_30, hard_limit, count_result = report_data

    from customer.models import Customer
    customers = Customer.objects.in_bulk(set(soft_limit.keys()) | set(soft_limit_30.keys()) | set(hard_limit.keys()))

    from plotly.graph_objs import Bar, Figure, Scatter

    def _add_customer_values(limit_map, label, target):
        x = list(limit_map.keys())
        y = [round(limit_map[date] * 2 / 60) / 2 for date in x]

        cur = Bar(x=x, y=y, name=label)
        target.append(cur)

    figures = {
        'soft_limit': None,
        'soft_limit_30': None,
        'hard_limit': None,
        'count': None,
    }

    if soft_limit:
        lines = []
        for customer_id, values in soft_limit.items():
            customer = customers[customer_id]
            _add_customer_values(values, str(customer), lines)

        figures['soft_limit'] = get_graph(Figure(data=lines, layout=get_layout(lines, barmode='group')), as_json=True)

    if soft_limit_30:
        lines = []
        for customer_id, values in soft_limit_30.items():
            customer = customers[customer_id]
            _add_customer_values(values, str(customer), lines)

        figures['soft_limit_30'] = get_graph(Figure(data=lines, layout=get_layout(lines, barmode='group')), as_json=True)

    if hard_limit:
        lines = []
        for customer_id, values in hard_limit.items():
            customer = customers[customer_id]
            _add_customer_values(values, str(customer), lines)

        figures['hard_limit'] = get_graph(Figure(data=lines, layout=get_layout(lines, barmode='group')), as_json=True)

    if count_result['count']:
        figures['count'] = {
            'layout': get_layout([], barmode='group')._props,
            'graphs': {},
        }

        for customer_id, values in count_result['count'].items():
            x = list(values.keys())
            y = [values[date] for date in x]

            count = Bar(x=x, y=y, name=_('Antal deltagare'))

            limits = []
            if count_result['limits'][customer_id]['soft_limit']:
                limits.append(Scatter(x=[x[0], x[-1]], y=[count_result['limits'][customer_id]['soft_limit']] * 2, name='Soft limit'))
            if count_result['limits'][customer_id]['hard_limit']:
                limits.append(Scatter(x=[x[0], x[-1]], y=[count_result['limits'][customer_id]['hard_limit']] * 2, name='Hard limit'))

            figures['count']['graphs'][customer_id] = get_graph(Figure(data=[count, *limits]), as_json=True)

    return figures

