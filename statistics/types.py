import dataclasses
from calendar import timegm
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Tuple, Dict, Sequence, Optional, Counter, DefaultDict, Set, Mapping

from django.utils.timezone import utc
from typing_extensions import TypeAlias


@dataclass
class LegData:
    """
    Data container for statistics leg. Uses slots for lower memory usage, but which requires it
    to be initialized without default values. Initialize with
    ```
    Leg.objects.values_list(LegData.fields())
    legs = [LegData(*leg, *LegData.non_db_fields()) for leg in legs]
    ```
    """
    id: int
    ts_start: datetime
    ts_stop: datetime
    duration: int
    target: str
    tenant: str
    ou: str
    call__cospace_id: str
    guid: str
    call__cospace: str
    call_id: int
    is_guest: bool
    org_unit: Optional[int]
    local: str
    remote: str

    overridden_tenant_title: Optional[str]
    titles: Optional['LegRelatedTitles']

    __slots__ = tuple(__annotations__)  # type: ignore  # noqa  # __slots__ doesn't allow default values

    @staticmethod
    def timegm(dt: datetime):
        if dt.tzinfo and dt.tzinfo is not utc:
            return int(timegm(dt.replace(tzinfo=utc).timetuple()))
        return int(timegm(dt.timetuple()))

    @staticmethod
    def non_db_fields():
        return ('overridden_tenant_title', 'titles')

    @staticmethod
    def non_db_values():
        return ('', None)

    @staticmethod
    def fields():
        non_db_fields = LegData.non_db_fields()
        return [f for f in dataclasses.fields(LegData) if f.name not in non_db_fields]


TimeSpanStartDurationTuple = Tuple[str, int]
LegTimestepDuration = Tuple[LegData, Iterable[TimeSpanStartDurationTuple]]


@dataclass
class DurationSecondsResult:
    seconds: int = 0
    start_call_count: int = 0

    def __getitem__(self, item):
        if item == 0:
            return self.seconds
        if item == 1:
            return self.start_call_count
        raise IndexError()


GroupedCallSecondsResult = Dict[str, Dict[str, DurationSecondsResult]]
CallSecondsResult = Dict[str, Dict[str, Counter[str]]]


@dataclass
class LegRelatedTitles:
    target: str
    cospace: str
    tenant: str
    ou: str
    org_unit: str
    __slots__ = __annotations__  # type: ignore  # noqa


@dataclass
class ValidCustomerRelations:
    ous: Dict[str, str]
    org_units: set
    tenants: Dict[str, str]
    customers: Dict[int, str]


@dataclass
class LegSummaryResultRow:
    duration: float = 0
    guest_duration: float = 0
    participant_count: int = 0
    call_count: int = 0
    related_id: str = ''


@dataclass
class LegSummaryResult:
    cospace: Dict[str, LegSummaryResultRow]
    ou: Dict[str, LegSummaryResultRow]
    user: Dict[str, LegSummaryResultRow]
    org_unit: Dict[str, LegSummaryResultRow]

    cospace_total: LegSummaryResultRow
    ou_total: LegSummaryResultRow
    user_total: LegSummaryResultRow
    org_unit_total: LegSummaryResultRow

    target_group: Optional[Dict[str, LegSummaryResultRow]] = None
    target_group_total: Optional[LegSummaryResultRow] = None

    def dict(self):
        """return recursive dicts for all values"""
        return dataclasses.asdict(self)

    def compact_dict(self):
        """return data rows as tuples, and <field>_total as dicts"""
        def _maybe_tuple(value):
            if isinstance(value, dict):
                return {k: dataclasses.astuple(v) for k, v in value.items()}
            elif isinstance(value, LegSummaryResultRow):
                return dataclasses.asdict(value)
            return value

        return {k.name: _maybe_tuple(getattr(self, k.name)) for k in dataclasses.fields(self)}


@dataclass
class LegSummaryTempRow(LegSummaryResultRow):
    call_counter: Set[int] = None

    def finalize(self):
        return LegSummaryResultRow(
            duration=float('%.02f' % (self.duration / (60 * 60.0))),
            guest_duration=float('%.02f' % (self.duration / (60 * 60.0))),
            participant_count=self.participant_count,
            call_count=len(self.call_counter or ()),
            related_id=self.related_id,
        )


@dataclass
class LegSummaryTemp:
    cospace: DefaultDict[str, LegSummaryTempRow]
    ou: DefaultDict[str, LegSummaryTempRow]
    user: DefaultDict[str, LegSummaryTempRow]
    org_unit: DefaultDict[str, LegSummaryTempRow]

    def finalize(self):
        def _finalize_dict(dct: Mapping[str, LegSummaryTempRow]):
            return {k: v.finalize() for k, v in sorted(dct.items())}

        def _sum_dict(dct: Mapping[str, LegSummaryResultRow]):
            result = LegSummaryResultRow(
                sum(row.duration for row in dct.values()),
                sum(row.guest_duration for row in dct.values()),
                sum(row.participant_count for row in dct.values()),
                sum(row.call_count for row in dct.values()),
            )
            return result

        cospace = _finalize_dict(self.cospace)
        ou = _finalize_dict(self.ou)
        user = _finalize_dict(self.user)
        org_unit = _finalize_dict(self.org_unit)

        return LegSummaryResult(
            cospace=cospace,
            ou=ou,
            user=user,
            org_unit=org_unit,
            cospace_total=_sum_dict(cospace),
            ou_total=_sum_dict(ou),
            user_total=_sum_dict(user),
            org_unit_total=_sum_dict(org_unit),
        )

