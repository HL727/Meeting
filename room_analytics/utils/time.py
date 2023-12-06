from datetime import timedelta

from django.utils.timezone import localtime

from statistics.utils.time import TimeRangeChunker


def get_hours_between(ts_start, ts_stop, only_days=None, only_hours=None):

    result = []
    for ts in TimeRangeChunker(60 * 60).iter_chunks(ts_start, ts_stop, open_begin=True):
        if only_hours and ts.hour not in only_hours:
            continue
        if only_days and ts.isoweekday() not in only_days:
            continue
        result.append(ts)

    return result


def get_dates_between(ts_start, ts_stop, only_days=None):

    d = localtime(ts_start).date()
    d2 = localtime(ts_stop).date()

    day = timedelta(days=1)

    result = []
    while d <= d2:
        if not only_days or d.isoweekday() in only_days:
            result.append(d)
        d += day
    return result


def get_days_between(ts_start, ts_stop, only_days=None):
    "<year>-<week> <day_number>"

    cur_date = localtime(ts_start).date()
    num_days = (ts_stop.date() - ts_start.date()).days

    result = []
    for _i in range(min(num_days + 1, 7)):
        cal = cur_date.isocalendar()
        if not only_days or cal[2] in only_days:
            result.append('{}-{} {}'.format(*cal))
        cur_date += timedelta(days=1)

    return result
