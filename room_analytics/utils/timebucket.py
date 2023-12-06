from datetime import datetime
from typing import Dict, Sequence, List

from typing_extensions import Literal

from room_analytics.utils.time import get_days_between, get_hours_between, get_dates_between


class Bucket:
    time_format: str

    @staticmethod
    def time_bucket_to_result_key(day_str):
        return day_str

    @staticmethod
    def get_all_intervals(ts_start: datetime,
                          ts_stop: datetime,
                          only_days: Sequence[int] = None,
                          only_hours : Sequence[int] = None
                          ) -> List[str]:
        raise NotImplementedError()

    @staticmethod
    def transform_bucket_results(results: Dict[str, List]):
        pass


class ValuePerHourIntervalMixin:
    time_format: str

    @classmethod
    def get_all_intervals(cls, ts_start, ts_stop, only_days=None, only_hours=None):
        return [ts.strftime(cls.time_format) for ts in get_hours_between(ts_start, ts_stop, only_days=only_days)]


class ByDayBucket(ValuePerHourIntervalMixin, Bucket):
    """one value each hour and day, group by day of week"""
    time_format = '%Y-%m-%d-%H %u'

    @staticmethod
    def time_bucket_to_result_key(day_str):
        return int(day_str.split(' ', 1)[1])

    @staticmethod
    def transform_bucket_results(results: Dict[str, List]):
        days = {i: day for i, day in enumerate('Sun Mon Tue Wed Thu Fri Sat Sun'.split())}
        results.x = [days[day] for day in results.x]


class ByDaySingleBucket(Bucket):
    """one value per day of week"""
    time_format = '%u'

    @classmethod
    def get_all_intervals(cls, ts_start, ts_stop, only_days=None, only_hours=None):
        return list(set(d.isoweekday() for d in get_dates_between(ts_start, ts_stop, only_days=only_days)))

    @staticmethod
    def time_bucket_to_result_key(day_str):
        return int(day_str)

    @staticmethod
    def transform_bucket_results(results: Dict[str, List]):
        days = {i: day for i, day in enumerate('Sun Mon Tue Wed Thu Fri Sat Sun'.split())}
        results.x = [days[day] for day in results.x]


class ByDateBucket(ValuePerHourIntervalMixin, Bucket):
    """one value each hour and day, group by date"""
    time_format = '%Y-%m-%d %H'

    @staticmethod
    def time_bucket_to_result_key(day_str):
        return day_str.split(' ', 1)[0]


class ByDateSingleBucket(Bucket):
    """one value each day, single value (as list)"""
    time_format = '%Y-%m-%d'

    @staticmethod
    def get_all_intervals(ts_start, ts_stop, only_days=None, only_hours=None):
        return [str(d) for d in get_dates_between(ts_start, ts_stop, only_days=only_days)]

    @staticmethod
    def time_bucket_to_result_key(day_str):
        return day_str


class NowBucket(Bucket):
    """max value (as list)"""
    time_format = 'x'

    @staticmethod
    def time_bucket_to_result_key(day_str):
        return 'Now'

    @staticmethod
    def get_all_intervals(ts_start, ts_stop, only_days=None, only_hours=None):
        return []


class HourSingleBucket(Bucket):
    """one value each hour of day, single value (as list)"""
    time_format = '%H'

    @staticmethod
    def time_bucket_to_result_key(hour_str):
        return '{}:00'.format(hour_str)

    @staticmethod
    def get_all_intervals(ts_start, ts_stop, only_days=None, only_hours=None):
        result = range(min(ts_start.hour, ts_stop.hour), max(ts_start.hour, ts_stop.hour) + 1)
        if only_hours:
            return [hour for hour in result if hour in only_hours]
        return list(result)


class HourBucket(ValuePerHourIntervalMixin, Bucket):
    """one value each hour and day, group by hour of day"""
    time_format = '%Y-%m-%d %H'

    @staticmethod
    def time_bucket_to_result_key(hour_str):
        return '{}:00'.format(hour_str.split(' ', 1)[1])


class BucketType:
    day = ByDayBucket
    day_single = ByDaySingleBucket
    date = ByDateBucket
    date_single = ByDateSingleBucket
    now = NowBucket
    hour_single = HourSingleBucket
    hour = HourBucket


BUCKET_TYPES = Literal['day', 'day_single', 'date', 'date_single', 'now', 'hour_single', 'hour']

