import dataclasses
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Iterable, Tuple, List, Sequence, Dict, Union, Iterator, TYPE_CHECKING, Any

from django.db.models import QuerySet
from django.utils.timezone import localtime
from typing_extensions import DefaultDict

from room_analytics.models import EndpointHeadCount
from room_analytics.graph import get_layout, get_graph
from endpoint.consts import DEFAULT_CAPACITY
from room_analytics.utils.timebucket import BucketType, Bucket, BUCKET_TYPES

if TYPE_CHECKING:
    from endpoint.models import Endpoint


@dataclass
class Points:
    x: List[datetime]
    y: List[int]


@dataclass
class EndpointHeadCountData:
    title: str
    id: int
    x: List[Any]
    y: List[int]
    capacity: int
    type: str


def get_head_count_values(
    endpoints: Union['QuerySet[Endpoint]', Sequence['Endpoint']],
    ts_start: datetime,
    ts_stop: datetime,
    as_percent=False,
) -> List[EndpointHeadCountData]:
    """
    Get all values between `ts_start` and `ts_stop` grouped by endpoint
    """

    if not isinstance(endpoints, QuerySet):
        endpoint_values = endpoints
    else:
        endpoint_values = endpoints.values_list('title', 'room_capacity', 'pk', named=True)

    endpoints_data = {e.pk: e for e in endpoint_values}

    head_count = EndpointHeadCount.objects.filter(ts__gte=ts_start, ts__lte=ts_stop, endpoint__in=endpoints)

    points: DefaultDict[int, Points] = defaultdict(lambda: Points([], []))

    head_counts: Sequence[Tuple[int, datetime, int]] = list(
        head_count.order_by('ts').exclude(value=-1).values_list('endpoint', 'ts', 'value')
    )

    for endpoint_id, ts, count in head_counts:

        points[endpoint_id].x.append(localtime(ts))
        capacity = endpoints_data[endpoint_id].room_capacity or DEFAULT_CAPACITY

        if as_percent:
            points[endpoint_id].y.append(round(count / capacity * 100))
        else:
            points[endpoint_id].y.append(count)

    result = []
    for endpoint_id, values in points.items():
        result.append(EndpointHeadCountData(
            title=endpoints_data[endpoint_id].title,
            id=endpoint_id,
            x=values.x,
            y=values.y,
            capacity=endpoints_data[endpoint_id].room_capacity,
            type='histogram',
        ))

    return result


class GroupedHeadCountStats:

    def __init__(
        self,
        endpoints: Union['QuerySet[Endpoint]', Sequence['Endpoint']],
        ts_start: datetime,
        ts_stop: datetime,
        only_hours: Union[str, Sequence[int]] = None,
        only_days=None,
    ):

        self.endpoints = endpoints
        self.ts_start = ts_start
        self.ts_stop = ts_stop

        self.filter_hours = set(self._split_int_ranges_str(only_hours))
        self.filter_days = set(self._split_int_ranges_str(only_days))

        self.cached = {}

    def get_values(self) -> List[EndpointHeadCountData]:
        return get_head_count_values(self.endpoints, self.ts_start, self.ts_stop, as_percent=False)

    @staticmethod
    def _split_int_ranges_str(value_str: Union[Sequence[int], str]) -> List[int]:
        """Return list of all numbers from string based ranges, e.g. 1-4,8-10"""
        result = []
        if not value_str:
            return []

        lst = value_str.split(',') if isinstance(value_str, str) else list(value_str)
        if all(isinstance(v, int) for v in lst):
            return lst

        for v in lst:
            v = v.replace(' ', '')
            if '-' in v:  # e.q. 1-10
                start, stop = list(map(int, v.split('-', 1)))
                result.extend(range(start, stop + 1))
            else:
                result.append(int(v))
        return result

    @staticmethod
    def fill_continous_hours(x: Iterable[datetime], y: Iterable[int]) -> Iterator[Tuple[datetime, int]]:
        continue_limit = timedelta(hours=4)
        one_hour = timedelta(hours=1)

        last = None
        last_value = None

        for ts, value in zip(x, y):

            if not last:
                last = ts
                last_value = value

            diff = (last - ts)

            if diff > one_hour and diff < continue_limit:
                cur = last + one_hour
                while cur < ts:
                    yield cur, last_value
                    cur += one_hour
            elif diff > continue_limit:  # add 0-count
                yield last + one_hour, 0

            last, last_value = ts, value
            yield ts, value

    def bucket_endpoint_head_counts(
        self,
        by: BUCKET_TYPES = 'hour',
        as_percent=False,
        ignore_empty=False,
        fill_gaps=True,
    ) -> List[EndpointHeadCountData]:
        """
        bucket values according to `BucketType.<by>` and aggregate statistics from the max
        value from every bucket
        """
        bucket = getattr(BucketType, by)

        all_intervals = []
        if fill_gaps:
            all_intervals = bucket.get_all_intervals(self.ts_start, self.ts_stop,
                                                     only_days=self.filter_days, only_hours=self.filter_hours)

        result = []

        for values in self.get_values():

            grouped = self.summarize_bucket(values, bucket, all_intervals=all_intervals, as_percent=as_percent,
                                            fill_gaps=fill_gaps, ignore_empty=ignore_empty)

            bucket.transform_bucket_results(grouped)
            result.append(grouped)

        return result

    def summarize_bucket(
        self,
        values: EndpointHeadCountData,
        bucket: Bucket,
        all_intervals,
        as_percent=False,
        ignore_empty=False,
        fill_gaps=True,
    ) -> EndpointHeadCountData:
        """
        Get max value for each bucket value
        """
        per_interval = defaultdict(list)

        for ts, value in self.fill_continous_hours(values.x, values.y):  # group by date and interval

            if self.filter_hours and ts.hour not in self.filter_hours:
                continue
            if self.filter_days and ts.isoweekday() not in self.filter_days:
                continue
            if ignore_empty and value <= 0:
                continue

            interval_str = ts.strftime(bucket.time_format)
            per_interval[interval_str].append(value)

        if fill_gaps and not ignore_empty:
            for interval_str in all_intervals:
                if interval_str not in per_interval:
                    per_interval[interval_str] = [0]

        interval_group = defaultdict(list)

        for interval_str, counts in per_interval.items():  # max value for each interval
            if as_percent:
                capacity = values.capacity or DEFAULT_CAPACITY
                cur = min(100, round(max(counts) / capacity * 100))
            else:
                cur = max(counts)

            result_key = bucket.time_bucket_to_result_key(interval_str)
            interval_group[result_key].append(cur)

        x = [interval for interval in sorted(interval_group) for h in range(len(interval_group[interval]))]
        y = [v for interval in sorted(interval_group) for v in interval_group[interval]]

        return dataclasses.replace(values, x=x, y=y)

    def get_invididual_graph(
        self,
        by: BUCKET_TYPES = 'hour',
        as_percent=False,
        ignore_empty=False,
        fill_gaps=True,
        as_image=False,
        as_json=False,
    ):
        """
        Get bar for each endpoint max value per bucket step
        """
        from plotly.graph_objs import Figure, Scatter, Bar

        data = self.bucket_endpoint_head_counts(by, as_percent=as_percent, ignore_empty=ignore_empty, fill_gaps=fill_gaps)

        show_capacity_lines = False
        if len(self.endpoints) == 1 and not as_percent and data and data[0].x:
            show_capacity_lines = True

        layout = get_layout(data, as_image=as_image, showlegend=not show_capacity_lines)

        fig = Figure(layout=layout)
        for values in data:
            fig.add_trace(Bar(x=values.x, y=values.y, name=values.title))

        if show_capacity_lines:
            fig.add_trace(Scatter(mode='lines', x=[data[0].x[0], data[0].x[-1]], y=[self.endpoints[0].room_capacity or DEFAULT_CAPACITY] * 2, name='Max'))

        return get_graph(fig, as_image=as_image, as_json=as_json)

    def get_graph(
        self,
        by: BUCKET_TYPES = 'hour',
        as_percent=False,
        ignore_empty=False,
        fill_gaps=True,
        as_image=False,
        as_json=False,
    ):
        """
        Get box graph for all values per bucket step
        """
        from plotly.graph_objs import Figure, Scatter, Box

        data = self.bucket_endpoint_head_counts(by, as_percent=as_percent, ignore_empty=ignore_empty, fill_gaps=fill_gaps)

        x = [x for values in data for x in values.x]
        y = [y for values in data for y in values.y]

        layout = get_layout(data, as_image=as_image)

        fig = Figure(data=Box(x=x, y=y, boxpoints=False), layout=layout)

        if len(self.endpoints) == 1 and not as_percent and x:
            fig.add_trace(Scatter(mode='lines', x=[x[0], x[-1]], y=[self.endpoints[0].room_capacity or DEFAULT_CAPACITY] * 2))

        return get_graph(fig, as_image=as_image, as_json=as_json)

    @staticmethod
    def get_max_values(endpoint_data: Sequence[EndpointHeadCountData]) -> Tuple[List[Any], List[int]]:
        """
        Get max value for each bucket, single serie
        """
        all_x = [x for values in endpoint_data for x in values.x]
        all_y = [y for values in endpoint_data for y in values.y]

        result = {}
        for x, y in zip(all_x, all_y):
            if x not in result:
                result[x] = y
            else:
                result[x] += y

        sum_x, sum_y = [], []
        for k in sorted(result):
            sum_x.append(k)
            sum_y.append(result[k])

        return sum_x, sum_y

    def get_max_values_graph(
        self,
        by: BUCKET_TYPES = 'hour',
        as_percent=False,
        ignore_empty=False,
        fill_gaps=True,
        as_image=False,
        as_json=False,
    ):
        """
        Get line graph of each max value over all endpoints per bucket step `by`
        """
        from plotly.graph_objs import Figure, Scatter

        endpoint_data = self.bucket_endpoint_head_counts(by, as_percent=as_percent, ignore_empty=ignore_empty, fill_gaps=fill_gaps)

        x, y = self.get_max_values(endpoint_data)

        layout = get_layout(endpoint_data, as_image=as_image)

        fig = Figure(data=Scatter(mode='lines', x=x, y=y), layout=layout)

        if len(self.endpoints) == 1 and not as_percent and x:
            fig.add_trace(Scatter(mode='lines', x=[x[0], x[-1]], y=[self.endpoints[0].room_capacity or DEFAULT_CAPACITY] * 2))

        return get_graph(fig, as_image=as_image, as_json=as_json)

    @staticmethod
    def get_sum_max_values(endpoint_data: Sequence[EndpointHeadCountData]) -> Tuple[List[Any], List[int]]:
        """
        Get sum of max values for each bucket step as a single serie
        """
        all_x = [x for values in endpoint_data for x in values.x]
        all_y = [y for values in endpoint_data for y in values.y]

        result = {}
        for x, y in zip(all_x, all_y):
            if x not in result:
                result[x] = y
            else:
                result[x] += y

        sum_x, sum_y = [], []
        for k in sorted(result):
            sum_x.append(k)
            sum_y.append(result[k])

        return sum_x, sum_y

    def get_sum_max_values_graph(
        self,
        by: BUCKET_TYPES = 'hour',
        as_percent=False,
        ignore_empty=False,
        fill_gaps=True,
        as_image=False,
        as_json=False,
    ):
        """
        Get line graph of sum of max value over all endpoints per bucket step `by`
        """
        from plotly.graph_objs import Figure, Scatter

        endpoint_data = self.bucket_endpoint_head_counts(by, as_percent=as_percent, ignore_empty=ignore_empty, fill_gaps=fill_gaps)

        x, y = self.get_sum_max_values(endpoint_data)

        layout = get_layout(endpoint_data, as_image=as_image)

        fig = Figure(data=Scatter(mode='lines', x=x, y=y), layout=layout)

        if len(self.endpoints) == 1 and not as_percent and x:
            fig.add_trace(Scatter(mode='lines', x=[x[0], x[-1]], y=[self.endpoints[0].room_capacity or DEFAULT_CAPACITY] * 2))

        return get_graph(fig, as_image=as_image, as_json=as_json)

    def get_all_graphs(self, as_percent=False, ignore_empty=False, fill_gaps=True, as_json=True, as_image=False):

        kwargs = dict(as_percent=as_percent, ignore_empty=ignore_empty, fill_gaps=fill_gaps, as_image=as_image, as_json=as_json)

        if not self.get_values():
            return self.empty_all_graphs()

        return {
            'per_hour': self.get_graph('hour', **kwargs),
            'per_day': self.get_graph('day', **kwargs),
            'per_date': self.get_graph('date', **kwargs),
        }

    def get_all_graphs_max_values(self, as_percent=False, ignore_empty=False, fill_gaps=True, as_json=True, as_image=False):

        kwargs = dict(as_percent=as_percent, ignore_empty=ignore_empty, fill_gaps=fill_gaps, as_image=as_image, as_json=as_json)

        if not self.get_values():
            return self.empty_all_graphs()

        return {
            'per_hour': self.get_max_values_graph('hour', **kwargs),
            'per_day': self.get_max_values_graph('day', **kwargs),
            'per_date': self.get_max_values_graph('date', **kwargs),
        }

    def get_all_individual_graphs(self, as_percent=False, ignore_empty=False, fill_gaps=True, as_json=True, as_image=False):

        kwargs = dict(as_percent=as_percent, ignore_empty=ignore_empty, fill_gaps=fill_gaps, as_image=as_image, as_json=as_json)

        if not self.get_values():
            return self.empty_all_graphs()

        return {
            'per_hour': self.get_invididual_graph('hour_single', **kwargs),
            'per_day': self.get_invididual_graph('day_single', **kwargs),
            'per_date': self.get_invididual_graph('date_single', **kwargs),
        }

    @staticmethod
    def empty_all_graphs():
        return {
            'empty': True,
            'per_hour': {},
            'per_day': {},
            'per_date': {},
        }
