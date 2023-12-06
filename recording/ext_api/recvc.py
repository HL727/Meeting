import requests
from requests.auth import HTTPDigestAuth
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from provider.exceptions import NotFound  # TODO

from provider.ext_api.base import RecordingProviderAPI
import json
import logging

logger = logging.getLogger(__name__)


class RecVcAPI(RecordingProviderAPI):

    can_retry = True
    provides_recording = True
    provides_streaming = True
    provides_playback = True

    def request(self, *args, **kwargs):
        kwargs['auth'] = HTTPDigestAuth(self.provider.username, self.provider.password)
        return super().request(*args, **kwargs)

    def login(self, force=False):

        return True

    def get_base_url(self):
        return 'https://my.rec.vc'

    def get_url(self, path):
        return '%s/api/v2/%s' % (self.get_base_url(), path.lstrip('/'))

    def get_recorders(self):

        response = self.get('recorderlist')
        if response.status_code != 200:
            raise self.error('status code not 200: %s' % response.text, response)

        return response.json()

    def dialout(self, meeting, recording, recorder_id=None):

        if not recorder_id:
            recorder_id = self.provider.channel

        response, stream_id = self.open_session(meeting.pin_dialstring, stream=recording.is_live,
            title=meeting.title, recorder_id=recorder_id)

        recording.recording_id2 = stream_id

        if response.status_code not in (200, 201):

            try:
                meeting.recording_embed_callback()
            except Exception as e:
                raise self.error('status not ok: %s + exception %s' % (response.text, e), response)

            raise self.error(_('Could not start recording'), response)

        recording.recording_id = response.json().get('session_id')
        recording.embed_code = response.json().get('filename')
        if not recording.recording_id:
            raise self.error('session not in response: %s' % response.text, response)

        recording.activate(commit=True)

    def adhoc_record(self, api, call_id, **kwargs):

        call = api.get_call(call_id)
        cospace = api.get_cospace(call['cospace'])
        sip_uri = api.get_sip_uri(uri=cospace['uri'])

        return self.open_session(sip_uri, pin_code=cospace['passcode'])

    def open_session(self, uri, stream=False, title=None, pin_code=None, recorder_id=None):

        if not recorder_id:
            recorder_id = self.provider.channel

        data = {
            'uri': uri,
        }

        if stream:
            data['stream'] = self.create_stream(title, recorder_id=recorder_id)
        if pin_code:
            data['dtmf'] = pin_code

        response = self.post('recorder/{}/session'.format(recorder_id), data)
        return response, data.get('stream', '')

    def create_stream(self, title, recorder_id=None):

        if not recorder_id:
            recorder_id = self.provider.channel

        data = {
            'title': title or self.customer.title,
        }
        response = self.post('recorder/{}/stream'.format(recorder_id), data)

        stream_id = response.json().get('stream_id')

        return stream_id

    def close_call(self, meeting, recording, recorder_id=None):

        if not recorder_id:
            recorder_id = self.provider.channel

        response = self.delete('recorder/{}/session/{}'.format(recorder_id, recording.recording_id))

        if recording.recording_id2:
            response = self.delete('stream/{}'.format(recording.recording_id2))

        if response.status_code != 204:
            raise self.error(_('Could not stop recording'), response)

        recording.deactivate(commit=True)

    def get_embed(self, meeting, recording):

        recording.video_sources = json.dumps({
            'type': 'recvc',
            'thumbnail': 'https://my.rec.vc/getthumbnailfile?name={}'.format(recording.embed_code),
            'videos': ['https://my.rec.vc/getvideofile?name={}'.format(recording.embed_code)],
        })

        recording.save()

        meeting.recording_embed_callback()

    def get_embed_callback_data(self, meeting, recording):
        from provider.models.utils import date_format

        data = []

        if recording.error or recording.embed_code:

            cur = {
                'ts_created': date_format(recording.ts_activated or now()),
                'error': recording.error,
                'video_sources': json.loads(recording.video_sources or '{}'),
                'embed_code': '<video style="max-width: 100%;" autoplay controls><source type="video/mp4" src="https://my.rec.vc/getvideofile?name={}"></source></video>'.format(
                    recording.embed_code
                ),
                'recording_id': 'recvc-{}'.format(recording.pk),
            }
            data.append(cur)

        return data

    def get_call(self, session_id, recorder_id=None):

        if not recorder_id:
            recorder_id = self.provider.channel

        response = self.get('recorder/{}/sessionstatus'.format(recorder_id))

        data = response.json()

        if data.get('sessionlist'):
            try:
                return [x for x in data['sessionlist'] if x['session_id'] == session_id][0]
            except IndexError:
                pass

        raise NotFound('Call not found')

