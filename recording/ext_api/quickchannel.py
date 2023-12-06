from django.utils.formats import date_format
from django.utils.timezone import now
from django.utils.translation import gettext as _

from provider.exceptions import AuthenticationError
import requests
from datetime import timedelta
import json
import logging
from recording.ext_api.acanortmp import RTMPStreamAPI
logger = logging.getLogger(__name__)


class QuickChannelAPI(RTMPStreamAPI):

    can_update_acano_stream_url = True
    provides_recording = True
    provides_playback = True
    can_schedule_stream = True
    can_reschedule = False

    def request(self, *args, **kwargs):
        if len(args) == 2 and kwargs.get('method') == "GET":
            *args, data = args
        else:
            data = kwargs.pop('data', {})

        if self.provider.has_session:
            data['sessionid'] = self.provider.session_id

        return super().request(*args, data=data, **kwargs)

    def login(self, force=False):

        response = requests.get(self.get_url('authentication/'), {
            'username': self.provider.username,
            'password': self.provider.password,
            'command': 'direct',
        })

        data = response.json()
        if data['error']:
            return False

        self.provider.session_id = data.get('sessionid') or ''
        self.provider.session_expires = now() + timedelta(seconds=60 * 60 * 20)
        self.provider.save()

        return True

    def check_login_status(self, response):

        if response.status_code == 200:
            if response.json().get('errormessage') == 'ERROR: Illegal authentication':
                raise AuthenticationError(response.json().get('errormessage'))

    def get_base_url(self):
        return 'https://secure.quickchannel.com'

    def get_url(self, path):
        return '%s/qc/rest/%s' % (self.get_base_url(), path.lstrip('/'))

    def schedule_stream(self, meeting, recording):

        data = {
            'command': 'bookrecording',
            'url': self.provider.channel,
            'eventdatetime': date_format(meeting.ts_start, 'Y-m-d H:i:s'),
            'duration': (meeting.ts_stop - meeting.ts_start).total_seconds(),
        }
        response = self.get('bookrecording/', data)

        if response.status_code != 200:
            raise self.error('Invalid code', response)

        response_data = response.json()
        recording.video_sources = json.dumps(
            {
                'playback_url': response_data['presentationuri'],
                'stream_url': response_data['destination_cam'],
            }
        )
        recording.embed_code = '<a href="{}">{}</a>'.format(
            response_data['presentationuri'], _('Spela upp i Quickchannel')
        )
        recording.stream_url = response_data['destination_cam']
        recording.save()

        meeting.recording_embed_callback()

        return response

    def unschedule_stream(self, meeting, recording):
        pass

    def get_stream_url(self, cospace_id=None):
        key = self.provider.recording_key.replace('mp4:', '')
        dynamic = cospace_id  # TODO clean

        if '%s' in key:
            if not dynamic:
                return None
            return key.replace('%s', dynamic)

        if not dynamic:
            return key

        return key.replace('_cam1', '_{}_cam1'.format(dynamic))

    def get_embed(self, meeting, recording):

        recording.video_sources = json.dumps({  # TODO
            'type': 'quickchannel',
            'thumbnail': '',
            'videos': [],
        })

        recording.save()

        meeting.recording_embed_callback()

    def get_media(self):
        response = self.get('allmedia_compatibility')
        return response.json()

    def get_embed_code(self, recording):
        return '<a href="https://secure.quickchannel.com">Gå till quickchannel för att visa filmen</a>'  # TODO

    def get_recording_id(self, recording):
        return 'quickchannel-{}'.format(recording.pk)

