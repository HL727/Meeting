import requests
from django.utils.timezone import now
from datetime import timedelta
from time import time
from urllib.parse import urljoin
from django.utils.translation import gettext_lazy as _

import logging
logger = logging.getLogger(__name__)

import json
from provider.ext_api.base import RecordingProviderAPI


class VideoCenterAPI(RecordingProviderAPI):

    can_retry = True
    provides_recording = True
    provides_streaming = True
    provides_playback = True

    def login(self, force=False):
        if self.provider.has_session and not force:
            return True

        s = requests.Session()
        s.verify = self.verify_certificate

        override_function = getattr(self, 'override_post', None)
        if override_function:
            response = override_function(self.get_url('access-token/'))
        else:
            response = s.get(self.get_url('access-token/'), params=dict(grant_type='password',
                username=self.provider.username, password=self.provider.password))

        self.provider.session_id = response.json().get('access_token') or ''
        self.provider.session_expires = now() + timedelta(seconds=60 * 60 * 20)

        self.provider.save()

        return True

    def get_base_url(self):
        return 'https://%s' % self.provider.hostname

    def get_url(self, path):
        return '%s/api/v1/%s' % (self.get_base_url(), path.lstrip('/'))

    def dialout(self, meeting, recording):

        self.login()
        if meeting.provider.is_acano and meeting.password:
            from recording.models import MeetingRecording
            if not MeetingRecording.objects.filter(meeting=meeting, ts_activated__isnull=False):
                meeting.api.book_unprotected_access(meeting)

        data = {
            "author": self.customer.recording_user or recording.provider.username,
            "bitrate_kbps": 768,
            "channel": self.customer.recording_channel or recording.provider.channel,
            "name": recording.name or self.customer.title,
            "url": meeting.pin_dialstring,
            "is_recorded": json.loads(meeting.recording or '{}').get('record', False),
            "is_live": recording.is_live,
            "is_public": recording.is_public,
            "pin": self.provider.recording_key,  # TODO
        }

        response = self.post('dialout', data=json.dumps(data))

        if '"ok"' not in response.text:
            recording.error = 'Could not start recording: %s' % response.text[:70]
            recording.save()

            try:
                meeting.recording_embed_callback()
            except Exception as e:
                raise self.error('status not ok: %s + exception %s' % (response.text, e), response)

            raise self.error('status not ok: %s' % response.text, response)

        recording.recording_id = response.json().get('recording-id')
        if not recording.recording_id:
            raise self.error('recording-id not in response: %s' % response.text, response)

        recording.activate(commit=True)

    def adhoc_record(self, api, call_id, recording_key=None, layout=None, **kwargs):

        call = api.get_call(call_id)

        uri = 'sip:record:{}@{}'.format(recording_key or self.provider.recording_key, self.provider.hostname or self.provider.ip)

        api_kwargs = {}
        if kwargs.get('silent'):
            api_kwargs['callLegProfile'] = api._get_webinar_call_legs(force_encryption=False)[0]

        return api.add_participant(call['id'], uri, layout=layout, **api_kwargs)

    def adhoc_stream(self, *args, **kwargs):
        return self.adhoc_record(*args, **kwargs)

    def close_call(self, meeting, recording, recorder_id=None):

        self.login()
        self.delete('calls/{}'.format(recording.recording_id))

        recording.deactivate(commit=True)

    def get_embed(self, meeting, recording):

        self.login()
        if recording.is_live and recording.backend_active:
            url = 'live-streams/' + recording.recording_id
        else:
            url = 'recordings/' + recording.recording_id

        response = self.get(url)

        if response.status_code == 200:
            data = response.json()
            recording.embed_code = data.get('embed_code') or ''
            recording.video_sources = json.dumps({
                'type': 'videocenter',
                'thumbnail': data.get('thumbnails', {}).get('large', ''),
                'videos': data.get('recordingfeed_set', []),
            })

        if not recording.embed_code:
            if meeting.ts_stop < now() - timedelta(hours=1):
                recording.error = 'Video not found on server'
            else:
                raise self.error('embed_code not in response: %s' % response.text, response)

        recording.save()

        meeting.recording_embed_callback()

    def get_embed_callback_data(self, meeting, recording):

        from provider.models.utils import date_format

        data = []

        if recording.error or recording.embed_code:

            cur = {
                'ts_created': date_format(recording.ts_activated or now()),
                'error': recording.error,
                'embed_code': recording.embed_code,
                'video_sources': json.loads(recording.video_sources or '{}'),
                'recording_id': recording.recording_id,
            }

            recording.ts_callback_sent = now()
            recording.save()

            data.append(cur)

        return data

    def reboot(self):

        s = requests.Session()

        login_url = urljoin(self.get_base_url(), '/accounts/login/?next=/videos/')
        response = s.get(login_url)

        response = s.post(login_url, {
            'csrfmiddlewaretoken': response.cookies['csrftoken'],
            'username': self.provider.username,
            'password': self.provider.password,
            'next': '/videos/',
        }, headers={'Referer': login_url}, allow_redirects=False)

        if response.status_code != 302:
            raise self.error(_('Not logged in'), response)

        reboot_url = urljoin(self.get_base_url(), '/server-admin/operations/shutdown/reboot/')

        response = s.get(reboot_url)

        response = s.post(reboot_url, {
            'csrfmiddlewaretoken': response.cookies['csrftoken'],
            'confirmed': 'True',
            'change_id': str(int(time() * 1000)),
            'reboot': 'true'
        }, headers={'Referer': reboot_url})

        if response.status_code != 200:
            raise self.error(_('Couldnt reboot'), response)

        return True

    def get_call(self, recording_id):

        response = self.get('calls/{}'.format(recording_id))
        if response.status_code == 404:
            raise self.error('Call not found', response)

        return response.json()

    def get_params(self):
        return {
            'access_token': self.provider.session_id,
        }
