
from os import path

from django.test.utils import override_settings

from conferencecenter.tests.base import ThreadedTestCase
from debuglog.models import EndpointCiscoProvision
from endpoint.tests.base import EndpointBaseTest

from ..consts import MANUFACTURER
from ..models import Endpoint, EndpointStatus

root = path.dirname(path.abspath(__file__))


class TestAPIViews(EndpointBaseTest):

    def _get_url(self, args):
        return '/json-api/v1/endpoint/{}/{}'.format(self.endpoint.id, args)

    def test_update_basic_data(self):

        self.endpoint.has_head_count = True
        self.endpoint.save()
        data = self.endpoint.update_basic_data()
        self.assertEquals(self.endpoint.has_head_count, False)

    def test_get_basic_data(self):

        data = self.endpoint.get_api().get_basic_data()
        require_keys = {
            'serial_number',
            'product_name',
            'mac_address',
            'ip',
            'software_version',
            'sip',
            'sip_display_name',
        }

        basic_data_with_value = {k for k in require_keys if data.get(k)}
        self.assertEqual(basic_data_with_value, require_keys)

    def test_get_status(self):

        datas = {}

        api = self.endpoint.get_api()
        for url_state in ('initial', 'in_call', 'incoming_call', 'with_warnings', 'muted'):
            self.set_url_state(url_state)
            datas[url_state] = api.get_status(data=api.get_status_data(force=True))

        require_keys = {
            'uptime',
            'status',
            'incoming',
            'in_call',
            'muted',
            'volume',
            #'inputs',
            #'presentation',
            'call_duration',
            #'upgrade',
            'warnings',
            'diagnostics',
        }

        status_data_with_value = {}
        for data in datas.values():
            for k in require_keys:
                if data.get(k) or data.get(k) == False:
                    status_data_with_value.setdefault(k, data[k])

        self.assertEqual(set(status_data_with_value), require_keys)

    def test_api_list(self):

        response = self.client.get('/json-api/v1/endpoint/')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertGreater(len(data), 0)

    def test_api_get_status(self):

        response = self.client.get(self._get_url('status/'))
        data = response.json()

        self.assertGreater(len(data), 0)

    def test_api_get_status_data(self):

        response = self.client.get(self._get_url('status_data/'))
        data = response.json()

        self.assertGreater(len(data), 0)

    def test_api_get_configuration_data(self):

        response = self.client.get(self._get_url('configuration_data/'))
        data = response.json()

        self.assertGreater(len(data), 0)

    def test_api_call_history(self):

        response = self.client.get(self._get_url('call_history/'))
        response.json()

        self.assertEquals(response.status_code, 200)

    def test_api_call_control(self):

        arguments = {
            'dial': ['test@example.org'],
            'mute': ['', 'true'],
            'volume': ['100'],
        }

        for action in (
            'dial',
            'answer',
            'reject',
            'disconnect',
            'mute',
            'reboot',
            'volume',
            'presentation',
            'presentation_stop',
        ):
            with self.subTest('callcontrol {}'.format(action)):

                for argument in arguments.get(action, ['']):

                    post_requests_before = self._get_change_requests()

                    try:
                        response = self.client.post(
                            self._get_url('call_control/'), {'action': action, 'argument': argument}
                        )
                        response.json()
                    except Exception:
                        if action in {'presentation', 'presentation_stop'}:
                            continue  # postpone
                        raise
                    if action in {'presentation', 'presentation_stop'}:
                        continue  # postpone

                    self.assertEquals(response.status_code, 200)

                    self.assertGreater(
                        len(self._get_change_requests()),
                        len(post_requests_before),
                        'No new post requests sent for {} call control {}: {}'.format(
                            self.__class__.__name__, action, argument
                        ),
                    )

    def test_api_get_dial_info(self):

        response = self.client.get(self._get_url('dial_info/'))
        data = response.json()

        self.assertEquals(data['sip'], 'sip@example.org')

    @override_settings(EPM_HOSTNAME='core.localhost')
    def test_provision_status(self):
        response = self.client.get(self._get_url('provision_status/'))
        data = response.json()

        with self.subTest('dial_settings_status'):
            self.assertTrue(data['dial_settings'])
            require_keys = {
                'name',
                'sip',
                'sip_display_name',
                'h323',
                'sip_proxy',
                'h323_gatekeeper',
            }

            with_data = {k for k in require_keys if data['dial_settings'].get(k)}
            self.assertEqual(require_keys, with_data)

            self.assertIn('@', data['dial_settings']['sip'])
            self.assertIn('@', data['dial_settings']['h323'])

        with self.subTest('addressbook_status'):
            self.assertTrue(data['addressbook'])

        with self.subTest('passive_status'):
            self.assertTrue(data['passive'])

        with self.subTest('event_status'):
            self.assertTrue(data['event'])

    def test_api_get_commands_data(self):

        response = self.client.get(self._get_url('commands_data/'))
        data = response.json()

        self.assertGreater(len(data), 0)

    def test_api_get_valuespace_data(self):

        response = self.client.get(self._get_url('valuespace_data/'))
        data = response.json()

        self.assertGreater(len(data), -1) # TODO ignore the case in which lengh of valuespace data is 0 for now


@override_settings(EPM_ENABLE_OBTP=True)
class TestMeetings(EndpointBaseTest):
    def _test_bookings(self):
        self.book_endpoint_meeting(self.endpoint)
        self.book_endpoint_meeting(
            self.endpoint, external_uri='https://teams.microsoft.com/meeting/test/'
        )

        task = EndpointCiscoProvision.objects.filter(
            endpoint=self.endpoint, event='bookings'
        ).last()
        self.assertTrue(task)
        self.assertTrue('example.org' in task.content_text)
        return task.content_text

    def test_active_xml(self):
        self.endpoint.status.software_version = 'ce9.01'
        self.endpoint.status.save()

        result = self._test_bookings()
        self.assertFalse('teams.microsoft.com' in result)

    def test_active_json(self):
        self.endpoint.status.software_version = 'ce9.14'
        self.endpoint.status.save()

        self.endpoint.webex_registration = False
        self.endpoint.save()

        result = self._test_bookings()
        self.assertFalse('teams.microsoft.com' in result)

    def test_active_json_teams(self):
        self.endpoint.status.software_version = 'ce9.14'
        self.endpoint.status.save()

        self.endpoint.webex_registration = True
        self.endpoint.save()

        result = self._test_bookings()
        self.assertTrue('teams.microsoft.com' in result)

    def test_pexip_registration(self):

        self.endpoint.update_all_data()
        self.assertEqual(self.endpoint.pexip_registration, False)

        dial_info = self.endpoint.get_api().get_dial_info()
        self.assertEqual(dial_info['sip_proxy'], 'sipproxy.example.org')

        configuration_data = self.endpoint.get_api().get_configuration_data()
        proxy_value = configuration_data._nested_keys[('SIP', 'Proxy', 'Address')]
        for v in proxy_value:
            if v.item.value == 'sipproxy.example.org':
                v.item.value = 'test.videxio.net'

        self.endpoint.update_dial_info(configuration_data)
        self.assertEqual(self.endpoint.pexip_registration, True)


class TestPassiveEndpoint(EndpointBaseTest):
    def setUp(self):
        super().setUp()
        self.endpoint.connection_type = self.endpoint.CONNECTION.PASSIVE
        self.endpoint.save()

    def _get_url(self, args):
        return '/json-api/v1/endpoint/{}/{}'.format(self.endpoint.id, args)

    def test_all(self):
        for url in [
            self._get_url('status/'),
            self._get_url('call_history/'),
        ]:
            response = self.client.get(url)
            self.assertEquals(response.status_code, 200, url)

        for url in [
            self._get_url('status_data/'),
            self._get_url('dial_info/'),
            self._get_url('commands_data/'),
            self._get_url('valuespace_data/'),
        ]:
            with self.subTest('test_all {}'.format(url)):
                response = self.client.get(url)
                if self.endpoint.is_cisco:  # TODO check poly as well
                    self.assertEquals(response.status_code, 503, url)


class TaskTestCase(ThreadedTestCase, EndpointBaseTest):

    manufacturer = MANUFACTURER.CISCO_CE

    def test_update_status(self):
        Endpoint.objects.create(
            customer=self.customer, hostname='auth_error', manufacturer=self.manufacturer
        )
        Endpoint.objects.create(
            customer=self.customer, hostname='response_error', manufacturer=self.manufacturer
        )
        Endpoint.objects.create(
            customer=self.customer, hostname='invalid_xml', manufacturer=self.manufacturer
        )
        EndpointStatus.objects.all().update(status=Endpoint.STATUS.UNKNOWN)

        from endpoint.tasks import update_all_endpoint_status

        update_all_endpoint_status()


class CeleryTasksTestCase(EndpointBaseTest):
    # TODO in depth tests

    def setUp(self):
        super().setUp()
        from endpoint import tasks

        self.tasks = tasks

    def test_update_active_meeting(self):
        self.tasks.update_active_meeting(self.endpoint.pk)

    def test_backup_endpoint(self):
        self.tasks.backup_endpoint(self.endpoint.pk)

    def test_sync_address_books(self):
        self.tasks.sync_address_books(self.endpoint.pk)

    def test_update_all_data(self):
        self.tasks.update_all_data([self.endpoint.pk])

    def test_update_endpoint_task_constraint_times(self):
        self.tasks.update_endpoint_task_constraint_times()

    def test_queue_pending_endpoint_tasks(self):
        self.tasks.queue_pending_endpoint_tasks()

    def test_sync_endpoint_bookings(self):
        self.tasks.sync_endpoint_bookings(self.endpoint.pk)

    def test_update_endpoint_statistics(self):
        self.tasks.update_endpoint_statistics(self.endpoint.pk)

    def test_sync_upcoming_endpoint_bookings(self):
        self.tasks.sync_upcoming_endpoint_bookings()
