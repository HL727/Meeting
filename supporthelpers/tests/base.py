from conferencecenter.tests.base import ConferenceBaseTest
from django.utils.timezone import now
from datetime import timedelta
from django.contrib.auth.models import User


class SupporthelpersTestCaseBase(ConferenceBaseTest):

    provider_subtype = 1

    def setUp(self):
        self._init()
        from meeting.models import Meeting

        self.provider = self.customer.lifesize_provider

        self.cospace_id = '22f67f91-1948-47ec-ad4f-4793458cfe0c'
        self.call_id = '935a38b8-0a80-4965-9db4-f02ab1a813d2'
        self.call_leg_id = '976dacd8-bc6b-4526-8bb7-d9050740b7c7'
        self.user_id = 'userguid111'
        self.user_jid = 'username@example.org'
        self.user_jid_without_space = 'username@example.org'

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')
        self.client.session['customer_id'] = self.customer.id
        self.client.session.save()

        self.meeting = Meeting.objects.create(provider=self.provider, customer=self.customer, creator_ip='127.0.0.1',
                                              ts_start=now(), ts_stop=now() + timedelta(hours=1), backend_active=True, provider_ref=self.cospace_id)  # TODO


class SupporthelpersTestCasePexipBase(SupporthelpersTestCaseBase):

    def setUp(self):
        super().setUp()
        self.user_id = '1'
        self.user_jid = 'test@example.org'
        self.user_jid_without_space = 'user2@example.org'
        self.cospace_id = 222
        self.meeting.provider_ref = self.cospace_id
        self.meeting.save()

    provider_subtype = 2
