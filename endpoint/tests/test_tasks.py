from endpoint import tasks
from endpoint.tests.base import EndpointBaseTest


class EndpointTaskTest(EndpointBaseTest):

    def test_update_endpoint_stats(self):
        tasks.update_endpoint_status(self.endpoint.pk)
