import os
from os.path import dirname
from io import BytesIO
import zipfile
from defusedxml.cElementTree import fromstring as safe_xml_fromstring, parse as safe_xml_parse
from urllib import parse

from django.core.files.base import ContentFile
from rest_framework.test import APITestCase

from django.core.files import File
from django.test import TestCase
from django.contrib.auth.models import User

from conferencecenter.tests.base import ConferenceBaseTest
from customer.models import Customer
from endpoint.models import Endpoint
from roomcontrol.export import get_export_url_params, generate_roomcontrol_zip
from roomcontrol.models import RoomControl, RoomControlFile, RoomControlTemplate


class RoomControlBaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

        self.customer = Customer.objects.create(title='test', shared_key='test_key')
        self._init()

    def _init(self):
        self.control = RoomControl.objects.create(customer=self.customer, title='TestControl')

    def _add_xml(self, filename, control=None):
        control = control or self.control
        xml_file = File(open(os.path.join(dirname(__file__), filename)))
        for filename, content in RoomControlFile.objects.validate_panel_xml(xml_file.read()):
            control.add_file(filename, content)

    def _add_js(self, filename, control=None):
        control = control or self.control
        js_file = File(open(os.path.join(dirname(__file__), filename)))
        control.add_file(filename, js_file.read())


class RoomControlTemplateTestCase(RoomControlBaseTestCase, APITestCase):

    def _init(self):
        RoomControlBaseTestCase._init(self)
        self.other_control = RoomControl.objects.create(customer=self.customer, title='TestControl')

        self.template = RoomControlTemplate.objects.create(customer=self.customer, title='TestTemplate')
        self.template.controls.add(self.control)
        self.template.controls.add(self.other_control)
        self.template.save()

    def test_export(self):
        self._add_xml('panels.xml')
        self._add_xml('panel.xml')
        self._add_js('macro.js', self.other_control)

        api_url = '/json-api/v1/roomcontrol_templates/{}/export/'.format(self.template.id)
        response = self.client.get(api_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get('Content-Disposition').endswith('.zip'))

        file_content = BytesIO(response.content)
        zipfile.ZipFile(file_content, 'r')

    def test_generate_commands(self):
        self._add_xml('panels.xml')
        self._add_xml('panel.xml')
        self._add_js('macro.js', self.other_control)

        from roomcontrol.export import generate_roomcontrol_commands

        macros, panels, activate = generate_roomcontrol_commands(
            templates=[self.template], controls=[self.other_control]
        )
        self.assertEqual(len(macros + panels + activate), 10)


class ProvisionTestCase(RoomControlBaseTestCase, ConferenceBaseTest):

    def test_provision(self):

        self._init()
        self.template = RoomControlTemplate.objects.create(customer=self.customer, title='TestTemplate')
        self.template.controls.add(self.control)

        endpoint = Endpoint.objects.create(customer=self.customer, title='test', ip='127.0.0.2')

        endpoint.get_api().clear_room_controls(all=True)
        endpoint.get_api().clear_room_controls(controls=[self.control])
        endpoint.get_api().clear_room_controls(templates=[self.template])

        endpoint.get_api().set_room_controls(controls=[self.control], templates=[self.template])


class RoomControlTestCase(RoomControlBaseTestCase, APITestCase):
    def test_create_control(self):
        data = {
            'title': 'test',
            'description': 'test',
            'files': File(open(dirname(__file__) + '/panel.xml')),
        }
        self.assertEqual(RoomControl.objects.count(), 1)

        response = self.client.post('/json-api/v1/roomcontrols/', data)
        self.assertEqual(response.status_code, 201)

        self.assertEqual(RoomControl.objects.count(), 2)
        self.assertEqual(RoomControlFile.objects.count(), 1)

    def test_invalid_xml(self):
        data = {
            'title': 'test',
            'description': 'test',
            'files': ContentFile('test', 'test.xml'),
        }
        self.assertEqual(RoomControl.objects.count(), 1)

        response = self.client.post('/json-api/v1/roomcontrols/', data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('files'), ['Invalid XML'])

    def test_update_control(self):
        data = {
            'title': 'test2',
            'description': 'test2',
            'files': File(open(dirname(__file__) + '/panel.xml')),
        }
        self.assertEqual(RoomControl.objects.count(), 1)

        response = self.client.put('/json-api/v1/roomcontrols/{}/'.format(self.control.id), data)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(RoomControl.objects.count(), 1)
        self.assertEqual(set(*RoomControl.objects.values_list('title', 'description')), {data['title'], data['description']})

    def test_update_with_zip(self):

        self._add_xml('panel.xml')
        self._add_js('macro.js')

        zipfile = ContentFile(generate_roomcontrol_zip('test', controls=[self.control])[1], 'test.zip')
        data = {
            'title': 'test2',
            'description': 'test2',
            'files': zipfile,
        }

        RoomControlFile.objects.all().delete()
        self.assertEqual(RoomControlFile.objects.count(), 0)

        response = self.client.put('/json-api/v1/roomcontrols/{}/'.format(self.control.id), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RoomControlFile.objects.count(), 2)

        zipfile.seek(0)
        response = self.client.post('/json-api/v1/roomcontrols/{}/add_files/'.format(self.control.id), data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(RoomControlFile.objects.count(), 2)

        self.assertEqual(RoomControl.objects.count(), 1)
        self.assertEqual(set(*RoomControl.objects.values_list('title', 'description')), {data['title'], data['description']})

    def test_update_with_files(self):
        data = {
            'title': 'test2',
            'description': 'test2',
            'files': ContentFile('<Extensions>', 'test.xml'),
        }
        self.assertEqual(RoomControl.objects.count(), 1)

        response = self.client.put('/json-api/v1/roomcontrols/{}/'.format(self.control.id), data)
        self.assertEqual(response.status_code, 400)

    def test_delete_control(self):
        self._add_xml('panel.xml')

        response = self.client.delete('/json-api/v1/roomcontrols/{}/'.format(self.control.id))
        self.assertEqual(response.status_code, 204)

        self.assertEqual(RoomControl.objects.all().count(), 0)
        self.assertEqual(RoomControlFile.objects.all().count(), 0)

    def test_export_control(self):
        self._add_xml('panel.xml')

        file = self.control.files.all()[0]

        api_url = '/json-api/v1/roomcontrols/{}/export/?files={}'.format(self.control.id, file.id)

        response = self.client.get(api_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get('Content-Disposition').endswith('.zip'))

        file_content = BytesIO(response.content)
        zip = zipfile.ZipFile(file_content, 'r')

        self.assertIsNone(zip.testzip())
        self.assertIn('testpanelsingle.xml', zip.namelist())
        self.assertIn('manifest.json', zip.namelist())

    def test_export_multiple_controls(self):
        self._add_xml('panel.xml')

        self.control.files.update(id=1)

        data = {'controls': [self.control.id]}
        response = self.client.post('/json-api/v1/roomcontrols/get_export_url/', data, format='json')

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data['status'], 'OK')

        url_parts = parse.urlsplit(data['url'])
        parse.parse_qs(url_parts.query).items()
        get_export_url_params(files=self.control.files.all())

        response = self.client.get('/epm/roomcontrol/package/?{}'.format(url_parts.query))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get('Content-Disposition').endswith('.zip'))

        file_content = BytesIO(response.content)
        zip = zipfile.ZipFile(file_content, 'r')

        self.assertIsNone(zip.testzip())
        self.assertIn('testpanelsingle.xml', zip.namelist())
        self.assertIn('manifest.json', zip.namelist())

        panel_file = zip.open('testpanelsingle.xml')

        # print(panel_file_content.read().decode("utf-8"))
        panel = safe_xml_parse(panel_file).getroot()
        panel_id = panel.find('./Panel/PanelId').text

        self.assertEqual(panel_id, 'testpanelsingle')


class RoomControlFileTestCase(RoomControlBaseTestCase):

    def test_panel_xml(self):
        self._add_xml('panel.xml')

        files = list(self.control.files.all())

        self.assertEqual(len(files), 1)

        file = files[0]

        self.assertEqual(file.name, 'testpanelsingle.xml')
        self.assertTrue(file.content != '')

        panel = safe_xml_fromstring(file.content)
        panel_id = panel.findtext('./Panel/PanelId')

        self.assertEqual(panel_id, 'testpanelsingle')

    def test_multiple_panel_xml(self):
        self._add_xml('panels.xml')

        files = list(self.control.files.all())

        self.assertEqual(len(files), 5)

        self.assertEqual({f.name for f in files},
                          {'testpanel.xml', 'testpanel44.xml', 'panel_2.xml', 'old_panel_2.xml', 'old_panel_1.xml'})

