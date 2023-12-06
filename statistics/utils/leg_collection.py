from collections import defaultdict
from datetime import datetime, timedelta, tzinfo
from typing import Iterable, Sequence, Union, List, Tuple, Optional, Dict, Iterator, DefaultDict, cast

from django.db import models
from django.db.models.query import QuerySet
from django.utils.timezone import get_current_timezone, now
from django.utils.translation import gettext_lazy as _
from typing_extensions import Counter

from customer.models import CustomerKey, Customer
from datastore.models import acano as ds
from organization.models import CoSpaceUnitRelation, UserUnitRelation, OrganizationUnit
from statistics.parser.utils import rewrite_internal_domains, get_internal_domains, clean_target
from ..models import Leg, Server
from .time import TimeRangeChunker, get_capped_duration
from ..types import LegData, DurationSecondsResult, LegTimestepDuration, GroupedCallSecondsResult, \
    LegRelatedTitles, ValidCustomerRelations, CallSecondsResult


class LegCollection:

    def __init__(
        self,
        legs: Sequence[LegData],
        related_data: 'LegCollectionRelatedData',
        trim_times: Tuple[datetime, datetime] = None,
    ):

        self.legs = list(legs)
        self.related_data = related_data

        default = now() + timedelta(hours=1)  # TODO what to do when empty?

        self.first_ts_start = legs[0].ts_start if legs else default
        self.last_ts_stop = max(leg.ts_stop for leg in legs) if legs else default

        self.trim_times = None
        if trim_times and all(trim_times):
            self.trim_times = trim_times
            if trim_times[1] < trim_times[0]:
                raise ValueError('Last time cant be before first time')
            self.first_ts_start = max(trim_times[0], self.first_ts_start or trim_times[0])
            self.last_ts_stop = min(trim_times[1], self.last_ts_stop or trim_times[1])

    @staticmethod
    def from_legs(
        legs: Union['LegCollection', Sequence[Leg], QuerySet[Leg], Iterable[LegData]],
        related_data: 'LegCollectionRelatedData' = None,
        trim_times: Tuple[datetime, datetime] = None,
        valid_relations: ValidCustomerRelations = None,
    ):
        if isinstance(legs, LegCollection):
            if trim_times and trim_times != legs.trim_times:
                raise ValueError('Conflicting trim_times for existing LegCollection')
            return legs

        if related_data is None:
            qs = cast(Union[Sequence[Leg], QuerySet[Leg]], legs)
            populated_legs, related_data = populate_legs(qs, trim_times=trim_times, valid_relations=valid_relations)
        elif valid_relations:
            raise ValueError('valid_relations should only be provided if related_data is not already loaded')
        else:
            populated_legs = cast(List[LegData], legs)

        return LegCollection(populated_legs, related_data=related_data, trim_times=trim_times)

    @classmethod
    def from_queryset(cls, leg_qs, ts_start=None, ts_stop=None):

        trim = (ts_start, ts_stop) if ts_start or ts_stop else None
        legs, related_data = populate_legs(leg_qs, trim_times=trim)
        return cls(legs, related_data, trim_times=trim)

    def __iter__(self) -> Iterator[LegData]:
        return iter(self.legs)

    def __len__(self):
        return len(self.legs)

    def iter_durations(self, cap_ts_start=None, cap_ts_stop=None):
        if not (cap_ts_start or cap_ts_stop):
            return ((leg, leg.duration) for leg in self.legs)

        for leg in self.legs:

            if (cap_ts_start and leg.ts_stop < cap_ts_start) or (cap_ts_stop and leg.ts_start > cap_ts_stop):
                continue

            yield leg, get_capped_duration(leg, cap_ts_start, cap_ts_stop)

    def count_and_sum_calls(
        self,
        leg_seconds: Iterator[LegTimestepDuration],
        group_attrs: List[str],
        group_by_titles: False,
    ) -> Sequence[GroupedCallSecondsResult]:
        """
        Group results by LegData attributes `group_attrs`.
        Return object with call seconds and number of started calls
        per each timestamp step
        """
        unique_started_calls = set()

        result: Dict[str, DefaultDict[str, DefaultDict[str, DurationSecondsResult]]] \
            = {k: defaultdict(lambda: defaultdict(DurationSecondsResult)) for k in group_attrs}

        def _count_call_start(call_id, first_step_ts, attr, title):
            cur = (call_id, attr, title)
            if cur in unique_started_calls:
                return
            unique_started_calls.add(cur)
            result[attr][title][first_step_ts].start_call_count += 1

        for leg, steps in leg_seconds:
            if group_by_titles:
                all_titles = leg.titles
                titles = [(attr, getattr(all_titles, attr) if attr else '') for attr in group_attrs]
            else:
                titles = [(attr, getattr(leg, attr) if attr else '') for attr in group_attrs]

            is_first = True
            for step_ts, seconds in steps:
                if is_first:
                    for attr, title in titles:
                        _count_call_start(leg.call_id, step_ts, attr, title)
                    is_first = False
                for attr, title in titles:
                    result[attr][title][step_ts].seconds += seconds

        return tuple({k: dict(v) for k, v in result[k].items()} for k in group_attrs)

    def sum_call_seconds_grouped(
        self,
        leg_seconds: Iterator[LegTimestepDuration],
    ) -> Tuple[CallSecondsResult, CallSecondsResult, CallSecondsResult, CallSecondsResult]:
        """
        Group results by standard set target, ou, org_unit and total.
        Return object with sum of seconds
        """
        keys = ['target', 'ou', 'org_unit', '']
        result: Sequence[DefaultDict[str, Counter[str]]] \
            = [defaultdict(lambda: Counter()) for _k in keys]

        for leg, steps in leg_seconds:
            for step_ts, seconds in steps:
                result[0][leg.target][step_ts] += seconds
                result[1][leg.titles.ou][step_ts] += seconds
                result[2][leg.titles.org_unit][step_ts] += seconds
                result[3][''][step_ts] += seconds

        return dict(result[0]), dict(result[1]), dict(result[2]), dict(result[3])

    def iter_call_seconds_per_step(
        self,
        hours: int = 1,
        group_dateformat: str = None,
    ) -> Iterator[LegTimestepDuration]:
        """
        Split times between each legs ``.ts_start`` and ``.ts_stop`` in ``hours`` chunks.
        Yield each leg and a list of tuples with the start time and duration contained in
        the legs timespan
        """
        chunker = TimeRangeChunker(resolution_seconds=hours * 60 * 60)

        for leg in self.legs:
            steps = chunker.iter_chunks_duration(leg.ts_start, leg.ts_stop, group_dateformat=group_dateformat)
            if not steps:
                continue
            yield leg, steps

    def iter_call_seconds_per_day(self) -> Iterator[LegTimestepDuration]:
        return self.iter_call_seconds_per_step(hours=24, group_dateformat='%Y-%m-%d')

    def iter_call_seconds_per_hour(self)  -> Iterator[LegTimestepDuration]:
        return self.iter_call_seconds_per_step(hours=1, group_dateformat='%Y-%m-%d %H:00')

    def iter_call_seconds_per_time_of_day(self) -> Iterator[LegTimestepDuration]:
        return self.iter_call_seconds_per_step(hours=1, group_dateformat='%H:00')

    def get_grouped_call_seconds_per_day(self) \
      -> Sequence[CallSecondsResult]:
        return self.sum_call_seconds_grouped(self.iter_call_seconds_per_day())

    def get_grouped_call_seconds_per__hour(self) \
      -> Sequence[CallSecondsResult]:
        return self.sum_call_seconds_grouped(self.iter_call_seconds_per_hour())

    def get_grouped_call_seconds_per_time_of_day(self) \
      -> Sequence[GroupedCallSecondsResult]:
        return self.count_and_sum_calls(self.iter_call_seconds_per_time_of_day())

    def get_grouped_call_stats_per_day(self) -> Sequence[GroupedCallSecondsResult]:
        return self.count_and_sum_calls(
            self.iter_call_seconds_per_day(),
            ['target', 'ou', 'org_unit', 'tenant', ''],
            group_by_titles=True,
        )

    def get_grouped_call_stats_per__hour(self) -> Sequence[GroupedCallSecondsResult]:
        return self.count_and_sum_calls(
            self.iter_call_seconds_per_hour(),
            ['target', 'ou', 'org_unit', 'tenant', ''],
            group_by_titles=True,
        )

    def get_grouped_call_stats_per_time_of_day(self) -> Sequence[GroupedCallSecondsResult]:
        return self.count_and_sum_calls(
            self.iter_call_seconds_per_time_of_day(),
            ['target', 'ou', 'org_unit', 'tenant', ''],
            group_by_titles=True,
        )

    @staticmethod
    def find_first_active_leg(legs: Sequence[LegData], lower_ts: datetime, upper_ts: datetime = None, start: int = 0) \
      -> Tuple[int, bool]:
        """
        Get index of first possibly active leg between ``lower_ts`` and ``upper_ts``
        """
        res = start
        upper_ts = upper_ts or lower_ts
        for i in range(start, len(legs)):
            if legs[i].ts_start > upper_ts:
                break
            res = i
            if legs[i].ts_stop >= lower_ts:
                return i, True
        return res, False

    @staticmethod
    def get_active_legs(legs: Sequence[LegData], lower_ts: datetime, upper_ts: datetime = None, start: int = 0) \
      -> List[LegData]:
        """Get all active legs for time starting from index ``start``. Leg at first index must be active"""
        result: List[LegData] = []
        upper_ts = upper_ts or lower_ts
        for i in range(start, len(legs)):
            leg = legs[i]
            if leg.ts_start > upper_ts:
                return result
            if leg.ts_stop >= lower_ts:
                result.append(leg)
        return result

    def iter_legs_in_timerange_chunks(
        self,
        resolution_seconds=600,
        include_empty=False,
        allow_drift: int = 60,
    ) -> Iterator[Tuple[datetime, List[LegData]]]:
        """
        Yield a tuple for each timestamps of ``ts_start`` (aligned) and ``ts_stop`` split in equal
        chunks and the active legs for the time. Allow drift of ``allow_drift`` from start and end
        """
        ts_start, ts_stop = self.first_ts_start, self.last_ts_stop

        if not self.legs:
            return

        if include_empty and self.trim_times:
            ts_start = self.trim_times[0]
            ts_stop = self.trim_times[1]

        first_i = 0
        count = len(self.legs)
        drift = timedelta(seconds=allow_drift) if allow_drift else None

        find_first_active_leg, legs = self.find_first_active_leg, self.legs

        chunker = TimeRangeChunker(resolution_seconds=resolution_seconds)

        for ts in chunker.iter_chunks(ts_start, ts_stop):
            if drift:
                lower_ts, upper_ts = ts - drift, ts + drift
            else:
                lower_ts = upper_ts = ts

            first_i, found = find_first_active_leg(legs, lower_ts, upper_ts, first_i)

            legs = []
            i = first_i
            while i < count:  # continue to find all active legs
                if legs[i].ts_start > lower_ts:  # out of started legs
                    break
                if legs[i].ts_stop >= upper_ts:  # active
                    legs.append(legs[i])
                i += 1

            if include_empty or legs:
                yield ts, legs

    def grouped_legs_count_for_chunks(self, resolution_seconds=600) -> Sequence[Dict[str, Counter[datetime]]]:
        keys = 'ou', 'org_unit', 'tenant', ''
        result: List[DefaultDict[str, Counter[datetime]]] = [defaultdict(Counter) for _k in keys]

        chunker = TimeRangeChunker(resolution_seconds=resolution_seconds)
        for leg in self.legs:
            for ts in chunker.iter_chunks(leg.ts_start, leg.ts_stop):
                result[0][leg.titles.ou][ts] += 1
                result[1][leg.titles.org_unit][ts] += 1
                result[2][leg.tenant][ts] += 1
                result[3][''][ts] += 1

        return [dict(r) for r in result]


class LegRelatedDataPopulator():
    """
    Gather related data for legs, filter for available tenants, populate missing data connections
    """
    # TODO move arguments to class attributes

    @classmethod
    def populate_legs(
        cls,
        input_legs: Union[Iterable[Leg], models.QuerySet[Leg]],
        tenant=None,
        ou=None,
        filter_unit=None,
        valid_relations: 'ValidCustomerRelations' = None,
        trim_times=None,
    ) -> Tuple[List[LegData], 'LegCollectionRelatedData']:

        # filters: make sure to run list(legs) if it will be looped more than once
        if ou:
            input_legs = (leg for leg in input_legs if ou == leg.ou)
        if tenant:
            input_legs = (leg for leg in input_legs if tenant == leg.tenant)

        legs = cls.convert_leg_times(input_legs, trim_times=trim_times)

        filter_unit_ids = set()
        if filter_unit:
            filter_unit_ids = set(filter_unit.get_descendants(include_self=False).values_list('id', flat=True))

        org_unit_relations = LegsOrgUnitRelations(legs)
        related_data = LegCollectionRelatedData.get_for_legs(legs, org_unit_relations=org_unit_relations, valid_relations=valid_relations)

        guest_ou = 'guest'
        result = []
        get_titles = related_data.get_titles

        for leg in legs:

            if not leg.ts_stop or not leg.ts_start or leg.ts_start >= leg.ts_stop:  # remove noncomplete and trimmed legs
                continue

            leg.titles = get_titles(leg)

            org_unit_id = org_unit_relations.get_for_leg(leg)

            if filter_unit and org_unit_id not in filter_unit_ids:
                continue

            tenant_title = related_data.tenant_titles.get(leg.tenant)
            leg.org_unit = org_unit_id

            if valid_relations:
                if org_unit_id not in valid_relations.org_units:
                    leg.org_unit = None
                else:
                    tenant_title = related_data.customer_titles[related_data.units[org_unit_id].customer_id]
                if leg.ou not in valid_relations.ous:
                    leg.ou = guest_ou
                if leg.tenant not in valid_relations.tenants:
                    leg.tenant = ''
            else:
                if org_unit_id in related_data.units:
                    tenant_title = related_data.unit_titles.get(org_unit_id)
                elif leg.ou in related_data.ou_titles:
                    tenant_title = str(related_data.ou_titles[leg.ou])

            if tenant_title and tenant_title != related_data.tenant_titles.get(leg.tenant):
                leg.overridden_tenant_title = tenant_title

            if leg.call__cospace_id not in related_data.cospace:
                related_data.cospace[leg.call__cospace_id] = {'name': leg.call__cospace}

            result.append(leg)

        return result, related_data

    @staticmethod
    def localtime_legdata(leg: LegData,
                          trim_times: Optional[Tuple[datetime, datetime]] = None,
                          timezone: tzinfo = None,
                          ) -> LegData:

        if not timezone:
            timezone = get_current_timezone()

        if leg.ts_start.tzinfo is not timezone:
            leg.ts_start, leg.ts_stop = leg.ts_start.astimezone(timezone), leg.ts_stop.astimezone(timezone)

        if not trim_times:
            return leg

        duration = leg.duration

        if leg.ts_start < trim_times[0]:
            leg.ts_start = trim_times[0]
            duration = -1
        if leg.ts_stop > trim_times[1]:
            leg.ts_stop = trim_times[1]
            duration = -1

        if duration == -1:
            leg.duration = int((leg.ts_stop - leg.ts_start).total_seconds())

        return leg

    @staticmethod
    def convert_leg_times(
        legs: Iterable[Union[LegData, Leg, models.QuerySet[Leg]]],
        trim_times: Optional[Tuple[datetime, datetime]] = None,
    ) -> List[LegData]:

        if trim_times and len(trim_times) != 2:
            raise ValueError('trim_times should be a (ts_start, ts_stop) tuple. Was {}'.format(trim_times))

        if isinstance(legs, models.QuerySet):
            fields = [field.name for field in LegData.fields()]
            non_db_values = LegData.non_db_values()
            legs = [LegData(*row, *non_db_values) for row in legs.values_list(*fields)]
        elif isinstance(legs, list) and legs and isinstance(legs[0], Leg):
            legs = [leg.to_leg_data() for leg in legs]
        else:
            legs = [leg.to_leg_data() if isinstance(leg, Leg) else leg for leg in legs]

        timezone = get_current_timezone()
        localtime_legdata = LegRelatedDataPopulator.localtime_legdata

        leg_datas = cast(Iterator[LegData], legs)
        return [localtime_legdata(leg, trim_times, timezone) for leg in leg_datas if leg.ts_start and leg.ts_stop]


class LegCollectionRelatedData:
    """
    Get related data and titles for legs for faster lookup
    """
    def __init__(
        self,
        units: Dict[int, OrganizationUnit],
        users: Dict[str, str],
        valid_relations: 'ValidCustomerRelations' = None,
    ):
        self.units = units
        self.users = users

        self.cospace: Dict[str, dict] = {}
        self.ou_titles: Dict[str, str] = {}
        self.unit_titles: Dict[int, str] = {}
        self.tenant_titles: Dict[str, str] = {}
        self.customer_titles: Dict[int, str] = {}
        self.unit_customers: Dict[int, str] = {}

        self.valid_relations = valid_relations

        self.single_tenant = False
        if valid_relations and len(valid_relations.customers) > 1:
            self.single_tenant = True

    @classmethod
    def get_for_legs(
        cls,
        legs: Sequence[LegData],
        org_unit_relations: 'LegsOrgUnitRelations',
        valid_relations: 'ValidCustomerRelations' = None,
    ) -> 'LegCollectionRelatedData':
        units = cls.get_related_units_for_legs(legs, org_unit_relations, valid_relations=valid_relations)
        users = cls.get_leg_user_relations(legs)

        res = LegCollectionRelatedData(units, users, valid_relations)
        res.populate_title_maps()
        return res

    @staticmethod
    def get_related_units_for_legs(
        legs: Sequence[LegData],
        org_unit_relations: 'LegsOrgUnitRelations',
        valid_relations: 'ValidCustomerRelations' = None,
    ) -> Dict[int, OrganizationUnit]:

        unit_customer_kwargs = {}

        if valid_relations:
            unit_customer_kwargs = dict(customer__in=valid_relations.customers)

        unit_ids = {l.org_unit for l in legs if l.org_unit}
        unit_ids |= set(org_unit_relations.cospace_relations.values()) | set(org_unit_relations.user_relations.values())

        units = {u.pk: u for u in OrganizationUnit.objects.filter(**unit_customer_kwargs).filter(pk__in=unit_ids).select_related('parent', 'parent__parent')}

        return units

    @classmethod
    def get_leg_user_relations(cls, legs: Sequence[LegData]):
        """
        Get related users for legs
        """
        maybe_users = {l.target for l in legs if not l.is_guest and '@' in l.target}

        TOO_MANY_LEGS = 20000  # TODO temp table or better solutions for large WHERE IN

        if len(legs) > TOO_MANY_LEGS:
            users = {username: uid for username, uid in ds.User.objects.all().values_list('username', 'uid')}
        else:
            users = dict(ds.User.objects.filter(username__in=maybe_users).values_list('username', 'uid'))

        return users

    def get_titles(self, leg: LegData) -> LegRelatedTitles:
        tenant_name = leg.overridden_tenant_title or self.tenant_titles.get(leg.tenant) or 'Default'

        if leg.org_unit:
            unit_title = self.unit_titles.get(leg.org_unit)
            if not unit_title:
                unit_title = self.units[leg.org_unit].full_name if leg.org_unit in self.units else 'default'
        else:
            unit_title = 'default'

        if self.single_tenant:  # strip customer for single tenant
            ou_title = leg.ou
        else:
            ou_title = self.ou_titles.get(leg.ou) or 'Default > {}'.format(leg.ou or 'default')
            unit_title = '{} > {}'.format(tenant_name, unit_title)

        cospace = leg.call__cospace or 'default'
        if len(cospace) > 37 and cospace[-37] == ':' and cospace[-36:].count('-') == 4:  # pexip guid suffix
            cospace = cospace[:-37]

        return LegRelatedTitles(
            target=leg.target, cospace=cospace, tenant=tenant_name, ou=ou_title, org_unit=unit_title
        )

    def populate_title_maps(self):
        valid_relations = self.valid_relations

        if valid_relations:
            customer_titles = valid_relations.customers
            tenant_map = valid_relations.tenants if len(valid_relations.tenants) > 1 else {}
            ou_customer_map = valid_relations.ous if len(valid_relations.ous) > 1 else {}
        else:
            customer_map = {c.pk: c for c in Customer.objects.all()}
            customer_titles = {k: str(c) for k, c in customer_map.items()}
            tenant_map = {c.acano_tenant_id: str(c) for c in customer_map.values() if c.acano_tenant_id}
            tenant_map.update({c.pexip_tenant_id: str(c) for c in customer_map.values() if c.pexip_tenant_id})

            ou_customer_map = {
                k.shared_key: str(customer_map[k.customer])
                for k in CustomerKey.objects.filter(active=True)
                .exclude(shared_key__contains='.')
                .values_list('customer', 'shared_key', named=True)
                if k.shared_key
            }

        self.tenant_titles = tenant_map
        self.customer_titles = customer_titles
        self.ou_titles = {ou: '{} > {}'.format(customer, ou) for ou, customer in ou_customer_map.items()}
        self.unit_titles = {org_unit.pk: org_unit.full_name for org_unit in self.units.values()}
        self.unit_customers = {u.pk: customer_titles.get(u.customer_id) or 'Default' for u in self.units.values()}


class LegsOrgUnitRelations:
    """
    Find missing connections from leg cospace/users to org units that may have been
    changed after the statistics were written
    """

    TOO_MANY_LEGS = 20000  # TODO temp table or better solutions for large WHERE IN

    user_relations: Dict[str, int]
    cospace_owners: Dict[str, str]
    cospace_relations: Dict[str, int]

    def __init__(self, legs: Sequence[LegData]):
        self.legs = legs
        self.populate_relations()
        self.legs = None

    def get_for_leg(self, leg: LegData):
        return leg.org_unit \
               or self.user_relations.get(leg.target) \
               or self.cospace_relations.get(leg.call__cospace_id) \
               or self.user_relations.get(self.cospace_owners.get(leg.call__cospace_id))

    def populate_relations(self):
        """
        Get related org units for legs
        """

        cospace_ids_without_unit = {l.call__cospace_id for l in self.legs if l.call__cospace_id and not l.org_unit}
        user_relations, cospace_owners = self.get_user_relations(cospace_ids_without_unit)
        self.user_relations = user_relations
        self.cospace_owners = cospace_owners

        self.cospace_relations = self.get_cospace_relations(cospace_ids_without_unit)

    def get_user_relations(self, cospace_ids_without_unit: set):

        if not UserUnitRelation.objects.exists():
            return {}, {}

        cospace_owners = {}
        targets_without_unit = {l.target for l in self.legs if not l.org_unit}
        if len(self.legs) > self.TOO_MANY_LEGS:
            user_relations = {jid: unit for jid, unit in UserUnitRelation.objects.all().values_list('user_jid', 'unit') if jid in targets_without_unit}
            cospace_owners = {cid: username for cid, username in ds.CoSpace.objects.filter(owner__isnull=False).values_list('cid', 'owner__username') if cid in cospace_ids_without_unit}
        else:
            if ds.CoSpace.objects.exists():
                cospace_owners = dict(ds.CoSpace.objects.filter(owner__isnull=False, cid__in=cospace_ids_without_unit).values_list('cid', 'owner__username'))
            user_relations = dict(UserUnitRelation.objects.filter(user_jid__in=targets_without_unit | set(cospace_owners.values())).values_list('user_jid', 'unit'))

        return user_relations, cospace_owners

    def get_cospace_relations(self, cospace_ids_without_unit: set):

        if not CoSpaceUnitRelation.objects.exists():
            return {}

        if self.TOO_MANY_LEGS:
            cospace_relations = {cid: unit_id
                                 for cid, unit_id in CoSpaceUnitRelation.objects.all().values_list('provider_ref', 'unit')
                                 if cid in cospace_ids_without_unit}
        else:
            cospace_relations = dict(CoSpaceUnitRelation.objects.filter(provider_ref__in=cospace_ids_without_unit).values_list('provider_ref', 'unit'))
        return cospace_relations


populate_legs = LegRelatedDataPopulator.populate_legs


def get_valid_relations(customers=None, user=None) -> ValidCustomerRelations:
    from organization.models import OrganizationUnit
    from customer.models import Customer

    if customers is None and not user:
        return ValidCustomerRelations({}, set(), {}, {})

    if customers is None:
        customers = []
    if user:
        customers.extend(Customer.objects.get_for_user(user))

    org_units = OrganizationUnit.objects.filter(customer__in=customers).values_list('id', flat=True)
    tenants = {}
    ous = {}

    for customer in customers:
        ous.update({k: customer for k in customer.get_non_domain_keys()})
        tenants[customer.acano_tenant_id] = str(customer)
        if customer.pexip_tenant_id:
            tenants[customer.pexip_tenant_id] = str(customer)

    return ValidCustomerRelations(ous, set(org_units), tenants, {c.pk: str(c) for c in customers})


def merge_duplicate_legs(legs, max_diff=30, allow_internal_merge=None, default_domain=''):
    result = []
    duplicates = {}
    rewrite_calls = {}

    diff_delta = timedelta(seconds=max_diff or 30)
    duplicates_overridden = set()

    internal_domains = get_internal_domains()

    if allow_internal_merge is None:
        # endpoint calls may be tracked both from remote and local end
        allow_internal_merge = set(Server.objects.filter(type=Server.ENDPOINTS).values_list('id', flat=True))
    else:
        allow_internal_merge = {getattr(s, 'id', s) for s in allow_internal_merge}

    def iter_back(leg, lst):

        ts_start_limit = leg.ts_start - diff_delta
        ts_stop_limit = leg.ts_stop + diff_delta

        for l in reversed(lst):

            if l.server_id == leg.server_id and leg.server_id not in allow_internal_merge:
                continue

            if l.pk == leg.pk:
                continue

            if l.ts_start < ts_start_limit:
                break
            if l.ts_stop > ts_stop_limit:
                continue

            yield l

    def combine_related_data(src, dst):
        # add matched data
        if src.org_unit_id and not dst.org_unit_id:
            dst.org_unit_id = src.org_unit_id
        if src.ou and not dst.ou:
            dst.ou = src.ou
        if src.tenant and not dst.tenant:
            dst.tenant = src.tenant
        if src.endpoint_id and not dst.endpoint_id:
            dst.endpoint_id = src.endpoint_id
        if src.is_guest and not dst.is_guest:
            dst.is_guest = True

        # prefer call with cospace_id
        if src.call.cospace_id and not dst.call.cospace_id:
            rewrite_calls[dst.call_id] = src.call
            rewrite_calls.pop(src.call_id, None)
        elif src.call_id not in rewrite_calls:
            rewrite_calls[src.call_id] = dst.call

        if rewrite_calls.get(dst.call_id) in duplicates_overridden:
            duplicates_overridden.add(rewrite_calls[dst.call_id])

    def check_false_positive(leg, l):
        "check if both legs should be included. e.g. one leg is matched in CMS but both legs in vcs have same uris"
        if len(duplicates.get(l.pk, ())) != 2 or l.call_id in duplicates_overridden:
            return

        for d_index, d in enumerate(duplicates.get(l.pk, [])):
            if not (d.server_id == leg.server_id and d.call_id == leg.call_id):
                continue

            duplicates_overridden.add(l.call_id)
            duplicates_overridden.add(leg.call_id)
            if l.target == leg.target:  # duplicate is other part. replace
                leg, duplicates[l.pk][d_index] = d, leg
            combine_related_data(leg, l)
            combine_related_data(l, leg)
            return leg

    for leg in legs:

        if not leg.call_id or not leg.ts_start or not leg.ts_stop:
            continue

        is_duplicate = False

        for l in iter_back(leg, result):

            targets = [rewrite_internal_domains(clean_target(t), internal_domains=internal_domains) for t in [leg.remote, leg.local, l.remote, l.local]]

            with_domains = {t.split('@')[0]: t for t in targets if '@' in t}
            for i, without_domain in enumerate(targets):
                if '@' in without_domain:
                    continue
                if without_domain in with_domains:
                    targets[i] = with_domains[without_domain]

            if sorted(targets[0:2]) == sorted(targets[2:4]):
                # duplicate from same call and server. check so that both parts are included even though uris are the same
                new_leg = check_false_positive(leg, l)
                if new_leg:
                    leg = new_leg
                    continue

                duplicates.setdefault(l.pk, [l]).append(leg)
                is_duplicate = True

                combine_related_data(leg, l)
                break

        if not is_duplicate:
            leg.target = rewrite_internal_domains(leg.target, default_domain=default_domain, internal_domains=internal_domains)
            result.append(leg)

    for leg in result:
        if leg.call_id in rewrite_calls:
            leg.call = rewrite_calls[leg.call_id]

    return [leg.to_leg_data() for leg in result], duplicates


def clean_duplicates(server, legs, max_diff=10, default_domain=''):

    duplicates = merge_duplicate_legs(legs, max_diff=max_diff, allow_internal_merge=[server], default_domain=default_domain)[1]

    for legs in duplicates.values():

        if not isinstance(legs, list):
            raise ValueError('Invalid data type: {}', type(legs), legs)

        if len({l.pk for l in legs}) != len(legs):
            raise ValueError(_('Duplicate ids in leg list'), legs)

        changed = False
        if not legs[0].guid:
            guids = [l.guid for l in legs[1:] if l.guid]
            if guids:
                legs[0].guid = guids[0]
                changed = True

        calls = sorted(legs, key=lambda x: x.call_id)
        if legs[0].call_id != calls[-1].call_id:
            legs[0].call = calls[-1].call
            changed = True

        if not legs[0].direction:
            directions = [l.direction for l in legs[1:] if l.direction]
            if directions:
                legs[0].direction = directions[0]
                changed = True

        if changed:
            legs[0].save()

        Leg.objects.filter(pk__in={l.pk for l in legs[1:]}).delete()

