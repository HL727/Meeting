import json
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from os import path

from django.utils.dateparse import parse_datetime
from django.utils.timezone import now, localtime, make_aware
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from room_analytics.graph import get_head_count_graph
from room_analytics.utils.report import GroupedHeadCountStats
from room_analytics.utils.time import get_hours_between
from endpoint import consts
from endpoint.models import Endpoint, EndpointMeetingParticipant
from room_analytics.models import EndpointHeadCount, EndpointRoomPresence

root = path.dirname(path.abspath(__file__))


class PeopleCountTestBase(ConferenceBaseTest):

    def setUp(self):
        super().setUp()
        self._init()
        self.endpoint = Endpoint.objects.create(customer=self.customer, ip='192.168.1.117', username='admin',
                manufacturer=consts.MANUFACTURER.CISCO_CE, mac_address='11:22:33:44:55:66')

        self.ts_start = (localtime() - timedelta(days=8)).replace(hour=0, minute=0, second=0, microsecond=0)
        self.ts_stop = (localtime() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        self._create_head_counts()

    def _create_head_counts(self):

        self.all_hours = get_hours_between(self.ts_start, self.ts_stop)
        if self.ts_start <= now().replace(month=10, day=25, hour=0) <= self.ts_stop:
            winter_time_diff = 1
        else:
            winter_time_diff = 0

        self.assertGreater(len(self.all_hours), 9 * 24 - winter_time_diff)

        last_ts = None

        for i, ts in enumerate(self.all_hours):
            last_ts = ts
            EndpointHeadCount.objects.create(endpoint=self.endpoint, value=i % 8, ts=ts)
            EndpointHeadCount.objects.create(
                endpoint=self.endpoint, value=i % 8 + 2, ts=ts + timedelta(minutes=30)
            )
            EndpointRoomPresence.objects.create(endpoint=self.endpoint, ts=ts, value=1)

        return last_ts


class TestEndpointStats(APITestCase, PeopleCountTestBase):

    def setUp(self):

        super().setUp()
        self.user = User.objects.create_user(username='test', password='test')
        self.client.login(username=self.user.username, password='test')

    def test_helpers(self):
        self._create_head_counts()

        count = EndpointHeadCount.objects.get_for_time(self.endpoint, self.ts_start, self.ts_stop)
        self.assertEqual(count, 9)

        count = EndpointHeadCount.objects.get_for_time(self.endpoint, self.ts_start)
        self.assertEqual(count, 0)

        count = EndpointHeadCount.objects.get_for_time(self.endpoint, self.ts_start - timedelta(minutes=1))
        self.assertEqual(count, 0)

        count = EndpointHeadCount.objects.get_for_time(self.endpoint, self.ts_start - timedelta(hours=1))
        self.assertEqual(count, None)

        count = EndpointHeadCount.objects.get_for_time(self.endpoint, self.ts_stop + timedelta(hours=2))
        self.assertEqual(count, None)

    def _create_meeting_with_endpoint(self):

        from meeting.models import Meeting
        meeting = Meeting.objects.create(title='test', customer=self.customer,
                                         provider=self.customer.get_api().cluster,
                                         ts_start=now() - timedelta(hours=1),
                                         ts_stop=now() + timedelta(hours=1),
                                         provider_ref2='fffffff-1948-47ec-ad4f-4793458cfe0c',
                                         creator_ip='127.0.0.1',
                                         room_info=json.dumps([{'endpoint': self.endpoint.email_key}]),
                                         )
        meeting.activate()
        return meeting

    def test_statistics_connections(self):
        from statistics.models import Call, Leg

        self._create_head_counts() - timedelta(minutes=30)
        meeting = self._create_meeting_with_endpoint()

        server = self.customer.get_api().cluster.get_statistics_server()
        call = Call.objects.create(server=server, cospace_id='fffffff-1948-47ec-ad4f-4793458cfe0c', ts_start=now())
        leg = Leg.objects.create(server=server, endpoint=self.endpoint, call=call, ts_start=now() - timedelta(hours=2))

        self.assertEquals(call.meeting_id, meeting.pk)
        self.assertTrue(leg.head_count)  # todo determinate correct value per hour
        self.assertEquals(leg.presence, True)

    def test_status_api(self):

        meeting = self._create_meeting_with_endpoint()
        if not settings.CELERY_TASK_ALWAYS_EAGER:
            meeting.sync_endpoint_bookings()
            from endpoint import tasks
            tasks.update_active_meeting(self.endpoint.pk)

        response = self.client.get('/json-api/v1/room_statistics/endpoint_status/')
        self.assertTrue(response.status_code, 200)

        data = response.json()
        self.assertTrue(data)
        self.assertTrue(data[0].get('active_meeting'))
        self.assertEquals(data[0]['active_meeting']['meeting'], meeting.pk)

    def test_head_count_graph(self):

        ts_start = self.ts_start
        ts_stop = self.ts_stop

        v1 = get_head_count_graph([self.endpoint], ts_start, ts_stop, as_json=True)

        self.assert_(v1)

        v2 = get_head_count_graph([self.endpoint], ts_start, ts_stop, as_percent=True, as_json=True)
        self.assert_(v2)
        self.assertNotEquals(v1, v2)

    def test_head_count_per_date_graph(self):
        data = GroupedHeadCountStats([self.endpoint], self.ts_start, self.ts_stop).get_graph('date', as_json=True)
        self.assert_(data)

    def test_head_count_per_day_graph(self):
        data = GroupedHeadCountStats([self.endpoint], self.ts_start, self.ts_stop).get_graph('day', as_json=True)
        self.assert_(data)

    def test_head_count_individual_per_date_graph(self):
        data = GroupedHeadCountStats([self.endpoint], self.ts_start, self.ts_stop).get_invididual_graph('date', as_json=True)
        self.assert_(data)

    def test_max_per_date_graph(self):
        data = GroupedHeadCountStats([self.endpoint], self.ts_start, self.ts_stop).get_max_values_graph('date', as_json=True)
        self.assert_(data)

    def test_sum_per_date_graph(self):
        data = GroupedHeadCountStats([self.endpoint], self.ts_start, self.ts_stop).get_sum_max_values_graph('date', as_json=True)
        self.assert_(data)

    def _test_head_count_per_hour(self):

        graph = GroupedHeadCountStats([self.endpoint], self.ts_start, self.ts_stop)

        normal = graph.get_graph('hour', as_json=True)
        self.assertEqual(len(normal['data'][0]['x']), len(self.all_hours))

        as_percent = graph.get_graph('hour', as_percent=True, as_json=True)
        self.assertEqual(as_percent['data'][0]['x'], normal['data'][0]['x'])
        self.assertNotEquals(as_percent['data'][0]['y'], normal['data'][0]['y'])

        no_fill_full = graph.get_graph('hour', as_percent=True, fill_gaps=False, as_json=True)
        self.assertEqual(no_fill_full['data'][0]['x'], normal['data'][0]['x'])
        self.assertEqual(no_fill_full['data'][0]['y'], as_percent['data'][0]['y'])

        removed = EndpointHeadCount.objects.filter(ts__hour=3).delete()
        self.assert_(removed)

        no_fill_missing = graph.get_graph('hour', as_percent=True, fill_gaps=False, as_json=True)
        self.assert_(no_fill_missing)
        self.assertNotEquals(no_fill_missing['data'][0]['x'], no_fill_full['data'][0]['x'])
        self.assertNotEquals(no_fill_missing['data'][0]['y'], no_fill_full['data'][0]['y'])

