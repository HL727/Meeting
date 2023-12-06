from os.path import dirname
import json

from statistics.models import Call
from cdrhooks.models import Hook, Dialout, Session
from conferencecenter.tests.base import ConferenceBaseTest
from provider.tasks import check_hook_session
from django.utils.timezone import now
from datetime import timedelta


class ParseHooksTestCase(ConferenceBaseTest):

    def test_acano_hooks(self):

        self._init()

        with open(dirname(__file__) + '/acano_cdr.json') as fd:
            data = fd.read()

        cospace_id = '9edd2132-11ab-481e-8bc8-6ceac75e45b0'

        hook = Hook.objects.create(customer=self.customer, provider=self.acano,
            recording_key='1234', provider_ref=cospace_id)

        server = self.acano.cluster.acano.get_statistics_server()

        dialout = Dialout.objects.create(hook=hook, dialstring='testcall@clearsea.mobi')

        for l in data.strip().split("\n"):
            response = self.client.post(server.get_cdr_path(), json.loads(l)['rawpost'], content_type='text/xml')
            self.assertEqual(response.status_code, 200)

        # Calls
        calls = Call.objects.filter(cospace_id=cospace_id)
        self.assertEqual(calls.count(), 1)
        self.assertGreater(calls[0].duration, 60)

        # Hook

        sessions = Session.objects.filter(hook=hook)
        self.assertEqual(sessions.count(), 1)

        session = sessions[0]
        self.assertTrue(session.ts_start)
        self.assertTrue(session.ts_stop)
        self.assertTrue(session.refs)
        self.assertTrue(session.recording_ref)
        self.assertTrue(session.refs)

        diff = session._check_active([
            {'id': 'asdf'},
        ])

        self.assertEqual(diff, {'asdf'})

        diff = session._check_active([
            {'id': session.recording_ref},
            {'id': session.refs[str(dialout.pk)]},
        ])
        self.assertEqual(diff, set())

        dialout.persistant = True
        dialout.save()

        diff = session._check_active([
            {'id': session.recording_ref},
            {'id': session.refs[str(dialout.pk)]},
        ])
        self.assertEqual(diff, {session.refs[str(dialout.pk)]})

        # step by step

        dialout.persistant = False
        dialout.save()

        self.assertEqual(hook.get_sessions().filter(ts_stop__isnull=True).count(), 0)
        Session.objects.all().update(backend_active=False)


        leg = calls[0].legs.all()[0]
        hook.handle_tag('callLegUpdate', leg)

        self.assertEqual(hook.get_sessions().count(), 1)

        # another leg
        self.set_url_state('multiple_participants')
        session = hook.get_sessions().get()
        hook.handle_tag('callLegUpdate', leg)

        self.assertEqual(hook.get_sessions().count(), 1)
        session2 = hook.get_sessions().get()

        self.assertEqual(session.pk, session2.pk)
        self.assertEqual(session.ts_start, session2.ts_start)
        self.assertEqual(session.ts_stop, session2.ts_stop)

        session = hook.get_sessions().get()

        # another leg
        self.set_url_state('multiple_participants')

        hook.handle_tag('callLegUpdate', leg)

        self.assertEqual(hook.get_sessions().filter(ts_stop__isnull=True).count(), 1)
        session2 = hook.get_sessions().get()

        self.assertEqual(session.pk, session2.pk)
        self.assertEqual(session.ts_start, session2.ts_start)

        # end
        self.set_url_state('after_call')
        hook.handle_tag('callLegEnd', leg)

        self.assertEqual(hook.get_sessions().filter(ts_stop__isnull=True).count(), 0)

    def check_tasks(self):
        return  # TODO
        session = Session.objects.get(backend_active=True)
        check_hook_session(session.pk)

        session = Session.objects.get(pk=session.pk)

        self.assertEqual(session.backend_active, True)

        session.ts_last_active = now() - timedelta(hours=2)
        session.save()

        check_hook_session(session.pk)

        session = Session.objects.get(pk=session.pk)
        self.assertEqual(session.backend_active, False)






