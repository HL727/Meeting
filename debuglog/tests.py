from email.message import Message

from django.test import TestCase
from django.utils.timezone import now

from .models import AcanoCDRLog, AcanoCDRSpamLog, EmailLog, VCSCallLog, EndpointCiscoEvent
from endpoint.tests.test_cisco_http_event import head_count_request

acano_cdr = '''
        <records session="f1f46817-3f81-4e91-a5bd-572c80c2753e">
<record type="callStart" time="2020-01-07T11:17:52Z" recordIndex="625081" correlatorIndex="625080">

<call id="1ffc9435-4e57-40e0-b43b-0592854734857"> <name>test </name> <ownerName> </ownerName>
<callType>coSpace</callType>
<coSpace>13137f2e-f80d-42b6-ab4e-8a9ac8392dec</coSpace>
<callCorrelator>84e10527-f98f-487b-b117-6fdafac3cf3e</callCorrelator>
</call>
</record>

</records>
<records session="f1f46817-3f81-4e91-a5bd-572c80c2753e">
<record type="callLegStart" time="2020-01-07T11:17:52Z" recordIndex="625082" correlatorIndex="625081">

<callLeg id="2157adbf-4a2c-400c-a429-885290cd2b56">
<remoteParty>test@example.org</remoteParty>
<displayName>Test test</displayName>
<type>acano
</type>
<direction>incoming
</direction>
<call>1ffc9435-4e57-40e0-b43b-0592854734857
</call>
<groupId>2157adbf-4a2c-400c-a429-885290cd2b57
</groupId>
</cdrTag>
</callLeg>
</record>

</records>
'''


class TestLogs(TestCase):

    def test_acano_cdr(self):

        AcanoCDRLog.objects.store(content=acano_cdr, ip='1.1.1.1')

        l = AcanoCDRLog.objects.get()
        self.assertEqual(l.ip, '1.1.1.1')
        self.assertEqual(l.content, acano_cdr.encode('utf-8'))
        self.assertEqual(l.id_prefixes, ' 1ffc9 2157a')

        invalid = AcanoCDRLog.objects.search_ids('1ffc9invalid')
        self.assertEqual(len(invalid), 0)

        valid = AcanoCDRLog.objects.search_ids('2157adbf-4a2c-400c-a429-885290cd2b56')
        self.assertEqual(len(valid), 1)

        self.assert_(l.as_dict())

    def test_acano_cdr_spam(self):

        AcanoCDRSpamLog.objects.store(content=acano_cdr)
        self.assertEqual(AcanoCDRSpamLog.objects.get().content, acano_cdr.encode('utf-8'))

    def test_email_log(self):

        m = Message()
        m['From'] = 'test@mividas.com'
        m['Subject'] = 'testar åäö'

        EmailLog.objects.store(content=m.as_bytes())

        l = EmailLog.objects.get()

        self.assertEqual(l.sender, 'test@mividas.com')
        self.assertEqual(l.subject, 'testar åäö')
        self.assert_(l.content)

    def test_vcs_log(self):

        VCSCallLog.objects.store(content='''{"records": []}''')
        self.assert_(VCSCallLog.objects.get().content)

        VCSCallLog.objects.store(content='''{"records": []}''', ts_start=now(), ts_stop=now())

    def test_endpoint_log(self):

        EndpointCiscoEvent.objects.store(content=head_count_request)
        self.assert_(EndpointCiscoEvent.objects.get().content)

    def test_archive(self):

        self.test_acano_cdr()
        AcanoCDRLog.objects.archive(now())







