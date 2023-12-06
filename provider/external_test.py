
from django.test import TestCase
from django.urls import reverse
import json
import urllib.request, urllib.parse, urllib.error
import requests
from os import environ
from datetime import datetime, timedelta
from provider.models.utils import date_format

ADD_TIME_INDEX = 0

HOST = environ['HOSTNAME']
SHARED_KEY = environ['SHARED_KEY']

if not ':' in HOST:
    HOST = 'http://%s' % HOST

PAUSE = environ.get('PAUSE')


class ExternalClient:

    @staticmethod
    def _req(method: str):
        def _inner(self, url, *args, **kwargs):
            url = '%s/%s' % (HOST, url.lstrip('/'))
            fn = getattr(requests, method)
            kwargs.pop('files', None)
            if args:  # TODO check arg 2
                kwargs['data'] = args[0]
                args = ()

            data = kwargs.pop('data', {})
            if not isinstance(data, str):
                data['format'] = 'html'
            kwargs['data'] = data

            result = fn(url, verify=False, *args, **kwargs)
            return result

        return _inner

    post = _req('post')
    get = _req('get')
    put = _req('put')


client = ExternalClient()


def pause(message, data=None):

    if not PAUSE:
        return
    print(message)
    print('======')
    if data:
        from pprint import pprint
        pprint(data)

    print('Continue? > ')
    eval(input())


class ExternalTest(TestCase):

    def setUp(self):
        self.meeting_ids = []
        self.client = client

    def _init(self):
        pass

    def tearDown(self):

        for m in self.meeting_ids:
            self.client.post(reverse('api_unbook', args=[m]))

    def compare_data(self, meeting):
        return

    def _test_booking(self, lifesize=True, only_internal=False):

        self._init()

        c = self.client

        # book
        data = {
            'creator': 'test_client',
            'key': SHARED_KEY,
            'internal_clients': 1,
        }
        if lifesize:
            if only_internal:
                data['only_internal'] = True
        else:
            data['external_clients'] = 3

        ts_start = datetime.now()
        ts_stop = datetime.now() + timedelta(hours=1)

        data.update({
            'ts_start': date_format(ts_start),
            'ts_stop': date_format(ts_stop),
        })

        files = {}
        result = c.post(reverse('api_book'), data, files=files)

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))

        meeting_id = json_data.get('meeting_id')
        self.meeting_ids.append(meeting_id)

        pause('book', json_data)

        # confirm

        result = c.post(reverse('api_meeting_confirm', args=[meeting_id]), data, files=files)

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertEqual(json_data.get('meeting_id'), meeting_id)

        pause('confirm', json_data)

        # rebook

        data = {
            'creator': 'test_client',
            'key': SHARED_KEY,
            'ts_start': date_format(ts_start + timedelta(seconds=60)),
            'ts_stop': date_format(ts_stop + timedelta(hours=1)),
            'internal_clients': 1,
            'password': '1234',
        }
        if lifesize:
            if only_internal:
                data['only_internal'] = True
        else:
            data['external_clients'] = 2

        files = {}
        result = c.post(reverse('api_rebook', args=[meeting_id]), data, files=files)

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))
        self.assertTrue(json_data.get('meeting_id') != meeting_id)

        meeting_id = json_data.get('meeting_id')
        self.meeting_ids.append(meeting_id)

        pause('rebook', json_data)

        # rest rebook
        data['confirm'] = True
        data['only_internal'] = 'false'

        result = c.put(reverse('api_meeting_rest', args=[meeting_id]), urllib.parse.urlencode(data), files=files)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))
        self.assertTrue(json_data.get('meeting_id') != meeting_id)

        meeting_id = json_data.get('meeting_id')
        self.meeting_ids.append(meeting_id)

        # unbook
        data = {'key': SHARED_KEY}
        files = {}
        result = c.post(reverse('api_unbook', args=[meeting_id]), data, files=files)

        self.assertEqual(result.status_code, 200)

        pause('rest rebook', json_data)

        # rest unbook
        data = {'key': SHARED_KEY}
        files = {}
        result = c.post(reverse('api_unbook', args=[meeting_id]), data, files=files)

        self.assertEqual(result.status_code, 200)

        pause('rest unbook', json_data)

        # meeting view

        data = {'key': SHARED_KEY}
        result = c.get(reverse('api_meeting_rest', args=[meeting_id]), data, files=files)
        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'))

        pause('meeting', json_data)

        # TODO check for double unbook

        # valid recurring

        data = {
            'creator': 'test_client',
            'key': SHARED_KEY,
            'internal_clients': 1,
        }
        if lifesize:
            pass
        else:
            data['external_clients'] = 3

        data.update({
            'ts_start': date_format(ts_start),
            'ts_stop': date_format(ts_stop),
            'recurring': 'FREQ=DAILY;COUNT=5',
            'recurring_exceptions': date_format(ts_start + timedelta(days=1)),
        })

        files = {}
        result = c.post(reverse('api_book'), data, files=files)

        self.assertEqual(result.status_code, 200)

        json_data = json.loads(result.content)
        self.assertTrue(json_data.get('meeting_id'), result.content)

        meeting_id = json_data.get('meeting_id')
        self.meeting_ids.append(meeting_id)

        # exception
        data.update({
            'recurring_exceptions': data['recurring_exceptions'] + ',' + date_format(ts_start + timedelta(days=2)),
            })

        result = c.post(reverse('api_rebook', args=[meeting_id]), data, files=files)
        self.assertEqual(result.status_code, 200)

        pause('recurring', json_data)


    def test_lifesize(self):
        self._test_booking(True)

    def test_lifesize_internal(self):
        self._test_booking(True, True)

    def test_clearsea(self):
        self._test_booking(False)
