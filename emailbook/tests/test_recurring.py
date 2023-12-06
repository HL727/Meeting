from datetime import timedelta

from django.utils.timezone import now

from calendar_invite.tests import _get_icalendar, _get_full_message
from conferencecenter.tests.base import ConferenceBaseTest
from emailbook.handler import EmailHandler
from provider.models.utils import date_format


class RecurringTestCase(ConferenceBaseTest):
    def setUp(self):
        super().setUp()
        self._init()

    def test_recurring(self):
        start = now()

        ical = _get_icalendar(ts_start=start,
                              extra_ical='RRULE:FREQ=DAILY;COUNT=10\nEXDATE:{}'.format(date_format(start))
                              )
        message = _get_full_message(calendar=ical)

        def _get_occurences(meeting):
            occurrences = meeting.recurring_master.occurences.all()
            dates = [str(m.ts_start.date()) for m in occurrences]
            return occurrences, dates

        content, meeting = self._test_recurring_real(message)
        occurrences, dates = _get_occurences(meeting)
        self.assertEqual(sorted(dates), sorted(set(dates)), 'No duplicate dates!')

        # again
        content, meeting2 = self._test_recurring_real(message)
        occurrences2, dates2 = _get_occurences(meeting2)
        self.assertEqual(meeting.recurring_master_id, meeting2.recurring_master_id)
        self.assertEqual([o.id for o in occurrences], [o.id for o in occurrences2])
        self.assertEqual(sorted(dates2), sorted(set(dates2)), 'No duplicate dates!')

        # move all forward
        for m in meeting2.recurring_master.occurences.all():
            m.ts_start = m.ts_start + timedelta(hours=1)
            m.ts_stop = m.ts_stop + timedelta(hours=1)
            m.recurrence_id = date_format(m.ts_start)
            m.save()

        # should be changed back
        content, meeting3 = self._test_recurring_real(message)
        occurrences3, dates3 = _get_occurences(meeting3)
        self.assertEqual([o.id for o in occurrences], [o.id for o in occurrences2])
        self.assertEqual(sorted(dates3), sorted(set(dates3)), 'No duplicate dates!')

        self.assertEqual(sorted(dates), sorted(dates3))

    def _test_recurring_real(self, message):
        handler = EmailHandler(message.as_string())
        valid, content, error = handler.handle_locked()

        meeting = content.get('meeting')

        self.assertTrue(meeting)
        self.assertTrue(content['meeting'].recurring_master)
        occurrences = content['meeting'].recurring_master.occurences.all()
        self.assertEqual(occurrences.count(), 10)

        return content, meeting
