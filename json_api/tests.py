from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from meeting.models import Meeting
from organization.models import OrganizationUnit, CoSpaceUnitRelation, UserUnitRelation
from provider.models.provider import Provider
from conferencecenter.tests.base import ConferenceBaseTest
from django.utils.timezone import now
from datetime import timedelta
from django.contrib.auth.models import User


class Json_ApiTestCaseBase(ConferenceBaseTest):

    def setUp(self):
        self._init()
        self.provider = self.acano
        self.customer.save()
        self.meeting = Meeting.objects.create(provider=self.provider, customer=self.customer, creator_ip='127.0.0.1',
            ts_start=now(), ts_stop=now() + timedelta(hours=1), backend_active=True)  # TODO

        self.cospace_id = '22f67f91-1948-47ec-ad4f-4793458cfe0c'
        self.call_id = '935a38b8-0a80-4965-9db4-f02ab1a813d2'
        self.call_leg_id = '976dacd8-bc6b-4526-8bb7-d9050740b7c7'

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')
        self.client.session['customer_id'] = self.customer.id
        self.client.session.save()


class CallLegMuteAudioTestCase(Json_ApiTestCaseBase, TestCase):
    "test for json_api.views.CallLegMuteAudio"

    @property
    def url(self):
        return reverse('json_api_call_leg_mute_audio', args=[])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, text='', status_code=405)

    def test_post_error(self):
        data = {
            'id': '',
            'mute': '',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, text='', status_code=404)

    def test_post_valid(self):
        data = {
            'id': self.call_leg_id,
            'mute': '',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)


class CallLegMuteVideoTestCase(Json_ApiTestCaseBase, TestCase):
    "test for json_api.views.CallLegMuteVideo"

    @property
    def url(self):
        return reverse('json_api_call_leg_mute_video', args=[])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, text='', status_code=405)

    def test_post_error(self):
        data = {
            'id': '',
            'mute': '',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, text='', status_code=404)

    def test_post_valid(self):
        data = {
            'id': self.call_leg_id,
            'mute': '',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)


class CallLegDetailsTestCase(Json_ApiTestCaseBase, TestCase):
    "test for json_api.views.CallLegDetails"

    @property
    def url(self):
        return reverse('json_api_call_leg_details', args=[]) + '?call_leg_id={}'.format(self.call_leg_id)

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, text='', status_code=200)

    def test_clustered(self):

        acano2 = Provider.objects.get(pk=self.acano.pk)
        acano2.pk = None
        acano2.save()
        self.acano.clustered.add(acano2)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class CallLegSetLayoutTestCase(Json_ApiTestCaseBase, TestCase):
    "test for json_api.views.CallLegSetLayout"

    @property
    def url(self):
        return reverse('json_api_call_leg_set_layout', args=[])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, text='', status_code=405)

    def test_post_error(self):
        data = {
            'layout': '',
            'leg_id': '',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, text='', status_code=404)

    def test_post_valid(self):
        data = {
            'layout': '',
            'leg_id': self.call_leg_id,
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)


class CallLegHangupTestCase(Json_ApiTestCaseBase, TestCase):
    "test for json_api.views.CallLegHangup"

    @property
    def url(self):
        return reverse('json_api_call_leg_hangup', args=[])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, text='', status_code=405)

    def test_post_error(self):
        data = {
            'leg_id': '',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, text='', status_code=404)

    def test_post_valid(self):
        data = {
            'leg_id': self.call_leg_id,
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)


class CallMuteAllAudioTestCase(Json_ApiTestCaseBase, TestCase):
    "test for json_api.views.CallMuteAllAudio"

    @property
    def url(self):
        return reverse('json_api_call_mute_all_audio', args=[])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, text='', status_code=405)

    def test_post_error(self):
        data = {
            'id': '',
            'mute': '',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, text='', status_code=404)

    def test_post_valid(self):
        data = {
            'id': self.call_id,
            'mute': '1',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)


class CallMuteAllVideoTestCase(Json_ApiTestCaseBase, TestCase):
    "test for json_api.views.CallMuteAllVideo"

    @property
    def url(self):
        return reverse('json_api_call_mute_all_video', args=[])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, text='', status_code=405)

    def test_post_error(self):
        data = {
            'id': '',
            'mute': '',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, text='', status_code=404)

    def test_post_valid(self):
        data = {
            'id': self.call_id,
            'mute': '1',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)


class CallLegsTestCase(Json_ApiTestCaseBase, TestCase):
    "test for json_api.views.CallLegs"

    @property
    def url(self):
        return reverse('json_api_call_legs', args=[self.call_id])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, text='', status_code=200)


class CustomerTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test', is_staff=True, is_superuser=True)
        self.client.login(username='test', password='test')

    def test_get(self):
        response = self.client.get('/json-api/v1/customer/')
        self.assertContains(response, text='', status_code=200)

        response = self.client.get('/json-api/v1/customerkey/')
        self.assertContains(response, text='', status_code=200)

    def test_post(self):
        data = {'title': 'test', 'shared_key': 'adsf'}
        response = self.client.post('/json-api/v1/customer/', data)
        self.assertContains(response, text='', status_code=201)

        response = self.client.get('/json-api/v1/customer/')
        self.assertContains(response, text='', status_code=200)

    def test_not_super(self):
        self.user.is_superuser = False
        self.user.save()
        response = self.client.get('/json-api/v1/customer/')
        self.assertContains(response, text='', status_code=200)
        self.assertNotContains(response, text='mcu')
        response = self.client.get('/json-api/v1/customerkey/')
        self.assertContains(response, text='', status_code=404)

class SwaggerTestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test', is_staff=True, is_superuser=True)
        self.client.login(username='test', password='test')

    def test_get(self):
        response = self.client.get('/json-api/v1/swagger.json')
        self.assertContains(response, text='', status_code=200)
