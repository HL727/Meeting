from django.utils.timezone import make_aware

from conferencecenter.tests.base import ConferenceBaseTest
from statistics import graph
from statistics.models import DomainTransform, DomainRewrite
from statistics.parser.utils import rewrite_internal_domains, is_internal_leg


class GraphFunctionTests(ConferenceBaseTest):

    def test_count_seconds_between_hours(self):

        from datetime import datetime
        start = make_aware(datetime(2019, 1, 1, 10, 30))
        stop = make_aware(datetime(2019, 1, 1, 12, 30))

        result = graph.chunk_duration_between(start, stop)

        self.assertEqual(result, [
            ('2019-01-01 10:00', 30 * 60),
            ('2019-01-01 11:00', 60 * 60),
            ('2019-01-01 12:00', 30 * 60),
        ])

    def test_count_seconds_between_hours_short(self):

        from datetime import datetime
        start = make_aware(datetime(2019, 1, 1, 10, 30))
        stop = make_aware(datetime(2019, 1, 1, 10, 32))

        result = graph.chunk_duration_between(start, stop)

        self.assertEqual(result, [
            ('2019-01-01 10:00', 2 * 60),
        ])

    def test_count_seconds_between_days(self):

        from datetime import datetime
        start = make_aware(datetime(2019, 1, 1, 10, 30))
        stop = make_aware(datetime(2019, 1, 3, 10, 00))

        result = graph.chunk_duration_between(start, stop, hours=24)

        self.assertEqual(result, [
            ('2019-01-01', 13.5 * 60 * 60),
            ('2019-01-02', 24 * 60 * 60),
            ('2019-01-03', 10 * 60 * 60),
        ])

    def test_count_seconds_between_days_short(self):

        from datetime import datetime
        start = make_aware(datetime(2019, 1, 1, 10, 00))
        stop = make_aware(datetime(2019, 1, 1, 10, 30))

        result = graph.chunk_duration_between(start, stop, hours=24)

        self.assertEqual(result, [
            ('2019-01-01', 30 * 60),
        ])

    def test_internal_domains(self):

        transform = DomainTransform.objects.create(domain='right.com')
        DomainRewrite.objects.create(transform=transform, alias_domain='wrong.com')

        self.assertEqual(rewrite_internal_domains('user@wrong.com'), 'user@right.com')
        self.assertEqual(rewrite_internal_domains('user2@wrong.com'), 'user2@right.com')
        self.assertEqual(rewrite_internal_domains('user2@other.com'), 'user2@other.com')
        self.assertEqual(rewrite_internal_domains('user2@right.com'), 'user2@right.com')

        self.assertEqual(is_internal_leg('test@right.com'), True)
        self.assertEqual(is_internal_leg('test@wrong.com'), True)
        self.assertEqual(is_internal_leg('12345'), True)
        self.assertEqual(is_internal_leg('test'), False)
        self.assertEqual(is_internal_leg('test@other.com'), False)
