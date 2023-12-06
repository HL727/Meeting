from django.contrib.auth.models import User

from conferencecenter.tests.mock_data.acano import distinct_ids
from .models import Hook, ScheduledDialout, ScheduledDialoutPart, Dialout
from conferencecenter.tests.base import ConferenceBaseTest
from django.utils.timezone import now
from datetime import timedelta
from django.conf import settings


class TestLeg:

    class call:
        cospace_id = 'testspace'


class DialoutTestCase(ConferenceBaseTest):

    cospace_id = distinct_ids['cospace_without_user']

    def setUp(self):
        super().setUp()
        self._init()
        User.objects.create_user(username='test', password='test', is_staff=True, is_superuser=True)
        self.client.login(username='test', password='test')

    def test_error(self):

        data = {
            'form_action': 'edit_hook',
            'dialstring': 'asdf' * 1000,
        }
        response = self.client.post('/cospaces/{}/hooks/'.format(self.cospace_id), data)
        self.assertEqual(response.status_code, 200)

    def test_form(self):
        data = {
            'enable': '1',
            'recording_key': '1234',
            'form_action': 'edit_hook',
        }
        response = self.client.post('/cospaces/{}/hooks/'.format(self.cospace_id), data)
        self.assertEqual(response.status_code, 302)

        data['dialstring'] = '1234@example.org'
        response = self.client.post('/cospaces/{}/hooks/'.format(self.cospace_id), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(Dialout.objects.all().values_list('dialstring', flat=True)), {data['dialstring']})

        data['enable'] = ''
        response = self.client.post('/cospaces/{}/hooks/'.format(self.cospace_id), data)
        self.assertEqual(response.status_code, 302)

    def test_disconnect_session(self):
        data = {
            'form_action': 'disconnect_session',
            'session': 'test',
        }
        response = self.client.post('/cospaces/{}/hooks/'.format(self.cospace_id), data)
        self.assertEqual(response.status_code, 302)

    def test_remove_dialout(self):
        data = {
            'form_action': 'remove_dialout',
            'dialout': 1,
            'hook': '3',
        }
        response = self.client.post('/cospaces/{}/hooks/'.format(self.cospace_id), data)
        self.assertEqual(response.status_code, 302)

        dialout = Dialout.objects.create(hook=Hook.objects.create(customer=self.customer, provider=self.customer.get_provider()))
        data = {
            'form_action': 'remove_dialout',
            'dialout': dialout.pk,
            'hook': dialout.hook.pk,
        }
        response = self.client.post('/cospaces/{}/hooks/'.format(self.cospace_id), data)
        self.assertEqual(response.status_code, 302)

    def test_parse_and_hooks(self):

        self._init()

        dialout = ScheduledDialout.objects.create(customer=self.customer, provider=self.acano, provider_ref='testspace', ts_start=now(), ts_stop=now() + timedelta(minutes=30))

        part = dialout.add_part('schedule@dialout.com')

        self.assertEqual(part.backend_active, False)

        dialout.schedule()
        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            dialout.start()

        self.assertEqual(ScheduledDialoutPart.objects.get().dial_count, 1)
        self.assertEqual(ScheduledDialoutPart.objects.get().backend_active, True)

        dialout.start()
        self.assertEqual(ScheduledDialoutPart.objects.get().dial_count, 2)
        self.assertEqual(ScheduledDialoutPart.objects.get().backend_active, True)


        dialout.check_status()
        self.assertEqual(ScheduledDialoutPart.objects.get().dial_count, 2)

        # TODO simulate disconnect

        Hook.objects.handle_tag('callLegEnd', TestLeg())

        dialout.stop()
        self.assertEqual(ScheduledDialoutPart.objects.get().backend_active, False)


