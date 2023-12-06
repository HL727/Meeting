import json
import re
from datetime import timedelta
from typing import Sequence

from dateutil.rrule import rrulestr
from django.utils.timezone import now
from ics import Calendar, Event
from ics.parsers.event_parser import EventParser
from ics.parsers.icalendar_parser import CalendarParser
from ics.parsers.parser import option
from ics.utils import iso_to_arrow, arrow_to_iso

from meeting.models import RecurringMeeting, Meeting


def monkey_patch_ics():
    # TODO replace ics module

    # remove required for PRODID
    del CalendarParser.parse_prodid.options

    def _add(fn):
        setattr(EventParser, fn.__name__, fn)

    # Save extra tags

    @_add
    def parse_x_microsoft_onlinemeetingconflink(event, line):
        """
        add skype support to ics module.
        note that event.skype raises AttributeError if not availible in file (i.e. use hasattr)
        """
        if line:
            event.skype = line.value

    @_add
    def parse_x_microsoft_locations(event, line):
        if line:
            try:
                event.ms_locations = json.loads(re.sub(r'\\(.)', r'\1', line.value))
            except ValueError:
                pass

    @_add
    def parse_rrule(event, line):
        if line:
            event.rrule = line.value

    @_add
    @option(multiple=True)
    def parse_exdate(event, lines):
        for line in lines:
            tz_dict = event._classmethod_kwargs["tz"]
            exdate = arrow_to_iso(iso_to_arrow(line, tz_dict))
            if getattr(event, 'exdate', None):
                event.exdate = '{},{}'.format(event.exdate, exdate)
            else:
                event.exdate = exdate

    @_add
    def parse_recurrence_id(event, line):
        if line:
            tz_dict = event._classmethod_kwargs["tz"]
            event.recurrence_id = arrow_to_iso(iso_to_arrow(line, tz_dict))


class ICalendarRecurringMeeting:

    def __init__(self, recurring_meeting, calendar):
        self.recurring_meeting = recurring_meeting
        self.calendar = calendar

    @classmethod
    def create(cls, customer, provider, ical):

        if not cls.is_ical_recurring(ical):
            return None

        calendar = cls._parse_ical(ical)

        recurring, created = RecurringMeeting.objects.get_or_create(  # TODO separate calendars?
            customer=customer, provider=provider,
            uid=calendar.events[0].uid
        )

        obj = cls(recurring, calendar)
        return obj, obj.create_meetings(now() + timedelta(days=365))

    @classmethod
    def _parse_ical(cls, ical: str) -> Calendar:
        fixed_ical = re.sub(r'TRIGGER;RELATED=.*', 'TRIGGER;VALUE=DATE-TIME:19980101T050000Z', ical)

        return Calendar(fixed_ical)

    @classmethod
    def is_ical_recurring(cls, ical: str):
        cal = cls._parse_ical(ical)
        return cls.is_calendar_recurring(cal)

    @classmethod
    def is_calendar_recurring(cls, cal: Calendar):

        with_rrule = [event for event in cal.events if hasattr(event, 'rrule')]

        if len(with_rrule) > 1:
            raise Exception('Got more than one RRULE in ical. Got {}'.format(len(with_rrule)))

        return len(with_rrule) == 1

    def get_objects(self):
        cal = self.calendar
        without_rrule = dict([(event.recurrence_id, event) for event in cal.events if not hasattr(event, 'rrule')])
        with_rrule = [event for event in cal.events if hasattr(event, 'rrule')]
        event = with_rrule[0]
        rstr = event.rrule
        meetdict = dict([(meeting.recurrence_id, meeting) for meeting in self.recurring_meeting.meeting_set.all() if meeting.recurrence_id])
        begin = event.begin.datetime
        end = event.end.datetime

        if len(with_rrule) > 1:
            raise Exception('Got more than one RRULE in ical. Got {}'.format(len(with_rrule)))

        if hasattr(event, 'exdate'):
            # Make rrule happy by appending 'Z' to each EXDATE, because timezones
            rstr = 'RRULE:'+rstr+'\r\n'+'EXDATE:'+','.join([ex+'Z' for ex in event.exdate.split(',')])

        rrule = rrulestr(rstr, dtstart=begin)

        return without_rrule, meetdict, begin, end, rrule

    def create_first_meeting(self):
        cal = self.calendar
        return Meeting.objects.create(
            title=cal.events[0].name,
            ts_start=cal.events[0].begin.datetime,
            ts_stop=cal.events[0].end.datetime,
            recurrence_id=cal.events[0].begin.datetime.strftime('%Y%m%dT%H%M%S'),
            provider=self.recurring_meeting.provider,
            customer=self.recurring_meeting.customer,
            recurring_master=self,
            creator_ip='127.0.0.1',
        )

    def create_meetings(self, enddate=None, **kwargs) -> Sequence[Meeting]:
        without_rrule, meetdict, begin, end, rrule = self.get_objects()
        rrr = rrule._rrule[0] if hasattr(rrule, '_rrule') else rrule

        if not rrr._until and not enddate:
            raise Exception('Need enddate for endlessly recurring meetings')

        if not self.recurring_meeting.first_meeting_id:
            self.recurring_meeting.first_meeting = self.create_first_meeting()
            self.recurring_meeting.save()

        first_meeting = self.recurring_meeting.first_meeting

        first_recurrence_id = rrule[0].strftime('%Y%m%dT%H%M%S')
        if first_meeting.recurrence_id != first_recurrence_id:
            if first_recurrence_id in meetdict:
                meetdict[first_recurrence_id].delete()
            first_meeting.recurrence_id = first_recurrence_id
            first_meeting.save()

        meetdict[first_recurrence_id] = first_meeting

        result = []
        for begin2 in rrule:
            if enddate is None or begin2 <= enddate:
                rec_id = begin2.strftime('%Y%m%dT%H%M%S')
                # See if there's an event with matching RECURRENCE-ID
                # If so then use its start/end times instead of begin2
                if rec_id in without_rrule:
                    ts_start = without_rrule[rec_id].begin.datetime
                    ts_stop = without_rrule[rec_id].end.datetime
                else:
                    ts_start = begin2
                    ts_stop = begin2 + (end - begin)

                if rec_id in meetdict:
                    meet = meetdict[rec_id]
                    if (meet.ts_start, meet.ts_stop) != (ts_start, ts_stop):
                        meet.ts_start = ts_start
                        meet.ts_stop = ts_stop
                        meet.save()
                        meet.schedule()
                    result.append(meet)
                else:
                    meet = first_meeting.copy(ts_start=ts_start, ts_stop=ts_stop, recurrence_id=rec_id, **kwargs)
                    meet.activate()
                    result.append(meet)
            else:
                break
        return result

    def update_meetings(self):
        without_rrule, meetdict, begin, end, rrule = self.get_objects()

        # Prune any meetings which are no longer in the recurrence
        for _rec_id, meeting in meetdict.items():
            if meeting.ts_start not in rrule:
                meeting.deactivate()
                meeting.delete()
