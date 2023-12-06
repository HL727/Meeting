import json

from django.conf import settings
from django.core.files.base import ContentFile

from endpoint import consts
from endpoint.tests.base import EndpointBaseTest
from endpoint_provision.models import (
    EndpointFirmware,
    EndpointProvision,
    EndpointTask,
    EndpointTemplate,
)


class TestProvisionAPI(EndpointBaseTest):
    def setUp(self):
        super().setUp()
        EndpointProvision.objects.provision(
            self.customer, [self.endpoint], user=self.user, events=True
        )
        self.task = EndpointTask.objects.get(endpoint=self.endpoint)
        if not settings.CELERY_TASK_ALWAYS_EAGER:
            from endpoint.tasks import run_task

            run_task(self.task.id)

    def test_list(self):

        response = self.client.get('/json-api/v1/endpointtask/')
        self.assertContains(response, text='test', status_code=200)

    def test_list_filter(self):

        response = self.client.get(
            '/json-api/v1/endpointtask/?order_by=change&status=0&changed_since=2020-01-01T00:00:00Z&endpoint=1'
        )
        self.assertContains(response, text='', status_code=200)

    def _get_url(self, args=None):
        return '/json-api/v1/endpointtask/{}/{}'.format(self.task.pk, args or '')

    def test_single(self):

        response = self.client.get(self._get_url())
        self.assertContains(response, text='test', status_code=200)

    def test_cancel(self):
        response = self.client.post(self._get_url('cancel/'))
        self.assertContains(response, text='error', status_code=400)

        self.task.status = self.task.TASKSTATUS.PENDING
        self.task.save()
        response = self.client.post(self._get_url('cancel/'))
        self.assertContains(response, text='events', status_code=200)

    def test_retry(self):
        self.task.status = self.task.TASKSTATUS.PENDING
        self.task.save()

        response = self.client.post(self._get_url('retry/'))
        self.assertContains(response, text='error', status_code=400)

        self.task.status = self.task.TASKSTATUS.COMPLETED
        self.task.save()
        response = self.client.post(self._get_url('retry/'))
        self.assertContains(response, text='events', status_code=200)


class TestEndpointTemplateApi(EndpointBaseTest):
    def setUp(self):
        super().setUp()
        self.template = EndpointTemplate.objects.create(customer=self.customer, name='test')

    def _get_url(self, pk=None):
        return '/json-api/v1/endpointtemplate/{}'.format('{}/'.format(pk) if pk else '')

    def test_get_list(self):

        response = self.client.get(self._get_url())
        self.assertContains(response, text='test', status_code=200)

    def test_get_single(self):
        response = self.client.get(self._get_url(self.template.pk))
        self.assertContains(response, text='test', status_code=200)

    def test_create(self):
        data = {'model': 'Test', 'settings': '[{"key": "test"}]'}
        response = self.client.post(self._get_url(), data)
        self.assertContains(response, text='test', status_code=201)
        self.assertTrue(EndpointTemplate.objects.get(model='Test').settings)

    def test_create_json(self):
        data = {'model': 'Test', 'settings': [{"key": "test"}]}
        response = self.client.post(
            self._get_url(), json.dumps(data), content_type='application/json'
        )
        self.assertContains(response, text='test', status_code=201)

    def test_create_command_json(self):
        data = {'model': 'Test', 'commands': [{"command": ["test"]}]}
        response = self.client.post(
            self._get_url(), json.dumps(data), content_type='application/json'
        )
        self.assertContains(response, text='test', status_code=201)

    def test_create_invalid(self):
        data = {
            'model': 'Test',
            'settings': [{"command": ["test"]}],
            'commands': [{"command": ["test"]}],
        }
        response = self.client.post(
            self._get_url(), json.dumps(data), content_type='application/json'
        )
        self.assertNotContains(response, text='test', status_code=400)


class TestFirmwareAPITestCase(EndpointBaseTest):
    def setUp(self):
        super().setUp()
        self.firmware = EndpointFirmware.objects.create(
            customer=self.customer,
            model='test',
            manufacturer=consts.MANUFACTURER.CISCO_CE,
            file=ContentFile('test', 'test.bin'),
        )

    def _get_url(self, pk=None, suffix=None):
        return '/json-api/v1/endpointfirmware/{}{}'.format(
            '{}/'.format(pk) if pk else '', suffix or ''
        )

    def test_get_list(self):

        response = self.client.get(self._get_url())
        self.assertContains(response, text='test', status_code=200)

    def test_get_single(self):
        response = self.client.get(self._get_url(self.firmware.pk))
        self.assertContains(response, text='test', status_code=200)

    def test_get_copy(self):
        response = self.client.post(
            self._get_url(self.firmware.pk, 'copy/'), {'models': ['model1', 'model2']}
        )
        self.assertContains(response, text='model2', status_code=200)
        self.firmware.delete()
        f = EndpointFirmware.objects.get(model='model2')
        self.assertTrue(f.file.read())

    def test_create(self):
        data = {
            'model': 'Test',
            'manufacturer': consts.MANUFACTURER.CISCO_CE.value,
            'file': ContentFile('test', 'test.bin'),
            'version': '1.0',
        }
        response = self.client.post(self._get_url(), data)
        self.assertContains(response, text='test', status_code=201)
        self.assertTrue(EndpointFirmware.objects.get(model='Test').file)
