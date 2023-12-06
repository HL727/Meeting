from django.test import TestCase
from django.urls import reverse

from customer.models import Customer
from meeting.models import Meeting
from provider.models.provider import Provider
from .initial import INITIAL_MESSAGES

from .invite import send_email_for_message, format_message_content
from .models import Message, String
from django.contrib.auth.models import User
from django.utils.timezone import now


class MessageTest(TestCase):

    def setUp(self):

        c = self.client

        Customer.objects.create(title='test')
        response = c.get(reverse('update_messages'))
        self.assertEqual(response.status_code, 302)

        u = User.objects.create_user(username='test', email='test@example.org', password='test')
        u.is_superuser = True
        u.is_staff = True
        u.save()

        response = c.post(reverse('login'), {'username': 'test', 'password': 'test'})
        self.assertEqual(response.status_code, 302)

    def test_messages(self):

        c = self.client

        messages = Message.objects.get_all()

        data = {
            'message_title': [m.type_title for m in messages],
            'message_id': [m.pk for m in messages],
            'message_content': [m.type_description for m in messages],
        }

        response = c.get(reverse('update_messages'))
        self.assertEqual(response.status_code, 200)

        response = c.post(reverse('update_messages'), data)
        self.assertEqual(response.status_code, 302)

        i = 0
        for m in Message.objects.get_all():

            self.assertEqual(m.title, data['message_title'][i])
            self.assertEqual(m.content, data['message_content'][i])
            self.assertEqual(m.id, data['message_id'][i])
            i += 1

    def test_default(self):
        customer = Customer.objects.create(title='test')

        Message.objects.create(customer=None, type=2, title='default2')
        customer_message = Message.objects.create(customer=customer, type=2, title='customer')
        Message.objects.create(customer=None, type=5, title='default')

        msg = Message.objects.get_by_type(2, customer)
        self.assertEqual(msg.title, 'customer')

        customer_message.active = False
        customer_message.save()

        msg = Message.objects.get_by_type(2, customer)
        self.assertEqual(msg.title, 'default2')

        msg = Message.objects.get_by_type(5, customer)
        self.assertEqual(msg.title, 'default')

    def test_send_mail(self):
        customer = Customer.objects.create(title='test')
        provider = Provider.objects.create(type=0, subtype=0, ip='127.0.0.1', title='test', is_standard=True, username='servertest', password='test')

        meeting = Meeting.objects.create(provider=provider, customer=customer, creator_ip='127.0.0.1', ts_stop=now(), ts_start=now())

        message = Message.objects.create(customer=customer, type=2, title='customer')

        mail = send_email_for_message(message.to_dict(meeting), ['test@example.org'])

        self.assertTrue(isinstance(mail, ValueError))
        self.assertEqual(str(mail), 'Message is empty')

        message.content = 'Test new mail'
        message.save()

        mail = send_email_for_message(message.to_dict(meeting), ['test@example.org'])

        self.assertEqual(mail, 1)

        mail_content = format_message_content('SUBJECTtest', 'CONTENTtest')

        self.assertIn('SUBJECTtest</h1>', mail_content)
        self.assertIn('SUBJECTtest</title>', mail_content)
        self.assertIn('CONTENTtest', mail_content)

    def test_extend_other(self):
        customer = Customer.objects.create(title='test')
        Message.objects.create(customer=customer, type=2, title='customer')
        Message.objects.create(customer=customer, type=5, title='extend', extend_other=2)


        msg = Message.objects.get_by_type(5, customer)
        self.assertEqual(msg.title, 'customer')

    def test_extend_other_default(self):
        customer = Customer.objects.create(title='test')
        Message.objects.create(customer=customer, type=5, title='extend', extend_other=2)

        Message.objects.create(customer=None, type=2, title='default', extend_other=5)
        Message.objects.create(customer=None, type=5, title='default_2')

        msg = Message.objects.get_by_type(5, customer)
        self.assertEqual(msg.title, 'default_2')

        Message.objects.filter(type=2, customer__isnull=True).update(extend_other=5)

        msg = Message.objects.get_by_type(5, customer)
        self.assertEqual(msg.title, 'default_2')

        msg = Message.objects.get_by_type(2, customer)
        self.assertEqual(msg.title, 'default_2')

    def test_strings(self):

        c = self.client

        string = String.objects.get_all()

        data = {
            'string_title': [s.type_title for s in string],
            'string_id': [s.pk for s in string],
        }

        response = c.post(reverse('update_messages'), data)
        self.assertEqual(response.status_code, 302)

        i = 0
        for s in String.objects.get_all():

            self.assertEqual(s.title, data['string_title'][i])
            self.assertEqual(s.id, data['string_id'][i])
            i += 1


class MessageFormatTest(TestCase):
    def setUp(self):
        super().setUp()
        provider = Provider.objects.create(type=0, subtype=0, ip='127.0.0.1', title='test', is_standard=True, username='servertest', password='test')
        customer = Customer.objects.create(title='test', shared_key='test_key')

        self.meeting = Meeting.objects.create(provider=provider, customer=customer, creator_ip='127.0.0.1', ts_stop=now(), ts_start=now())
        self.message = Message.objects.create(type=8)

    def test_format_has_positive_conditional_rendering_for_password(self):
        self.given_meeting_keys(password='value')

        self.when_formatting_message_content('before | {if password}this should be rendered, containing the "{password}"{endif} | after')

        self.then_renders('before | this should be rendered, containing the "value" | after')

    def test_format_leaves_out_positive_conditional_rendering_if_condition_is_false(self):
        self.given_meeting_keys(password='')

        self.when_formatting_message_content('before | {if password}this should not be rendered, containing the "{password}"{endif} | after')

        self.then_renders('before |  | after')

    def test_format_has_positive_conditional_rendering_for_any_key(self):
        self.when_formatting_message_content('before | {if some_made_up_key}this should not be rendered{endif} | after')

        self.then_renders('before |  | after')

    def test_format_leaves_out_negative_conditional_rendering_if_condition_is_true(self):
        self.given_meeting_keys(password='password_exists')

        self.when_formatting_message_content('before | {if not password}this should not be rendered{endif} | after')

        self.then_renders('before |  | after')

    def test_format_has_negative_conditional_rendering_for_any_key(self):
        self.when_formatting_message_content('before | {if not some_made_up_key}this should be rendered{endif} | after')

        self.then_renders('before | this should be rendered | after')

    def given_meeting_keys(self, **kwargs):
        for key, value in list(kwargs.items()):
            setattr(self.meeting, key, value)

    def when_formatting_message_content(self, content):
        self.actual = self.message.format(self.meeting, content=content)

    def then_renders(self, expected):
        self.assertEqual(self.actual, expected)


class InitialMessagesTestCase(TestCase):

    def setUp(self):
        super().setUp()

        self.no_default = {'outlook_message', 'acano_client'} & set(Message.TYPES.id_map)
        self.dynamic_defaults = {'sandbox'}

        self.enabled_types = set(Message.ENABLED_TYPES.id_map.keys())
        self.initial_types = {m.name for m in INITIAL_MESSAGES}

    def test_all_messages_have_defaults(self):

        # check so all types have defaults
        self.assertTrue(len(self.enabled_types))
        self.assertEqual(self.enabled_types - self.initial_types - self.no_default, set(),
                         'There are message types without default values in ui_message.initial.py')

    def test_set_initial(self):
        total_count = len(self.enabled_types.union(self.dynamic_defaults) - self.no_default)

        self.assertEqual(Message.objects.count(), 0)

        result = Message.objects.init_default()
        self.assertEqual(len(result), total_count)

        self.assertEqual(Message.objects.filter(content='').count(), 0)
        self.assertEqual(Message.objects.exclude(content='').count(), total_count)



