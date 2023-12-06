from datetime import date

from django.utils.translation import ngettext

from endpoint.tests.base import EndpointBaseTest
from statistics.models import Server
from .utils.call_statistics import DemoCallsGenerator


class GenerateDemoCallsTestCase(EndpointBaseTest):
    def setUp(self):
        super().setUp()

        endpoint_server = Server.objects.get_endpoint_server(self.customer)

        self.server = self.acano.cluster.acano.get_statistics_server()
        cospaces = [{
            'id': '22f67f91-1948-47ec-ad4f-4793458cfe0c',
            'call_id': '61170',
            'name': 'cospace_test',
            'uri': '61170',
            'auto_generated': False
        }]

        self.generator = DemoCallsGenerator(customer=self.customer,
                                            server=self.server,
                                            endpoint_server=endpoint_server,
                                            endpoints=[self.endpoint],
                                            cospaces=cospaces)

    def test_call_generator(self):
        # Default vrm

        call = self.generator.generate_call(
            call_date=date.today(), random_cospace=False, server=self.server
        )

        self.assertEqual(call.server.pk, self.server.pk)
        self.assertEqual(call.cospace, 'default')

        # Random vrm

        call = self.generator.generate_call(
            call_date=date.today(), random_cospace=True, server=self.server
        )

        self.assertEqual(call.server.pk, self.server.pk)
        self.assertEqual(call.cospace, 'cospace_test')
        self.assertEqual(call.cospace_id, '22f67f91-1948-47ec-ad4f-4793458cfe0c')

    def test_leg_generator(self):
        call = self.generator.generate_call(
            call_date=date.today(), random_cospace=False, server=self.server
        )

        # No endpoint

        leg, leg_type = self.generator.generate_call_leg(call=call,
                                                         leg_target='test1@example.com',
                                                         is_endpoint=False)

        self.assertEqual(leg_type, 'legs')
        self.assertEqual(leg.call_id, call.pk)
        self.assertEqual(leg.target, 'test1@example.com')

        # For endpoint

        leg, leg_type = self.generator.generate_call_leg(call=call,
                                                         leg_target='test2@example.com',
                                                         is_endpoint=True)

        self.assertEqual(leg_type, 'endpoint_legs')
        self.assertEqual(leg.call_id, call.pk)
        self.assertEqual(leg.endpoint_id, self.endpoint.pk)
        self.assertEqual(leg.target, 'test2@example.com')
