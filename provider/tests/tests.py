import urllib.request, urllib.parse, urllib.error
import uuid
from datetime import timedelta

from django.urls import reverse
import json

from django.utils.http import urlencode
from django.utils.timezone import now

from conferencecenter.tests.base import ConferenceBaseTest, ThreadedTestCase
from datastore.models.base import ProviderSync
from meeting.models import Meeting
from recording.models import MeetingRecording
from provider.models.utils import date_format, parse_timestamp
from provider.models.provider_data import SettingsProfile
from provider import tasks
from django.conf import settings

SKIP_KEY_COMPARE = ('key', 'creator', 'password', 'room_info', 'recording', 'webinar')
DEFAULT_START_FUTURE = 0


class MeetingTestCaseBase(ConferenceBaseTest):

    def setUp(self):
        self._init()  # base
        if not self.disable_clearsea:
            self.customer.always_enable_external = True
            self.customer.save()

    def tearDown(self):
        from provider.ext_api.acano import AcanoAPI
        from provider.ext_api.clearsea import ClearSeaAPI
        super().tearDown()
        AcanoAPI.unbook_expired()
        ClearSeaAPI.unbook_expired()

    def get_times(self, duration=60, future=DEFAULT_START_FUTURE):
        ts_start = now().replace(microsecond=0) + timedelta(minutes=future)
        return ts_start, ts_start + timedelta(minutes=duration)

    def get_formatted_times(self, duration=60, future=DEFAULT_START_FUTURE):
        ts_start, ts_stop = self.get_times(duration=duration, future=future)
        return date_format(ts_start), date_format(ts_stop)

    def get_formatted_time_kwargs(self, duration=60, future=DEFAULT_START_FUTURE):
        ts_start, ts_stop = self.get_formatted_times(duration=duration, future=future)
        return {'ts_start': ts_start, 'ts_stop': ts_stop}

    def test_invalid_key(self):

        c = self.client

        # invalid key
        data = {
            'creator': 'john',
            'key': '_invalid',
            'internal_clients': 1,
        }

        if self.disable_clearsea:
            pass
        else:
            data['external_clients'] = 3

        data.update({
            **self.get_formatted_time_kwargs(),
        })

        files = {}
        result = c.post(reverse('api_book'), data, files=files)

        self.assertEqual(result.status_code, 403)

        json_data = json.loads(result.content)
        self.assertEqual(json_data.get('status'), 'Error')
        self.assertEqual(json_data.get('type'), 'InvalidKey')

    def test_invalid_data(self):

        c = self.client

        data = {
            'key': self.customer_shared_key,
            'internal_clients': 1,
            'ts_start': 'Invalid',
        }

        files = {}
        result = c.post(reverse('api_book'), data, files=files)

        self.assertEqual(result.status_code, 400)

        json_data = json.loads(result.content)
        self.assertEqual(json_data.get('status'), 'Error')
        self.assertEqual(json_data.get('type'), 'InvalidData')
        self.assertIn('ts_start', json_data.get('fields'))
        self.assertIn('creator', json_data.get('fields'))

    def test_book(self):

        c = self.client

        data = {
            'creator': 'john',
            'key': self.customer_shared_key,
            'internal_clients': 1,
            'room_info': '''[{"title": "test", "dialstring": "1.2.3.4##1234", "dialout": true}]''',
            'recording': '''{"record": true, "is_live": true, "is_public": true}''',
        }
        if self.disable_clearsea:
            if self.only_internal:
                data['only_internal'] = True
        else:
            data['external_clients'] = 3

        data.update({
            **self.get_formatted_time_kwargs(),
        })

        # set to invalid session to test
        self.lifesize.session_id = 'Invalid'
        self.lifesize.session_expires = now() + timedelta(days=7)
        self.lifesize.save()

        self.clearsea.session_id = 'Invalid'
        self.clearsea.session_expires = now() + timedelta(days=7)
        self.clearsea.save()

        self.videocenter.session_id = 'Invalid'
        self.videocenter.session_expires = now() + timedelta(days=7)
        self.videocenter.save()

        files = {}
        result = c.post(reverse('api_book'), data, files=files)

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))

        meeting_id = json_data.get('meeting_id')
        meeting = Meeting.objects.get_by_id_key(meeting_id)
        self.assertEqual(meeting.backend_active, True)
        self.assertEqual(meeting.customer_confirmed, None)
        self.assertEqual(meeting.room_info, data['room_info'])

        for k in data:
            if k in SKIP_KEY_COMPARE or self.customer.get_provider().is_acano:
                continue
            self.assertEqual(data.get(k), json_data.get(k), '%s is not the same (%s != %s)' % (k, data.get(k), json_data.get(k)))

        self.compare_data(meeting)

        # if meeting.should_book_external_client:  # TODO
            # self.assertNotEquals(meeting.get_external_account(), None)

    def _test_moderator_and_participant_messages(
        self, meeting_data=None, meeting_settings_data=None
    ):

        from ui_message.models import Message

        Message.objects.update_or_create(
            type=Message.TYPES.webinar, defaults=dict(content='{room_number} {web_url}')
        )
        Message.objects.update_or_create(
            type=Message.TYPES.webinar_moderator, defaults=dict(content='{room_number} {web_url}')
        )

        c = self.client

        data = {
            'creator': 'john',
            'key': self.customer_shared_key,
            'internal_clients': 1,
            'password': 'pwd123',
            'external_clients': 3,
            **self.get_formatted_time_kwargs(),
            **(meeting_data or {}),
            'settings': json.dumps(
                {
                    'force_encryption': True,
                    'disable_chat': True,
                    **(meeting_settings_data or {}),
                }
            ),
            'format': 'html',
        }
        result = c.post(reverse('api_book'), data)

        meeting = Meeting.objects.get_by_id_key(result.json()['meeting_id'])

        connection_data = meeting.get_connection_data()
        message = Message.objects.get_for_meeting(meeting).format(meeting)

        meeting.is_moderator = True
        moderator_connection_data = meeting.get_connection_data()
        moderator_message = Message.objects.get_for_meeting(meeting).format(meeting)

        api = self.customer.get_api()

        self.assertNotEqual(connection_data['web_url'], moderator_connection_data['web_url'])

        if api.provider.is_acano:

            accessmethod_request_data = self._mock_requests.find_data(
                'POST coSpaces/22f67f91-1948-47ec-ad4f-4793458cfe0c/accessMethods'
            )
            if meeting.is_webinar:
                self.assertTrue(accessmethod_request_data.get('uri'))
                self.assertEqual(
                    accessmethod_request_data.get('callLegProfile'), api._get_webinar_call_legs()[1]
                )
            else:
                self.assertEqual(accessmethod_request_data.get('uri'), '61170')

            self.assertTrue(isinstance(accessmethod_request_data.get('callLegProfile'), str))

            self.assertEqual(meeting.provider_ref, '61170')
            self.assertEqual(meeting.provider_secret, 'BBBBBBBBBBBBBBBBBBBBBB')

            self.assertEqual(connection_data['dialstring'], '61170@127.0.0.1')
            self.assertEqual(
                connection_data['web_url'],
                'https://127.0.0.1/invited.sf?id=61170&secret=BBBBBBBBBBBBBBBBBBBBBB',
            )

            if not meeting.is_webinar:
                self.assertEqual(moderator_connection_data['dialstring'], '61170@127.0.0.1')
                self.assertEqual(
                    moderator_connection_data['web_url'],
                    'https://127.0.0.1/invited.sf?id=61170&secret=abc123',
                )
            else:
                self.assertNotEqual(
                    connection_data['uri_numeric'], moderator_connection_data['uri_numeric']
                )

        elif api.provider.is_pexip:
            self.assertEqual(connection_data['dialstring'], moderator_connection_data['dialstring'])
            self.assertEqual(
                connection_data['uri_numeric'], moderator_connection_data['uri_numeric']
            )
            self.assertNotEqual(connection_data['password'], moderator_connection_data['password'])
            self.assertIn(
                connection_data['password'],
                connection_data['web_url'],
            )
            self.assertIn(
                moderator_connection_data['password'],
                moderator_connection_data['web_url'],
            )

        self.assertIn(connection_data['web_url'], message)
        self.assertIn(moderator_connection_data['web_url'], moderator_message)

        # rebook
        response = c.post(reverse('api_rebook', args=[meeting.id_key]), data)
        self.assertEqual(response.status_code, 200)

        new_meeting = Meeting.objects.get_by_id_key(response.json()['meeting_id'])
        new_connection_data = new_meeting.get_connection_data()

        new_meeting.is_moderator = True
        new_moderator_connection_data = new_meeting.get_connection_data()

        self.assertEqual(connection_data, new_connection_data)
        self.assertEqual(moderator_connection_data, new_moderator_connection_data)

    def test_lobby_pin(self):
        provider = self.customer.get_api().provider
        if not provider.is_acano and not provider.is_pexip:
            return
        self._test_moderator_and_participant_messages(
            meeting_settings_data={'lobby_pin': '4564234'}
        )

    def test_webinar(self):
        provider = self.customer.get_api().provider
        if not provider.is_acano and not provider.is_pexip:
            return
        self._test_moderator_and_participant_messages(
            meeting_data={'webinar': json.dumps({'is_webinar': True, 'moderator_pin': '6543'})}
        )

    def test_webinar_moderator_layout(self):
        provider = self.customer.get_api().provider
        if not provider.is_acano and not provider.is_pexip:
            return
        self._test_moderator_and_participant_messages(
            meeting_data={
                'webinar': json.dumps(
                    {'is_webinar': True, 'moderator_pin': '6543', 'moderator_layout': 'automatic'}
                )
            }
        )

    def test_member(self):

        data = {
            'creator': 'username@example.org',
            'key': self.customer_shared_key,
            'internal_clients': 1,
            'password': 'pwd123',
            'external_clients': 3,
            **self.get_formatted_time_kwargs(),
            'settings': json.dumps(
                {
                    'force_encryption': True,
                    'disable_chat': True,
                }
            ),
            'format': 'html',
        }
        self.set_url_state('owner-cospace')
        result = self.client.post(reverse('api_book'), data)
        meeting = Meeting.objects.get_by_id_key(result.json()['meeting_id'])

        if self.customer.get_api().provider.is_acano:
            member_request_data = self._mock_requests.find_data(
                'coSpaces/{}/coSpaceUsers'.format(meeting.provider_ref2)
            )
            self.assertTrue(member_request_data)

    def test_book_extra_settings(self):

        from ui_message.models import Message
        Message.objects.update_or_create(type=Message.TYPES.webinar, defaults=dict(content='{room_number} {web_url}'))
        Message.objects.update_or_create(type=Message.TYPES.webinar_moderator, defaults=dict(content='{room_number} {web_url}'))

        c = self.client

        data = {
            'creator': 'john',
            'key': self.customer_shared_key,
            'internal_clients': 1,
            'password': 'pwd123',
            'room_info': '''[{"title": "test", "dialstring": "1.2.3.4##1234", "dialout": true}]''',
            'recording': '''{"record": true, "is_live": true, "is_public": true}''',
            'external_clients': 3,
            **self.get_formatted_time_kwargs(),
            'settings': json.dumps({
                'force_encryption': True,
                'disable_chat': True,
                'lobby_pin': '4564234',
            }),
            'format': 'html',
        }

        files = {}
        result = c.post(reverse('api_book'), data, files=files)
        if self.customer.get_api().provider.is_acano:
            request_data = self._mock_requests.find_data('coSpaces/')
            call_profile = SettingsProfile.objects.get(profile_id=request_data['callProfile'])
            self.assertEqual(call_profile.result.get('messageBoardEnabled'), 'false')

            call_leg_profile = SettingsProfile.objects.get(profile_id=request_data['callLegProfile'])
            self.assertEqual(call_leg_profile.result.get('needsActivation'), 'true')
            self.assertEqual(call_leg_profile.result.get('sipMediaEncryption'), 'required')

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))
        self.assertIn(data['password'], json_data.get('message'))
        self.assertNotIn('4564234', json_data.get('message'))

        meeting_id = json_data.get('meeting_id')
        meeting = Meeting.objects.get_by_id_key(meeting_id)
        self.assertEqual(meeting.backend_active, True)

        message = Message.objects.get_for_meeting(meeting)
        self.assertEqual(message.type, Message.TYPES.clearsea_meeting_pin)

        message_content = message.format(meeting)
        self.assertIn(data['password'], message_content)
        self.assertNotIn('4564234', message_content)

        meeting.is_moderator = True
        message_content = message.format(meeting)
        self.assertNotIn(data['password'], message_content)
        self.assertIn('4564234', message_content)

    def test_confirm(self):

        c = self.client
        meeting = self._book_meeting()
        meeting_id = meeting.id_key

        result = c.post(
            reverse('api_meeting_confirm', args=[meeting_id])
            + '?key={}'.format(self.customer_shared_key)
        )

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertEqual(json_data.get('meeting_id'), meeting_id)

        meeting_id = json_data.get('meeting_id')
        self.assertEqual(Meeting.objects.get_by_id_key(meeting_id).backend_active, True)
        self.assertTrue(Meeting.objects.get_by_id_key(meeting_id).customer_confirmed)

    def test_rebook(self):

        c = self.client

        meeting = self._book_meeting()
        meeting_id = meeting.id_key
        provider_ref = Meeting.objects.get_by_id_key(meeting_id).provider_ref

        data = {
            'creator': 'john',
            'key': self.customer_shared_key,
            **self.get_formatted_time_kwargs(future=10),
            'internal_clients': 1,
            'password': '1234',
            'webinar': '{}',
        }
        if self.disable_clearsea:
            if self.only_internal:
                data['only_internal'] = True
        else:
            data['external_clients'] = 2

        result = c.post(reverse('api_rebook', args=[meeting_id]), data)

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertEqual(json_data['status'], 'OK')
        self.assertTrue(json_data.get('meeting_id'))
        self.assertTrue(json_data.get('meeting_id') != meeting_id)

        self.assertEqual(Meeting.objects.get_by_id_key(meeting_id).backend_active, False)
        self.assertEqual(meeting_id, Meeting.objects.get_by_id_key(json_data.get('meeting_id')).parent.id_key)

        meeting_id = json_data.get('meeting_id')

        for k in data:
            if k in SKIP_KEY_COMPARE or self.customer.get_provider().is_acano:
                continue
            self.assertEqual(data.get(k), json_data.get(k), '%s is not the same' % k)

        self.assertIsNone(Meeting.objects.get_by_id_key(meeting_id).customer_confirmed)
        self.assertEqual(Meeting.objects.get_by_id_key(meeting_id).password, data['password'])

        self.compare_data(Meeting.objects.get_by_id_key(meeting_id))

        if meeting.should_book_external_client:
            self.assertNotEqual(Meeting.objects.get_by_id_key(meeting_id).get_external_account(), None)

        # rebook external
        if meeting.should_book_external_client:
            ext = Meeting.objects.get_by_id_key(meeting_id).get_external_account()
            self.assertTrue(ext.backend_active)
            ext.provider.get_api(ext.meeting.customer).unbook(ext)

            ext = Meeting.objects.get_by_id_key(meeting_id).get_external_account()
            self.assertFalse(ext.backend_active)

            result = c.post(reverse('api_rebook', args=[meeting_id]), data)
            self.assertEqual(result.status_code, 200)

            json_data = json.loads(result.content)
            meeting_id = json_data.get('meeting_id')

            ext = Meeting.objects.get_by_id_key(meeting_id).get_external_account()
            self.assertTrue(ext.backend_active)

        self.assertEqual(provider_ref, Meeting.objects.get_by_id_key(meeting_id).provider_ref)

    def test_update_settings(self):

        c = self.client

        meeting = self._book_meeting()
        meeting_id = meeting.id_key

        # settings

        data = {
            'key': self.customer_shared_key,
            'recording': json.dumps({'is_live': True, 'is_public': True, 'name': 'test', 'record': True}),
            'room_info': json.dumps([{'title': 'test', 'dialstring': '1.2.3.4##1234', 'dialout': True}]),
            'layout': 'allEqual',
        }
        result = c.post(reverse('api_meeting_settings', args=[meeting_id]), data)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'OK')

        new_meeting = Meeting.objects.get(pk=meeting.pk)
        self.assertEqual(meeting.ts_start, new_meeting.ts_start)
        self.assertEqual(meeting.ts_stop, new_meeting.ts_stop)

    def test_unbook(self):

        c = self.client

        meeting = self._book_meeting()
        meeting_id = meeting.id_key

        data = {'key': self.customer_shared_key}
        self.assertEqual(Meeting.objects.get_by_id_key(meeting_id).backend_active, True)
        result = c.post(reverse('api_unbook', args=[meeting_id]), data)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(Meeting.objects.get_by_id_key(meeting_id).backend_active, False)

        self.compare_data(Meeting.objects.get_by_id_key(meeting_id))

    def test_rest_rebook(self):

        c = self.client

        meeting = self._book_meeting()
        meeting_id = meeting.id_key
        provider_ref = Meeting.objects.get_by_id_key(meeting_id).provider_ref

        data = {
            'creator': 'john',
            'key': self.customer_shared_key,
            **self.get_formatted_time_kwargs(future=10),
            'internal_clients': 1,
            'password': '1234',
            'webinar': '{}',
            'confirm': True,
            'only_internal': self.only_internal,
        }

        result = c.put(reverse('api_meeting_rest', args=[meeting_id]), urllib.parse.urlencode(data))

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))
        self.assertTrue(json_data.get('meeting_id') != meeting_id)

        meeting_id = json_data['meeting_id']

        self.assertIsNotNone(Meeting.objects.get_by_id_key(meeting_id).customer_confirmed)

        self.compare_data(Meeting.objects.get_by_id_key(meeting_id))

        self.assertEqual(provider_ref, Meeting.objects.get_by_id_key(meeting_id).provider_ref)

    def test_rest_unbook(self):

        c = self.client

        meeting = self._book_meeting()
        meeting_id = meeting.id_key

        # rest unbook
        data = {'key': self.customer_shared_key}
        files = {}
        result = c.post(reverse('api_unbook', args=[meeting_id]), data, files=files)

        self.assertEqual(result.status_code, 200)

        self.compare_data(Meeting.objects.get_by_id_key(meeting_id))
        # TODO check for double unbook

    def test_meeting_view(self):

        c = self.client

        meeting = self._book_meeting()
        meeting_id = meeting.id_key

        data = {'key': self.customer_shared_key}
        result = c.get(reverse('api_meeting_rest', args=[meeting_id]), data)
        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))

    def test_recurring(self):

        c = self.client
        from endpoint.models import Endpoint

        endpoint = Endpoint.objects.create(title='test', customer=self.customer)

        data = {
            'creator': 'john',
            'key': self.customer_shared_key,
            'internal_clients': 1,
            'room_info': json.dumps(
                [
                    {
                        'endpoint': endpoint.email_key,
                    },
                    {
                        'dialout': True,
                        'dialstring': '1234@example.org',
                    },
                ]
            ),
        }
        if self.disable_clearsea:
            pass
        else:
            data['external_clients'] = 3

        # invalid recurring
        data.update({
            **self.get_formatted_time_kwargs(),
            'recurring': 'ASDFFREQ=DAILY;COUNT=5;INTERVAL=10',
            'recurring_exceptions': '20140830T060000Z',
        })

        files = {}
        result = c.post(reverse('api_book'), data, files=files)

        self.assertEqual(result.status_code, 400)
        json_data = json.loads(result.content)

        self.assertEqual(json_data.get('status'), 'Error')
        self.assertEqual(json_data.get('type'), 'InvalidData')

        # valid recurring
        data.update({
            'recurring': 'FREQ=DAILY;COUNT=5;INTERVAL=10',
        })
        result = c.post(reverse('api_book'), data, files=files)

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))

        meeting_id = json_data.get('meeting_id')
        meeting = Meeting.objects.get_by_id_key(meeting_id)

        self.assertEqual(meeting.backend_active, True)
        self.assertEqual(meeting.customer_confirmed, None)

        self.assertEqual(meeting.recurring_master.occurences.count(), 5)
        for occurence in meeting.recurring_master.occurences.all():
            self.assertTrue(occurence.backend_active)
            self.assertEqual(occurence.endpoints.all().count(), 1)
            self.assertEqual(occurence.dialouts.all().count(), 1)

        for k in data:
            if k in SKIP_KEY_COMPARE or self.customer.get_provider().is_acano:
                continue
            self.assertEqual(data.get(k), json_data.get(k), '%s is not the same' % k)

        self.compare_data(meeting)


class LifesizeTestCase(MeetingTestCaseBase, ConferenceBaseTest):

    provider_subtype = 0
    disable_clearsea = True
    only_internal = False


class LifesizeInternalTestCase(MeetingTestCaseBase, ConferenceBaseTest):

    provider_subtype = 0
    disable_clearsea = True
    only_internal = True


class LifesizeClearSeaTestCase(MeetingTestCaseBase, ConferenceBaseTest):

    provider_subtype = 0
    disable_clearsea = False
    only_internal = False


class AcanoMeetingTestCase(MeetingTestCaseBase, ConferenceBaseTest):

    disable_clearsea = True
    provider_subtype = 1
    only_internal = False


class PexipMeetingTestCase(MeetingTestCaseBase, ConferenceBaseTest):

    disable_clearsea = True
    provider_subtype = 2
    only_internal = False


class AcanoClearSeaMeetingTestCase(MeetingTestCaseBase, ConferenceBaseTest):

    provider_subtype = 1
    disable_clearsea = False
    only_internal = False


class AcanoTestCase(ConferenceBaseTest):

    provider_subtype = 1

    def setUp(self):
        self._init()

    def test_cluster(self):
        from provider.models.provider import Cluster, Provider

        cluster = Cluster.objects.create(type=Cluster.TYPES.acano_cluster, title='test')

        api = cluster.get_api(self.customer)
        self.assertEqual(
            sum(1 for _x in api.iter_clustered_provider_api(only_call_bridges=False)), 0
        )

        Provider.objects.create(cluster=cluster, title='test', hostname='test')

        api = cluster.get_api(self.customer)
        self.assertEqual(
            sum(1 for _x in api.iter_clustered_provider_api(only_call_bridges=False)), 1
        )

    def test_sync(self):
        c = self.client

        sync_data = {
            'key': self.customer_shared_key,
        }
        response = c.post(reverse('api_sync_users'), data=sync_data)
        self.assertEqual(response.status_code, 200)

    def test_ext_profiles(self):
        api = self.customer.get_api()
        api._get_force_encryption_call_leg()
        api._get_force_encryption_call_leg(sync=True)

        api._get_webinar_call_legs(force_encryption=True)
        api._get_webinar_call_legs(force_encryption=True, sync=True)

        api._get_no_chat_call_profile()
        api._get_no_chat_call_profile(sync=True)

        api._get_needs_activation_call_leg_profile(force_encryption=True)
        api._get_needs_activation_call_leg_profile(force_encryption=True, sync=True)

        api.update_callbranding('callBranding-1948-47ec-ad4f-4793458cfe0c', 'test', 'test')

    def test_get_tenants(self):
        self.customer.get_api().get_tenants()


class AcanoAdvancedMeetingTestCase(ConferenceBaseTest):
    provider_subtype = 1

    def setUp(self):
        self._init()

    def test_webinar(self):

        from ui_message.models import Message

        c = self.client

        Message.objects.update_or_create(type=Message.TYPES.webinar, defaults=dict(content='{room_number} {web_url}'))
        Message.objects.update_or_create(type=Message.TYPES.webinar_moderator, defaults=dict(content='{room_number} {web_url}'))

        webinar_data = {
            'title': 'Ett webinar',
            'key': self.customer_shared_key,
            'uri': 'test',
            'password': '1234',
            'moderator_password': '9999',
            'group': 'mividas',
            'enable_chat': 1,
            'customer': self.customer.pk,
        }
        response = c.post(reverse('api_webinar'), data=webinar_data)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.json()['status'], 'OK')

        webinar_id = response.json()['meeting_id']

        # list webinars
        webinar_data = {
            'key': self.customer_shared_key,
        }
        response = c.get(reverse('api_webinar_list'), webinar_data)
        self.assertEqual(response.status_code, 200)

        response = c.get(
            reverse('api_meeting_rest', args=[webinar_id])
            + '?key={}'.format(self.customer_shared_key)
        )
        self.assertEqual(response.status_code, 200)

        response = c.get(
            reverse("api_meeting_webinar_moderator_message", args=[webinar_id]),
            {"key": self.customer_shared_key},
        )
        self.assertEqual(response.status_code, 200)

        meeting = Meeting.objects.get_by_id_key(webinar_id)
        webinar = meeting.webinars.get()

        participant_join_url = meeting.join_url

        self.assert_(webinar.provider_ref)
        self.assertIn(meeting.provider_ref, meeting.as_dict(message_format='html')['message'])
        self.assertIn(meeting.join_url, meeting.as_dict(message_format='html')['message'])
        if meeting.api.provider.is_acano:
            self.assertNotIn(
                webinar.provider_ref, meeting.as_dict(message_format='html')['message']
            )
            self.assertNotIn(webinar.join_url, meeting.as_dict(message_format='html')['message'])
            self.assertNotEqual(meeting.join_url, webinar.join_url)

        meeting.is_moderator = True
        self.assertIn(webinar.provider_ref, meeting.as_dict(message_format='html')['message'])
        self.assertIn(webinar.join_url, meeting.as_dict(message_format='html')['message'])
        if meeting.api.provider.is_acano:
            self.assertNotIn(
                meeting.provider_ref, meeting.as_dict(message_format='html')['message']
            )
            self.assertNotIn(
                participant_join_url, meeting.as_dict(message_format='html')['message']
            )

    def test_change_time(self, extra_data=None):

        meeting = self._book_meeting(**(extra_data or {}))
        meeting.schedule()

        data = {
            'title': 'New title',
            'ts_start': date_format(now() + timedelta(days=1)),
            'ts_stop': date_format(now() + timedelta(days=1, hours=1)),
            'key': self.customer_shared_key,
        }
        response = self.client.post(reverse('api_meeting_settings', args=[meeting.id_key]), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'OK')

        new_meeting = Meeting.objects.get(pk=meeting.pk)
        self.assertEqual(new_meeting.ts_start, parse_timestamp(data['ts_start']))
        self.assertEqual(new_meeting.ts_stop, parse_timestamp(data['ts_stop']))
        self.assertEqual(new_meeting.title, data['title'])

    def test_change_pin(self, extra_data=None):

        meeting = self._book_meeting(**(extra_data or {}))
        meeting.schedule()

        data = {
            'password': '6789',
            'key': self.customer_shared_key,
        }
        response = self.client.post(reverse('api_meeting_settings', args=[meeting.id_key]), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'OK')
        self.assertIn(data['password'], response.content.decode('utf-8'))

        new_meeting = Meeting.objects.get(pk=meeting.pk)
        self.assertEqual(new_meeting.password, data['password'])

    def test_change_moderator_pin(self, extra_data=None):

        meeting = self._book_meeting(**(extra_data or {}))
        meeting.schedule()

        data = {
            'moderator_password': '6789',
            'key': self.customer_shared_key,
        }
        response = self.client.post(
            reverse('api_meeting_settings', args=[meeting.id_key]) + '?include_moderator_data=1',
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'OK')
        self.assertIn(data['moderator_password'], response.content.decode('utf-8'))

        new_meeting = Meeting.objects.get(pk=meeting.pk)
        self.assertEqual(new_meeting.moderator_password, data['moderator_password'])

    def test_change_time_recording(self):

        self.test_change_time({
            'recording': json.dumps({'is_live': True, 'is_public': True, 'name': 'test', 'record': True}),
            'room_info': json.dumps([{'title': 'test', 'dialstring': '1.2.3.4##1234', 'dialout': True}]),
        })

    def test_unbook_meeting_webinar(self):

        meeting = self._book_meeting()

        meeting.webinar = json.dumps({
            'moderator_pin': '1234',
            'enable_chat': False,
            'uri': 'webinar_test',
            'group': 'afd',
        })

        meeting.api.webinar(meeting)
        meeting.api.unbook(meeting)

        meeting = Meeting.objects.get(pk=meeting.pk)
        self.assertFalse(meeting.backend_active)
        self.assertFalse(meeting.is_superseded)

    def test_cospaces_api(self):

        c = self.client
        cospace_data = {
            'title': 'Ett cospace',
            'key': self.customer_shared_key,
            'uri': 'test',
            'layout': 'telepresence',
            'call_id': 12345,
            'password': '1234',
            'moderator_password': '9999',
            'group': 'mindspace',
            'enable_chat': 1,
            'lobby': 1,
            'customer': self.customer.pk,
        }
        response = c.post(reverse('api_cospace'), data=cospace_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['status'], 'OK')

        cospace_id = json.loads(response.content)['rest_url'].strip('/').split('/')[-1]

        # list
        webinar_data = {
            'key': self.customer_shared_key,
        }
        response = c.get(reverse('api_cospace_list'), webinar_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)), 1)

        # update
        response = c.post(reverse('api_cospace', args=[cospace_id]), data=cospace_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['status'], 'OK')

        key = {'key': self.customer_shared_key}

        # get
        response = c.get(reverse('api_cospace', args=[cospace_id]), data=key)
        self.assertEqual(response.status_code, 200)

        # add member
        response = c.post(
            reverse("api_cospace_members", args=[cospace_id]),
            data=dict(add="username2@example.org", **key),
        )
        self.assertEqual(response.status_code, 200)

        # remove member
        response = c.post(
            reverse("api_cospace_members", args=[cospace_id]),
            data=dict(remove="username@example.org", **key),
        )
        self.assertEqual(response.status_code, 200)

        # delete
        response = c.delete(reverse("api_cospace", args=[cospace_id]) + "?" + urlencode(key))
        self.assertEqual(response.status_code, 200)

    def test_set_cospace_stream_urls(self):

        from .. import tasks
        tasks.set_cospace_stream_urls()

    def test_unbook_expired(self):

        self.customer.get_api().unbook_expired()

    def test_sync_ldap(self):

        self.customer.get_api().sync_ldap()


class PexipAdvancedMeetingTestCase(AcanoAdvancedMeetingTestCase):
    provider_subtype = 2

    def test_cospaces_api(self):
        return  # TODO add support


class CacheClusterDataTestCase(ThreadedTestCase, ConferenceBaseTest):

    def setUp(self):
        self._init()
        super().setUp()

    def test_sync_provider_data(self):
        self.assertEqual(ProviderSync.objects.all().count(), 0)

        from provider.tasks import cache_cluster_data, cache_single_cluster_data
        for _i in range(2):
            cache_cluster_data()
            if not settings.CELERY_TASK_ALWAYS_EAGER:
                cache_single_cluster_data(self.acano.cluster_id)
                cache_single_cluster_data(self.pexip.cluster_id)

        self.assertEqual(ProviderSync.objects.filter(provider=self.acano.cluster).count(), 1)
        self.assertEqual(ProviderSync.objects.filter(provider=self.pexip.cluster).count(), 1)

    def test_sync_provider_data_incremental(self):
        self.assertEqual(ProviderSync.objects.all().count(), 0)

        from provider.tasks import cache_cluster_data_incremental, cache_single_cluster_data_incremental
        for _i in range(2):
            cache_cluster_data_incremental()
            if not settings.CELERY_TASK_ALWAYS_EAGER:
                cache_single_cluster_data_incremental(self.acano.cluster_id)
                cache_single_cluster_data_incremental(self.pexip.cluster_id)

        self.assertEqual(ProviderSync.objects.filter(provider=self.acano.cluster).count(), 1)
        self.assertEqual(ProviderSync.objects.filter(provider=self.pexip.cluster).count(), 1)


class RecordingTestCase(ConferenceBaseTest):

    def setUp(self):
        self._init()  # base

    def tearDown(self):
        super().tearDown()

    def test_recording(self):

        meeting = self._book_meeting(recording=json.dumps({
            'record': True,
            'is_live': True,
            'callback': 'http://localhost/callback/'
        }))

        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            self.assertEqual(MeetingRecording.objects.all().count(), 1)
        self.assertEqual(meeting.backend_active, True)

        recording = meeting.schedule_recording()
        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            if recording.get_api().can_schedule_stream:
                self.assertNotEqual(recording.recording_id, '')
            else:
                self.assertEqual(recording.recording_id, '')
            recording.refresh_from_db()
            tasks.record(meeting.pk, recording.pk, recording.schedule_id)  # async
        else:
            recording = MeetingRecording.objects.all()[0]

        recording = MeetingRecording.objects.get(pk=recording.pk)
        if meeting.customer.get_recording_api().provider.is_videocenter:
            self.assertEqual(recording.recording_id, '1234')
        self.assertEqual(recording.backend_active, True)

        self.assertEqual(MeetingRecording.objects.all().count(), 1)
        self.assertTrue(recording)

        recording = MeetingRecording.objects.all()[0]
        self.assertEqual(recording.error, '')
        self.assertEqual(recording.backend_active, True)
        self.assertEqual(recording.is_live, True)

        tasks.stop_record(recording.meeting_id, recording.id, recording.schedule_id)  # async
        recording = MeetingRecording.objects.get(pk=recording.pk)

        self.assertEqual(recording.backend_active, False)

    def test_retry(self):

        meeting = self._book_meeting(recording=json.dumps({
            'record': True,
            'is_live': True,
        }))

        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            recording = meeting.schedule_recording()
            if recording.get_api().can_schedule_stream:
                self.assertNotEqual(recording.recording_id, '')
            else:
                self.assertEqual(recording.recording_id, '')
            self.assertEqual(recording.recording_id, '')
            tasks.record(meeting.pk, recording.pk, recording.schedule_id)  # async

        recording = MeetingRecording.objects.all()[0]

        self.assertEqual(MeetingRecording.objects.all().count(), 1)

        active = recording.check_active()
        self.assertEqual(active, True)

        recording = MeetingRecording.objects.all()[0]
        self.assertEqual(recording.backend_active, True)

        result = tasks.check_recording(recording.pk, True)
        self.assertEqual(result, True)

        if not self.customer.get_recording_api().can_retry:
            return  # cant check if active or not for now.

        self.set_url_state('recording-not-found')

        self.assertEqual(MeetingRecording.objects.all().count(), 1)

        active = recording.check_active()
        self.assertEqual(active, False)

        result = tasks.check_recording(recording.pk, True)
        self.assertEqual(result, False)

        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):  # retried is run multiple times
            self.assertEqual(MeetingRecording.objects.all().count(), 2)
            self.assertEqual(MeetingRecording.objects.filter(retry_count=1).count(), 1)


class RecordingRecVCTestCase(RecordingTestCase):

    def setUp(self):
        super().setUp()
        self.customer.videocenter_provider.channel = '1recorderid2'
        self.customer.videocenter_provider.save()

    rec_provider_type = 10


class RecordingQuickChannelTestCase(RecordingTestCase):

    rec_provider_type = 20

    def test_set_cospace_stream_urls(self):

        recording_api = self.customer.get_recording_api()

        recording_api.provider.recording_key = 'test_mp4:test_cam1'
        recording_api.provider.save()

        def _callback(*args):
            return recording_api.get_stream_url(*args)

        if self.customer.get_provider().is_acano:
            self.customer.get_api().set_cospace_stream_urls(_callback)


class RecordingQuickChannelPexipTestCase(RecordingTestCase):
    provider_subtype = 2


class MividasStreamTestCase(RecordingTestCase):

    rec_provider_type = 40

    def test_set_cospace_stream_urls(self):

        recording_api = self.customer.get_recording_api()

        recording_api.provider.recording_key = 'abc123'
        recording_api.provider.save()

        def _callback(*args):
            return recording_api.get_stream_url(*args)

        if self.customer.get_provider().is_acano:
            self.customer.get_api().set_cospace_stream_urls(_callback)


class RecordingAcanoNativeTestCase(RecordingTestCase):

    rec_provider_type = 30


class RecordingRTMPStreamTestCase(RecordingTestCase):

    rec_provider_type = 15

    def test_set_cospace_stream_urls(self):

        recording_api = self.customer.get_recording_api()

        def _callback(*args):
            return recording_api.get_stream_url(*args)

        if self.customer.get_provider().is_acano:
            self.customer.get_api().set_cospace_stream_urls(_callback)


class StatusTestCase(ConferenceBaseTest):

    def test_status(self):

        self._init()

        from ui_message.models import Message, String

        c = self.client

        message = Message.objects.get_welcome()
        message.title = 'Welcome title'
        message.content = '<div>Welcome content</div>'
        message.save()

        s = String.objects.get_all()[0]
        s.title = 'testar'
        s.save()

        data = {'key': self.customer_shared_key}
        result = c.get(reverse('api_status'), data)

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertEqual(json_data.get('status'), 'OK')

        data = {'key': self.customer_shared_key}
        result = c.get(reverse('api_welcome_message'), data)
        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertEqual(json_data.get('status'), 'OK')

        self.assertEqual(json_data.get('welcome_title'), message.title)

        self.assertEqual(json_data.get('welcome_message'), message.content)

        # second key
        data = {'key': self.key2}
        result = c.get(reverse('api_welcome_message'), data)
        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertEqual(json_data.get('welcome_title'), message.title)

        m = Message(customer=self.customer, type=Message.TYPES.outlook_welcome)
        m.title = 'Customer title'
        m.content = 'test'
        m.active = True
        m.save()
        self.assertNotEqual(m.pk, message.pk)

        result = c.get(reverse('api_welcome_message'), data)
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.content)

        self.assertEqual(json_data.get('welcome_title'), m.title)

        self.assertEqual(json_data.get('welcome_message'), m.content)

        self.assertEqual(json_data.get(s.type_key), s.title)

    def test_exception_errors(self):

        from meeting.api_views import ExceptionTestView, ResponseErrorTestView

        class FakeRequest:
            path = '/test/'

        request = FakeRequest()

        ExceptionTestView.as_view()(request)

        ResponseErrorTestView.as_view()(request)


class VCSETestCase(ConferenceBaseTest):

    def test_status(self):

        self._init()
        api = self.customer.get_vcs_api()

        status = api.get_status()
        self.assertEqual(status['uptime'], '5 days, 13:21')
        self.assertEqual(status['product'], 'TANDBERG VCS')
        self.assertEqual(status['software_version'], 'X8.11.4')

    def test_status_scrape(self):

        self._init()
        api = self.customer.get_vcs_api()

        status = api.get_status_by_scrape()
        self.assertEqual(status['last_update'], 'Resource usage (last updated: 16:18:08 CEST)')
        self.assertEqual(status['Non-traversal calls']['Current'], 0)
        self.assertEqual(status['Traversal calls']['Current video'], 0)

    def test_uptime(self):

        self._init()
        api = self.customer.get_vcs_api()

        uptime = api.get_uptime()
        self.assertEqual(uptime, '5 days, 13:21')

    def test_uptime_scrape(self):

        self._init()
        api = self.customer.get_vcs_api()

        uptime = api.get_uptime_by_scrape()
        self.assertEqual(uptime, '34 days 17 minutes')
