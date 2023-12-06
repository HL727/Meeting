from django.conf import settings
from provider.exceptions import NotFound
from provider.ext_api.base import RecordingProviderAPI
import json
import logging
from django.utils.timezone import now
from datetime import timedelta
from urllib.parse import urljoin
logger = logging.getLogger(__name__)


class AcanoRecordingAPI(RecordingProviderAPI):

    can_reschedule = True

    def dialout(self, meeting, recording):

        if not meeting.provider.is_acano:
            meeting.add_error('Meeting provider is not Acano')
            return  # TODO raise exception? Other handling?

        cospace = meeting.api.get_cospace(meeting.provider_ref2)

        call_profile = meeting.api._call_profile('cospace', cospace['id'])
        call_profile.add_settings('recording_automatic_recording', {'recordingMode': 'automatic'})

        if settings.ACANO_ALWAYS_CREATE_RECORDING_CALL:
            if not meeting.api.get_calls(cospace=cospace['id']):
                meeting.api.add_call(cospace)

        if cospace.get('callProfile'):
            recording.recording_id2 = cospace['callProfile']

        meeting.api.update_cospace(meeting.provider_ref2, {
            'callProfile': call_profile.commit(),
        })

        recording.recording_id = recording.pk
        recording.activate(commit=True)

    def close_call(self, meeting, recording, recorder_id=None):

        cospace = meeting.api.get_cospace(meeting.provider_ref2)

        call_profile = meeting.api._call_profile('cospace', cospace['id'])
        call_profile.add_settings('recording_manual_recording', {'streamingMode': 'manual'})
        call_profile.pop_settings('recording_automatic_recording')

        meeting.api.update_cospace(meeting.provider_ref2, {'callProfile': call_profile.commit()})

        calls, count = meeting.api.get_clustered_calls(cospace=meeting.provider_ref2)
        for call in calls:
            try:
                meeting.api.update_call(call['id'], {'recording': 'false'})
            except NotFound:
                pass

        call_profile.pop_settings('recording_automatic_recording')
        call_profile.pop_settings('recording_manual_recording')

        meeting.api.update_cospace(meeting.provider_ref2, {'callProfile': call_profile.commit()})
        recording.deactivate(commit=True)

    def get_call(self, recording_id):
        from recording.models import MeetingRecording
        try:
            if MeetingRecording.objects.filter(provider=self.provider, recording_id=recording_id).last().meeting.backend_active:
                return {'active': True}  # TODO possible to check? Use call/ attribute streaming in acano?
        except (MeetingRecording.DoesNotExist, AttributeError):
            pass
        return None

    def adhoc_record(self, api, call_id, **kwargs):

        call, api = api.get_clustered_call(call_id)[0]

        call_profile = api._call_profile('call', call_id, cospace_id=call['cospace'])
        call_profile.add_settings('adhoc_manual_record', {'recordingMode': 'manual'})

        try:
            api.update_call(call_id, {'recording': 'true', 'callProfile': call_profile.commit()})
        except NotFound:
            raise

    def adhoc_stop_record(self, api, call_id):

        call, api = api.get_clustered_call(call_id)[0]

        call_profile = api._call_profile('call', call_id, cospace_id=call['cospace'])
        call_profile.add_settings('adhoc_manual_record', {'recordingMode': 'manual'})

        try:
            api.update_call(call_id, {'callProfile': call_profile.commit()})
            api.update_call(call_id, {'recording': 'false'})
        except NotFound:
            pass

        call_profile.pop_settings('manual_record')
        call_profile.commit()


    def get_video_url_for_recording(self, recording):
        from recording.models import AcanoRecording

        recording_data = AcanoRecording.objects.filter(cospace_id=recording.meeting.provider_ref2).first()  # TODO multiple
        if not recording_data:
            return ''
        return self.get_video_url(recording_data.secret_key)

    def get_video_url(self, secret_key):

        return urljoin(self.provider.web_host or self.provider.hostname, '/videos/auth/{}.mp4'.format(secret_key))

    def get_acano_recordings(self, meeting):
        from recording.models import AcanoRecording
        recordings = AcanoRecording.objects.filter(cospace_id=meeting.provider_ref2)

        recordings = recordings.filter(ts_start__gt=meeting.ts_start - timedelta(hours=2), ts_stop__lt=meeting.ts_stop + timedelta(hours=2))
        return recordings

    def get_embed(self, meeting, recording):

        videos = []

        for recording_data in self.get_acano_recordings(meeting):
            videos.append({
                'path': recording_data.path,
                'url': self.get_video_url(recording_data.secret_key),
            })

        result = {
            'type': 'acano',
            'thumbnail': '',
            'videos': videos,
        }
        recording.video_sources = json.dumps(result)
        recording.save()

        meeting.recording_embed_callback()
        return result

    def get_embed_code(self, recording=None, secret_key=None):

        if recording:
            video_url = self.get_video_url_for_recording(recording)
        elif secret_key:
            video_url = self.get_video_url(secret_key)
        else:
            raise ValueError('recording or secret key must be provided')

        return '<div><video controls style="max-width: 100%;"><source src="{}" type="video/mp4" /></video></div>'.format(video_url)

    def get_embed_callback_data(self, meeting, recording):
        from provider.models.utils import date_format

        data = []

        if not recording.error:

            for r in self.get_acano_recordings(meeting):

                cur = {
                    'ts_created': date_format(r.ts_start or now()),
                    'error': recording.error,
                    'video_sources': json.loads(recording.video_sources or '{}'),
                    'embed_code': self.get_embed_code(recording),
                    'recording_id': 'acano-{}'.format(recording.pk),
                }
                data.append(cur)

        return data

