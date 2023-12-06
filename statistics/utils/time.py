from datetime import timedelta, datetime
from typing import Optional, Iterator, Union

from statistics.models import Leg
from statistics.types import LegData, TimeSpanStartDurationTuple


class TimeRangeChunker:

    def __init__(self, resolution_seconds=600):

        self.resolution_seconds = resolution_seconds
        self.step = timedelta(seconds=resolution_seconds)

        self._last_started_step: Optional[datetime] = None
        self._last_inclusive_step: Optional[datetime] = None

    def _reuse_last_first_step(self, ts_start: datetime, open_begin=False) -> Optional[datetime]:
        """Reuse last first value to skip calculations in tight loops"""
        if not self._last_started_step:  # first run, no cached value
            return

        if open_begin and self._last_started_step and ts_start < self._last_inclusive_step:
            return self._last_started_step

        if ts_start <= self._last_inclusive_step:
            return self._last_inclusive_step

    def get_first_step(self, ts_start: datetime, open_begin=False) -> datetime:
        """Reuse last first value to skip calculations"""
        last_value = self._last_started_step and self._reuse_last_first_step(ts_start, open_begin=open_begin)
        if last_value:
            return last_value

        if ts_start.microsecond:
            ts_start = ts_start.replace(microsecond=0)

        diff = LegData.timegm(ts_start) % self.resolution_seconds
        if diff:
            diff = self.resolution_seconds - diff

        next_step = ts_start + timedelta(seconds=diff)
        started_step = next_step - self.step

        self._last_inclusive_step = next_step
        self._last_started_step = started_step

        if open_begin and next_step > ts_start:
            return started_step

        return next_step

    def iter_chunks(
        self,
        ts_start: datetime,
        ts_stop: datetime,
        open_begin=False,
        open_end=False,
    ) -> Iterator[datetime]:
        """
        Yield each timestamp of ``ts_start`` (aligned, inclusive) and ``ts_stop`` split in equal chunks
        Include opened chunk before if ``open_begin``, and chunk after the last opened if ``open_end``
        """
        res = self.step

        ts = self.get_first_step(ts_start, open_begin=open_begin)
        if ts > ts_stop and not open_end:
            return

        if ts_stop.microsecond:
            ts_stop = ts_stop.replace(microsecond=0)

        while True:
            yield ts
            ts = ts + res
            if ts > ts_stop:
                break

        if open_end and ts > ts_stop:
            yield ts

    def iter_chunks_duration(
        self,
        ts_start: datetime,
        ts_stop: datetime,
        group_dateformat='%Y-%m-%d %H:%M',
    ) -> Iterator[TimeSpanStartDurationTuple]:
        """
        Yield a tuple for each timestamps of ``ts_start`` (aligned) and ``ts_stop`` split in equal
        chunks and a calculated duration between the current step and next
        """

        ts = self.get_first_step(ts_start, open_begin=True)

        if ts < ts_start:  # part of first step
            next_step = min(ts_stop, ts + self.step)
            yield ts.strftime(group_dateformat), (next_step - ts_start).total_seconds()
            if next_step >= ts_stop:
                return

        check_end = ts_stop - self.step
        for ts in self.iter_chunks(ts_start, ts_stop):  # full steps
            if ts > check_end:  # calculate last step
                yield ts.strftime(group_dateformat), (min(ts_stop, ts + self.step) - ts).total_seconds()
            else:
                yield ts.strftime(group_dateformat), self.resolution_seconds


def get_capped_duration(leg: Union[LegData, Leg], ts_start: datetime = None, ts_stop: datetime = None):

    cur_ts_start = ts_start if ts_start and ts_start > leg.ts_start else leg.ts_start
    cur_ts_stop = ts_stop if ts_stop and ts_stop < leg.ts_stop else leg.ts_stop

    if cur_ts_start is not leg.ts_start or cur_ts_stop is not leg.ts_stop:
        return (cur_ts_stop - cur_ts_start).total_seconds()
    return leg.duration
