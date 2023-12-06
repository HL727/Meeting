from django.utils.text import slugify
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from recording.ext_api.acanortmp import RTMPStreamAPI
import json
import logging
from urllib.parse import urljoin
logger = logging.getLogger(__name__)


class MividasStreamAPI(RTMPStreamAPI):

    can_update_acano_stream_url = True
    provides_recording = False
    provides_playback = True
    can_schedule_stream = True

    def get_base_url(self):
        return 'https://{}/api/v1/'.format(self.provider.web_host or self.provider.hostname)

    def get_secret_key(self):
        key = self.provider.recording_key

        if 'rtmp://' in self.provider.recording_key:
            parts = self.provider.recording_key.strip('/').rsplit('/', 1)[-1].split('_')
            key = parts[0]

        return key

    def get_stream_url(self, cospace_id=''):

        uri = cospace_id

        key = self.get_secret_key()

        base = self.provider.web_host or self.provider.hostname
        base = base.replace('https://', '')
        if '//' not in base:
            base = 'rtmp://{}'.format(base)

        if uri:
            result = urljoin(base.replace('rtmp:', 'https:'), '/push/{}_{}_main'.format(key, slugify(uri)))
        else:
            result = urljoin(base.replace('rtmp:', 'https:'), '/push/{}_main'.format(key))

        return result.replace('https:', 'rtmp://').replace(':////', '://')  # urljoin does not support rtmp://

    def dialout(self, meeting, recording):
        if not recording.stream_url:
            self.schedule_stream(meeting, recording)
        return super().dialout(meeting, recording)

    def schedule_stream(self, meeting, recording):

        data = {
            'title': meeting.title,
            'ts_start': meeting.ts_start,
            'ts_stop': meeting.ts_stop,
        }
        response = self.post('book/{}/book/'.format(self.get_secret_key()), data)

        if not response.status_code == 201:
            raise self.error('Invalid code', response)

        response_data = response.json()
        recording.video_sources = json.dumps({
            'playback_url': response_data['playback_url'],
            'stream_url': response_data['publish_rtmp'],
        })
        recording.recording_id = response_data['secret_key']
        recording.stream_url = response_data['publish_rtmp']
        recording.embed_code = response_data['embed_code']
        recording.save()

        meeting.recording_embed_callback()

        return response

    def unschedule_stream(self, meeting, recording):
        response = self.delete('book/{}/'.format(self.recording_id))
        if response.status != 404 and not str(response.status).startswith('2'):
            raise self.error('Could not delete stream {}'.format(response.status), response)
        return response

    def get_embed(self, meeting, recording):

        existing = json.loads(recording.video_sources or '{}')

        result = {
            'type': 'mividas',
            'thumbnail': '',
            'playback_url': existing.get('playback_url'),
        }
        if not recording.embed_code:
            response = self.get('book/{}/'.format(recording.recording_id))
            if response.status_code != 200:
                raise self.error(_('Could not get embed'), response)

            recording.embed_code = response.json().get('embed_code')

        recording.video_sources = json.dumps(result)
        recording.save()

        meeting.recording_embed_callback()
        return result

    def get_embed_callback_data(self, meeting, recording):
        from provider.models.utils import date_format

        data = []

        if not recording.error:

            cur = {
                'ts_created': date_format(recording.ts_activated or now()),
                'error': recording.error,
                'video_sources': json.loads(recording.video_sources or '{}'),
                'embed_code': recording.embed_code,
                'recording_id': 'mividas-{}'.format(recording.pk),
            }
            data.append(cur)

        return data

