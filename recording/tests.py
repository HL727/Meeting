from conferencecenter.tests.base import ConferenceBaseTest
from .cdr import parse_cdr
from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse


class RecordingTestCase(ConferenceBaseTest):

    def setUp(self):
        self._init()

    def test_parse_record(self):

        xml_start = '''
        <record type="recordingStart" time="2019-03-21T13:50:50Z" recordIndex="231266" correlatorIndex="231265">\n
        <recording id="83180c3c-d05c-49b8-95ff-aaaaaaaaa">
        <path>spaces/aaaaaaaa-d375-482a-a492-906765a2ea0d/20190321145048+0100
        </path>
        <recorderUrl>https://88.88.88.40:8443
        </recorderUrl>
        <call>0e041bae-4c4b-4292-9809-1afec5379d2f
        </call>
        <callLeg>dc81b217-9db1-4b03-9f57-92eb27560ed8
        </callLeg>
        </recording>
        </record>\n
        '''

        xml_end = '''
        <record type="recordingEnd" time="2019-03-21T13:51:02Z" recordIndex="231275" correlatorIndex="231274">
        <recording id="83180c3c-d05c-49b8-95ff-aaaaaaaaa">
        </recording>
        </record>
        '''

        node = safe_xml_fromstring(xml_start.strip())
        result = parse_cdr(node)[0]

        self.assert_(result)
        self.assert_(result.ts_start)

        self.assertEqual(result.recording_id, '83180c3c-d05c-49b8-95ff-aaaaaaaaa')
        self.assertEqual(result.path, 'spaces/aaaaaaaa-d375-482a-a492-906765a2ea0d/20190321145048+0100')

        node = safe_xml_fromstring(xml_end.strip())
        result = parse_cdr(node)[0]

        self.assert_(result)
        self.assert_(result.ts_stop)

        if settings.EXTENDED_API_KEYS:
            response = self.client.get(reverse('api_get_recording', args=[result.secret_key]) + '?shared_key={}'.format(list(settings.EXTENDED_API_KEYS)[0]))
            self.assertEqual(response.status_code, 200)

            response = self.client.get(reverse('api_get_recording', args=[result.secret_key]) + '?shared_key=invalid')
            self.assertEqual(response.status_code, 403)

        # staff auth
        user = User.objects.create_user(username='test', password='test', is_staff=True)
        self.client.login(username=user.username, password='test')

        response = self.client.get(reverse('api_get_recording', args=[result.secret_key]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['path'], result.path)

    def test_parse_stream(self):

        xml_start = '''
        <record type="streamingStart" time="2019-03-21T10:10:17Z" recordIndex="209063" correlatorIndex="209062">\n
        <streaming id="aaaaaaaa-95d5-4699-af02-78854b2f0e1a">
        <streamUrl>rtmp://stream11.abiliteam.com/ability1121push/0xaaaaaaa7505b411c75b4cbce19732_cam1
        </streamUrl>
        <streamerUrl>https://88.83.48.41:443
        </streamerUrl>
        <call>1cae52fa-27ae-45e7-8c91-646aefbc96f9
        </call>
        <callLeg>318b9e44-ad3d-444d-90e2-d8b12cd2cb5f
        </callLeg>
        </streaming>
        </record>
        '''

        xml_end = '''
        <record type="streamingEnd" time="2019-03-21T10:15:05Z" recordIndex="209232" correlatorIndex="209231">\n
        <streaming id="aaaaaaaa-95d5-4699-af02-78854b2f0e1a">
        </streaming>
        </record>
         '''

        node = safe_xml_fromstring(xml_start.strip())
        result = parse_cdr(node)[0]

        self.assert_(result)
        self.assert_(result.ts_start)

        self.assertEqual(result.stream_url, 'rtmp://stream11.abiliteam.com/ability1121push/0xaaaaaaa7505b411c75b4cbce19732_cam1')

        node = safe_xml_fromstring(xml_end.strip())
        result = parse_cdr(node)[0]

        self.assert_(result)
        self.assert_(result.ts_stop)

