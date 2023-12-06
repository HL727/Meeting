from datetime import timedelta

from django.utils.timezone import now

from conferencecenter.tests.base import ConferenceBaseTest
from provider.models.provider import Cluster
from statistics.cleanup import merge_duplicate_calls, rewrite_history_chunks, rewrite_pexip_chunks
from statistics.models import Call, Server, Leg


class UtilsTestCase(ConferenceBaseTest):

    def setUp(self):
        self._init()

    def _create_calls(self):

        server = Server.objects.create(type=Server.PEXIP, cluster=self.pexip.cluster)
        call = Call.objects.create(server=server, cospace='room1', ts_start=now() - timedelta(minutes=10))
        call2 = Call.objects.create(server=server, cospace='room1', ts_start=now() - timedelta(minutes=15), ts_stop=now())

        call3 = Call.objects.create(server=server, cospace='room2', ts_start=call.ts_start)

        Leg.objects.create(call=call, server=server, ts_start=now() - timedelta(minutes=10))
        Leg.objects.create(call=call2, server=server, ts_start=now() - timedelta(minutes=10), ts_stop=now())
        Leg.objects.create(call=call3, server=server, ts_start=call.ts_start)

        self.server = server
        self.call, self.call2 = call, call2

    def test_merge_duplicate_calls(self):

        self._create_calls()

        self.assertEqual(Call.objects.count(), 3)

        result = merge_duplicate_calls(self.server)
        self.assertTrue(result)

        self.assertEqual(Leg.objects.filter(call=self.call2).count(), 2)
        self.assertEqual(Call.objects.count(), 2)
        self.assertEqual(Leg.objects.count(), 3)

    def test_rewrite_history(self):
        self.customer.lifesize_provider = self.pexip
        self.customer.save()

        self._create_calls()

        rewrite_history_chunks()
        rewrite_pexip_chunks()

    def test_reset_missing_leg_stop_time(self):

        self._init()
        cluster = Cluster.objects.create(title='test', type=Cluster.TYPES.pexip_cluster)
        server = Server.objects.create(type=Server.PEXIP, cluster=cluster)
        call = Call.objects.create(server=server, cospace='room1', ts_start=now() - timedelta(minutes=10))

        Leg.objects.create(call=call, guid='1', server=server, ts_start=now() - timedelta(minutes=20))
        Leg.objects.create(call=call, guid='2', server=server, ts_start=now() - timedelta(minutes=20))
        Leg.objects.create(call=call, guid='3', server=server, ts_start=now() - timedelta(minutes=20))

        from policy.tasks import reset_missing_leg_stop_time

        reset_missing_leg_stop_time(cluster.pk, [{'call_uuid': '2'}, {'call_uuid': '3'}])
        self.assertEqual(Leg.objects.filter(ts_stop__isnull=True).count(), 2)

        reset_missing_leg_stop_time(cluster.pk)
        self.assertEqual(Leg.objects.filter(ts_stop__isnull=True).count(), 0)
