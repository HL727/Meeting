from django.urls import reverse

from conferencecenter.tests.base import PexipProviderBaseTest, ThreadedTestCase
from statistics.models import Server
from statistics.tests.test_views import StatsViewsBase


class StatsViewsTestCase(StatsViewsBase):
    def test_server_list(self):

        response = self.client.get('/json-api/v1/callstatistics_server/')
        self.assertEqual(response.status_code, 200)

    def test_server_single(self):

        server = Server.objects.first()
        response = self.client.get('/json-api/v1/callstatistics_server/{}/'.format(server.pk))
        self.assertEqual(response.status_code, 200)


class RecountVCSStatsTest(StatsViewsBase):
    def get_cluster(self):
        return self.vcse.cluster

    def get_server(self):
        return self.get_cluster().get_statistics_server()

    def test_reparse_logs(self):

        server = self.get_server()
        self.get_cluster().get_api(self.customer).update_stats()

        response = self.client.post(
            '/json-api/v1/callstatistics_server/{}/reparse_logs/'.format(server.pk)
        )
        self.assertEqual(response.status_code, 200)

    def test_reparse_api(self):

        server = self.get_server()

        self.get_cluster().get_api(self.customer).update_stats()

        response = self.client.post(
            '/json-api/v1/callstatistics_server/{}/reparse_api_history/'.format(server.pk)
        )
        self.assertEqual(response.status_code, 200)


class RecountPexipStatsTest(RecountVCSStatsTest, PexipProviderBaseTest, ThreadedTestCase):
    def get_cluster(self):
        return self.pexip.cluster

    def test_rematch_stats(self):

        server = self.get_server()

        self.get_cluster().get_api(self.customer).update_stats()

        response = self.client.post(
            '/json-api/v1/callstatistics_server/{}/rematch_stats/'.format(server.pk)
        )
        self.assertEqual(response.status_code, 200)
