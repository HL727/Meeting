import csv
from copy import deepcopy
from io import StringIO
from os.path import dirname
import json

from organization.models import OrganizationUnit, UserUnitRelation, CoSpaceUnitRelation
from conferencecenter.tests.mock_data.pexip import eventsink_events
from policy.models import ActiveParticipant
from provider.models.provider import Provider
from statistics.models import Call, Server, Leg
from conferencecenter.tests.base import ConferenceBaseTest

from statistics.parser.cisco_ce import CiscoCEStatisticsParser
from statistics.parser.pexip import PexipEventParser


class AcanoParseTestCase(ConferenceBaseTest):

    def setUp(self):
        super().setUp()
        self._init()

    def test_parse_acano(self):
        with open(dirname(__file__) + '/acano_cdr.json') as fd:
            data = fd.read()

        cospace_id = '9edd2132-11ab-481e-8bc8-6ceac75e45b0'
        server = self.acano.cluster.acano.get_statistics_server()

        org_unit = OrganizationUnit.objects.create(customer=self.customer, name='test')
        UserUnitRelation.objects.create(unit=org_unit, user_jid='user2@example.org')
        CoSpaceUnitRelation.objects.create(
            unit=org_unit, provider_ref='9edd2132-11ab-481e-8bc8-6ceac75e45b0'
        )

        for l in data.strip().split("\n"):
            response = self.client.post(server.get_cdr_path(), json.loads(l)['rawpost'], content_type='text/xml')
            self.assertEqual(response.status_code, 200)

        # Calls
        calls = Call.objects.filter(cospace_id=cospace_id)
        self.assertEqual(calls.count(), 1)
        self.assertGreater(calls[0].duration, 60)

        calls[0].legs.all()[0]
        self.assertEqual(set(Call.objects.values_list('org_unit', flat=True)), {org_unit.pk})
        self.assertEqual(set(Leg.objects.values_list('org_unit', flat=True)), {org_unit.pk, None})


class AcanoTestMissingEvents(ConferenceBaseTest):
    def setUp(self):
        super().setUp()
        self._init()

    call_start = '''
        <?xml version="1.0" ?>
        <records session="8bf2f897-e4d6-4217-81d2-1ad41c245389" callBridge="04aec22b-20bb-4e71-b5bc-3e82279fb4ac">
            <record type="callStart" time="2022-05-17T10:07:29Z" recordIndex="86556" correlatorIndex="196284">


                <call id="d4d90b1d-7590-4a1b-8586-3dfdd35936ba">
                    <name>Test</name>
                    <ownerName/>
                    <callType>coSpace</callType>
                    <coSpace>068ee526-6f72-4ca7-ad1d-fe75e9c52753</coSpace>
                    <tenant>5f90ff0f-0705-4341-9b20-42b8df54c012</tenant>
                    <callCorrelator>4417fa02-5538-48cc-a835-ff854afc0d8c</callCorrelator>
                </call>
            </record>


        </records>
        '''.strip()

    call_leg_update = '''
    <?xml version="1.0" ?>
    <records session="8bf2f897-e4d6-4217-81d2-1ad41c245389" callBridge="04aec22b-20bb-4e71-b5bc-3e82279fb4ac">
        <record type="callLegUpdate" time="2022-05-17T10:08:31Z" recordIndex="86561" correlatorIndex="196289">


            <callLeg id="1611cb0c-e6a1-4e54-bd3a-53926d321da3">
                <state>connected</state>
                <call>d4d90b1d-7590-4a1b-8586-3dfdd35936ba</call>
                <deactivated>false</deactivated>
                <groupId>3cfa15ee-cda4-4aff-8c50-02c26201afce</groupId>
                <sipCallId>1B014FC3-D50011EC-832E975D-E41722E3@cube01.smartmeeting.se</sipCallId>
                <remoteAddress>0701234567@node01.example.org</remoteAddress>
                <canMove>true</canMove>
                <confirmationStatus>notRequired</confirmationStatus>
            </callLeg>
        </record>
    </records>
    '''.strip()

    def test_parse_missing_start(self):
        server = self.acano.cluster.acano.get_statistics_server()
        response = self.client.post(server.get_cdr_path(), self.call_start, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            server.get_cdr_path(), self.call_leg_update, content_type='text/xml'
        )
        self.assertEqual(response.status_code, 200)

        leg = Leg.objects.get(guid='1611cb0c-e6a1-4e54-bd3a-53926d321da3')
        self.assertTrue(leg.ts_start)
        self.assertFalse(leg.ts_stop)

        call_leg_end = '''
        <?xml version="1.0" ?>
        <records session="8bf2f897-e4d6-4217-81d2-1ad41c245389" callBridge="04aec22b-20bb-4e71-b5bc-3e82279fb4ac">
            <record type="callLegEnd" time="2022-05-17T10:09:08Z" recordIndex="86563" correlatorIndex="196291">


                <callLeg id="1611cb0c-e6a1-4e54-bd3a-53926d321da3">
                    <reason>remoteTeardown</reason>
                    <remoteTeardown>true</remoteTeardown>
                    <confirmationStatus>rejected</confirmationStatus>
                    <durationSeconds>98</durationSeconds>
                </callLeg>
            </record>
        </records>
        '''.strip()

        response = self.client.post(server.get_cdr_path(), call_leg_end, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        leg = Leg.objects.get(guid='1611cb0c-e6a1-4e54-bd3a-53926d321da3')
        self.assertTrue(leg.ts_start)
        self.assertTrue(leg.ts_stop)
        self.assertTrue(leg.should_count_stats)

    def test_parse_missing_leg_end(self):
        server = self.acano.cluster.acano.get_statistics_server()
        response = self.client.post(server.get_cdr_path(), self.call_start, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            server.get_cdr_path(), self.call_leg_update, content_type='text/xml'
        )
        self.assertEqual(response.status_code, 200)

        leg = Leg.objects.get(guid='1611cb0c-e6a1-4e54-bd3a-53926d321da3')
        self.assertTrue(leg.ts_start)
        self.assertFalse(leg.ts_stop)

        call_end = '''
        <?xml version="1.0" ?>
        <records session="8bf2f897-e4d6-4217-81d2-1ad41c245389" callBridge="04aec22b-20bb-4e71-b5bc-3e82279fb4ac">
            <record type="callEnd" time="2022-05-17T10:09:08Z" recordIndex="86564" correlatorIndex="196292">
                <call id="d4d90b1d-7590-4a1b-8586-3dfdd35936ba">
                    <callLegsCompleted>2</callLegsCompleted>
                    <callLegsMaxActive>2</callLegsMaxActive>
                    <durationSeconds>99</durationSeconds>
                </call>
            </record>
        </records>
        '''.strip()

        response = self.client.post(server.get_cdr_path(), call_end, content_type='text/xml')
        self.assertEqual(response.status_code, 200)

        leg = Leg.objects.get(guid='1611cb0c-e6a1-4e54-bd3a-53926d321da3')
        self.assertTrue(leg.ts_start)
        self.assertTrue(leg.ts_stop)
        self.assertTrue(leg.should_count_stats)


class CiscoCEParseTestCase(ConferenceBaseTest):

    def test_parse_cisco_ce_roomkit(self):

        with open(dirname(__file__) + '/cisco_ce_call.xml') as fd:
            self._test_parse_cisco_ce(fd.read().strip())

    def test_parse_cisco_ce_sx10(self):

        with open(dirname(__file__) + '/cisco_ce_call_sx10.xml') as fd:
            self._test_parse_cisco_ce(fd.read().strip())

    def _test_parse_cisco_ce(self, xml):

        from endpoint.models import Endpoint

        self._init()

        endpoint = Endpoint.objects.create(customer=self.customer, title='test', manufacturer=Endpoint.MANUFACTURER.CISCO_CE)
        server = Server.objects.create(type=Server.ENDPOINTS, customer=self.customer)

        result = CiscoCEStatisticsParser(server, endpoint).parse_xml(xml)
        self.assertNotEqual(result, None)

        # Calls
        calls = Call.objects.all()
        self.assertEqual(calls.count(), 1)
        self.assertGreater(calls[0].duration, 60)

        calls[0].legs.all()[0]


class PexipParseTestCase(ConferenceBaseTest):

    def setUp(self):
        super().setUp()
        self._init()
        self.customer.lifesize_provider = self.pexip
        self.customer.save()

    def test_parse_pexip_event(self):

        pexip = self.pexip.cluster
        server = Server.objects.create(type=Server.PEXIP, cluster=pexip)

        conference_started = eventsink_events['conference_started']

        call = PexipEventParser(server).parse_eventsink_event(conference_started)
        self.assertEqual(call.tenant, '')

        from datastore.models.pexip import Conference, Tenant
        Conference.objects.create(name='meet.webapp', cid=123, provider=pexip, tenant=Tenant.objects.create(tid=self.customer.get_pexip_tenant_id(), provider=pexip))

        call = PexipEventParser(server).parse_eventsink_event(conference_started)
        self.assertEqual(call.tenant, self.customer.pexip_tenant_id)

        for _i in range(2):
            participant_connected = eventsink_events['participant_connected']
            PexipEventParser(server).parse_eventsink_event(participant_connected)
            self.assertEqual(len(Leg.objects.filter(server=server, ts_stop__isnull=True)), 1)
            self.assertEqual(len(Call.objects.filter(server=server, ts_stop__isnull=True)), 1)

        part2 = deepcopy(participant_connected)
        part2['data']['conversation_id'] += '2'
        part2['data']['call_id'] += '2'
        part2['data']['connect_time'] -= 10

        PexipEventParser(server).parse_eventsink_event(part2)
        self.assertEqual(len(Leg.objects.filter(server=server, ts_stop__isnull=True)), 2)
        self.assertEqual(len(Call.objects.filter(server=server, ts_stop__isnull=True)), 1)

        self.assertEqual(ActiveParticipant.objects.all().count(), 2)

        participant_disconnected = eventsink_events['participant_disconnected']

        PexipEventParser(server).parse_eventsink_event(participant_disconnected)
        self.assertEqual(ActiveParticipant.objects.all().count(), 1)

        part2 = deepcopy(participant_disconnected)
        part2['data']['conversation_id'] += '2'
        part2['data']['call_id'] += '2'
        part2['data']['connect_time'] -= 10

        PexipEventParser(server).parse_eventsink_event(part2)
        self.assertEqual(ActiveParticipant.objects.all().count(), 0)

        self.assertEqual(len(Leg.objects.filter(server=server, ts_stop__isnull=True)), 0)

        self.assertEqual(len(Call.objects.filter(server=server)), 1)
        self.assertEqual(len(Leg.objects.filter(server=server)), 2)

    def test_pexip_eventsink(self):

        pexip = self.pexip.cluster
        server = pexip.get_statistics_server()
        pexip.pexip.default_customer = None
        pexip.pexip.save()

        # name match
        from customer.models import CustomerMatch

        self.assertEqual(self.customer.pexip_tenant_id, '')
        CustomerMatch.objects.create(cluster=pexip, customer=self.customer, prefix_match='meet.')
        self.assertNotEqual(self.customer.pexip_tenant_id, '')

        # test evensink urls
        self.client.post(server.get_cdr_url(), json.dumps(eventsink_events['conference_started']), content_type='text/json')
        self.assertEqual(Call.objects.filter(server=server).first().tenant, '')  # no conference match

        self.assertEqual(ActiveParticipant.objects.all().count(), 0)
        self.client.post(server.get_cdr_url(), json.dumps(eventsink_events['participant_disconnected']), content_type='text/json')
        self.assertEqual(ActiveParticipant.objects.all().count(), 0)

        self.customer.refresh_from_db()
        self.assertEqual(Call.objects.filter(server=server).first().tenant, self.customer.pexip_tenant_id)  # got from participant

        self.customer.refresh_from_db()
        self.assert_(self.customer.pexip_tenant_id)
        self.assertEqual(Call.objects.filter(server=server).first().tenant, self.customer.pexip_tenant_id)
        self.assertEqual(Leg.objects.filter(server=server).first().tenant, self.customer.pexip_tenant_id)

    def test_pexip_csv(self):

        self._init()
        pexip = Provider.objects.create(type=Provider.TYPES.pexip_cluster, title='test')
        server = Server.objects.create(type=Server.PEXIP, cluster=pexip, customer=self.customer)


        conference = {
    'duration': 579,
    'end_time': '2015-04-02T09:55:33.141261',
    'id': '8583f400-7886-48c9-874b-5fefc2ac097e',
    'instant_message_count': 0,
    'name': 'meet.alice',
    'participant_count': 3,
    'participants': [
        '/api/admin/history/v1/participant/e9883f1d-88ca-495d-8366-b6eb772dfe57/',
        '/api/admin/history/v1/participant/5881adda-00ef-4315-8886-5d873d2ef269/',
        '/api/admin/history/v1/participant/29744376-0436-4fe1-ab80-06d93c71eb1c/'
      ],
    'resource_uri': '/api/admin/history/v1/conference/8583f400-7886-48c9-874b-5fefc2ac097e/',
    'service_type': 'conference',
    'start_time': '2015-04-02T09:36:53.712941',
    'tag': ''
    }
        participant = {
                'bandwidth': 768,
                'call_direction': 'in',
                'call_quality': '1_good',
                'call_uuid': 'b0a5b554-d1de-11e3-a321-000c29e37602',
                'conference': '/api/admin/history/v1/conference/8583f400-7886-48c9-874b-5fefc2ac097e/',
                'conference_name': 'meet.alice',
                'conversation_id': 'b0a5b554-d1de-11e3-a321-000c29e37602',
                'disconnect_reason': 'Call disconnected',
                'display_name': 'Bob',
                'duration': 519,
                'encryption': 'On',
                'end_time': '2015-04-02T09:55:33.141261',
                'has_media': True,
                'id': '00000000-0000-0000-0000-000000000003',
                'is_streaming': False,
                'license_count': 1,
                'license_type': 'port',
                'local_alias': 'meet@example.com',
                'media_node': '10.0.0.1',
                'media_streams': [
                    {
                        'end_time': '2015-07-22T12:43:33.645043',
                        'id': 36,
                        'node': '10.0.0.1',
                        'participant': '/api/admin/history/v1/participant/5881adda-00ef-4315-8886-5d873d2ef269/',
                        'rx_bitrate': 29,
                        'rx_codec': 'opus',
                        'rx_packet_loss': 0.0,
                        'rx_packets_lost': 0,
                        'rx_packets_received': 28091,
                        'rx_resolution': '',
                        'start_time': '2015-07-22T12:33:31.909536',
                        'stream_id': '0',
                        'stream_type': 'audio',
                        'tx_bitrate': 2,
                        'tx_codec': 'opus',
                        'tx_packet_loss': 0.0,
                        'tx_packets_lost': 0,
                        'tx_packets_sent': 56347,
                        'tx_resolution': ''
                    },
                    {
                        'end_time': '2015-07-22T12:43:33.683385',
                        'id': 37,
                        'node': '10.0.0.1',
                        'participant': '/api/admin/history/v1/participant/5881adda-00ef-4315-8886-5d873d2ef269/',
                        'rx_bitrate': 511,
                        'rx_codec': 'VP8',
                        'rx_packet_loss': 0.01,
                        'rx_packets_lost': 2,
                        'rx_packets_received': 37027,
                        'rx_resolution': '1280x720',
                        'start_time': '2015-07-22T12:33:32.151438',
                        'stream_id': '1',
                        'stream_type': 'video',
                        'tx_bitrate': 511,
                        'tx_codec': 'VP8',
                        'tx_packet_loss': 0.0,
                        'tx_packets_lost': 0,
                        'tx_packets_sent': 37335,
                        'tx_resolution': '768x448'
                    }
                ],
                'parent_id': '29744376-0436-4fe1-ab80-06d93c71eb1c',
                'protocol': 'WebRTC',
                'proxy_node': 'None',
                'remote_address': '10.0.0.2',
                'remote_alias': 'Infinity_Connect_Media_10.0.0.2',
                'remote_port': 11007,
                'resource_uri': '/api/admin/history/v1/participant/00000000-0000-0000-0000-000000000003/',
                'role': 'chair',
                'service_tag': '',
                'service_type': 'conference',
                'signalling_node': '10.0.0.1',
                'start_time': '2015-04-02T09:46:53.712941',
                'system_location': 'London',
                'vendor': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.101 Safari/537.36'
            }


        # test csv urls
        def _get_csv(dct):
            keys = list(dct.keys())
            values = [dct[k] for k in keys]
            return json.dumps({'cols': keys, 'rows': [values]})
        self.client.post(server.get_cdr_url() + 'conference/csv/', _get_csv(conference), content_type='text/json')

        self.client.post(server.get_cdr_url() + 'participant/csv/', _get_csv(participant), content_type='text/json')

        fd = StringIO()
        writer = csv.DictWriter(fd, participant.keys())
        writer.writeheader()
        writer.writerow({**participant, 'media_streams': None})
        fd.seek(0)
        self.client.post(server.get_cdr_url() + 'participant/csv/', fd.getvalue(), content_type='text/csv')

        self.assertEquals(Call.objects.filter(server=server).count(), 1)
        self.assertEquals(Leg.objects.filter(server=server).count(), 1)

        # Mividas Import/export  # TODO move out to separate test
        server2 = Server.objects.create(name='test')

        call_csv = self._export_call_csv(server)
        self._import_call_csv(server2, call_csv)

        new_call_csv = self._export_call_csv(server2)
        self.assertEquals(call_csv.decode('utf-8').split('\n'), new_call_csv.decode('utf-8').split('\n'))

        leg_csv = self._export_leg_csv(server)
        self._import_leg_csv(server2, leg_csv)

        new_leg_csv = self._export_leg_csv(server2)
        self.assertEquals(leg_csv.decode('utf-8').split('\n'), new_leg_csv.decode('utf-8').split('\n'))

    def _login(self):
        from django.contrib.auth.models import User
        User.objects.filter(username='export') or User.objects.create_user(username='export', password='export', is_staff=True, is_superuser=True)
        self.client.login(username='export', password='export')

    def _export_call_csv(self, server):
        self._login()
        response = self.client.get(server.get_export_path('call') + '?export=1')
        self.assertEquals(response.status_code, 200)
        mividas_call_export_csv = b''.join(response.streaming_content)

        self.assertGreater(len(mividas_call_export_csv), 200)
        return mividas_call_export_csv

    def _import_call_csv(self, server, csv_content):
        # import
        response = self.client.post(server.get_import_path('call'), csv_content, content_type='text/csv')
        list(response.streaming_content)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(Call.objects.filter(server=server).count(), 1)

    def _export_leg_csv(self, server):
        self._login()
        response = self.client.get(server.get_export_path('leg') + '?export=1')
        self.assertEquals(response.status_code, 200)
        mividas_leg_export_csv = b''.join(response.streaming_content)

        self.assertGreater(len(mividas_leg_export_csv), 200)
        return mividas_leg_export_csv

    def _import_leg_csv(self, server, csv_content):
        response = self.client.post(server.get_import_path('leg'), csv_content, content_type='text/csv')
        list(response.streaming_content)
        self.assertEquals(response.status_code, 200)
        self.assertEqual(Leg.objects.filter(server=server).count(), 1)

