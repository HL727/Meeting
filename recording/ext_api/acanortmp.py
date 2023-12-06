from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.timezone import now
from django.utils.translation import gettext as _

from provider.exceptions import NotFound
from provider.ext_api.base import RecordingProviderAPI
import json
import logging

if TYPE_CHECKING:
    from recording.models import MeetingRecording
    from meeting.models import Meeting
    from provider.ext_api.pexip import PexipAPI
    from provider.ext_api.acano import AcanoAPI


logger = logging.getLogger(__name__)


class RTMPStreamAPI(RecordingProviderAPI):

    can_update_acano_stream_url = True
    provides_recording = False
    provides_playback = False

    def get_stream_url(self, cospace_id=None):
        key = self.provider.recording_key.replace('mp4:', '')
        dynamic = cospace_id  # TODO clean

        if '%s' in key:
            if not dynamic:
                return None
            return key.replace('%s', dynamic)

        return key

    def get_call(self, recording_id):
        from recording.models import MeetingRecording

        try:
            if (
                MeetingRecording.objects.filter(provider=self.provider, recording_id=recording_id)
                .last()
                .meeting.backend_active
            ):
                return {
                    'active': True
                }  # TODO possible to check? Use call/ attribute streaming in acano?
        except (MeetingRecording.DoesNotExist, AttributeError):
            pass
        return None

    def get_embed(self, meeting: Meeting, recording: MeetingRecording):

        recording.video_sources = json.dumps(
            {  # TODO
                'type': 'rtmp',
                'thumbnail': '',
                'videos': [],
            }
        )

        recording.save()

        meeting.recording_embed_callback()

    def get_embed_code(self, recording):
        return _('Gå till din leverantör för att se filmen')  # TODO

    def get_recording_id(self, recording):
        return 'rtmp-{}'.format(recording.pk)

    def get_embed_callback_data(self, meeting: Meeting, recording: MeetingRecording):
        from provider.models.utils import date_format

        data = []
        if not recording.error:  # nothing to send

            cur = {
                'ts_created': date_format(recording.ts_activated or now()),
                'error': recording.error,
                'video_sources': json.loads(recording.video_sources or '{}'),
                'embed_code': self.get_embed_code(recording),
                'recording_id': self.get_recording_id(recording),
                'is_live': True,
            }

            data.append(cur)

        return data

    def dialout(self, meeting: Meeting, recording: MeetingRecording):
        api = meeting.api
        if api.cluster.is_acano:
            return AcanoRTMPStreamAPI.dialout(self, meeting, recording)
        elif api.cluster.is_pexip:
            return AcanoRTMPStreamAPI.dialout(self, meeting, recording)

    def close_call(self, meeting: Meeting, recording: MeetingRecording, recorder_id=None):
        api = meeting.api
        if api.cluster.is_acano:
            return AcanoRTMPStreamAPI.close_call(self, meeting, recording, recorder_id=recorder_id)

    def adhoc_record(self, api: AcanoAPI, call_id, **kwargs):
        if api.cluster.is_acano:
            return AcanoRTMPStreamAPI.adhoc_record(self, api, call_id, **kwargs)
        elif api.cluster.is_pexip:
            return PexipRTMPStreamAPI.adhoc_record(self, api, call_id, **kwargs)

    def adhoc_stop_record(self, api: AcanoAPI, call_id, **kwargs):
        if api.cluster.is_acano:
            return AcanoRTMPStreamAPI.adhoc_stop_record(self, api, call_id, **kwargs)
        elif api.cluster.is_pexip:
            return PexipRTMPStreamAPI.adhoc_record(self, api, call_id, **kwargs)


class AcanoRTMPStreamAPI(RTMPStreamAPI):
    def dialout(self, meeting: Meeting, recording: MeetingRecording):

        cospace = meeting.api.get_cospace(meeting.provider_ref2)

        call_profile = meeting.api._call_profile('cospace', cospace['id'])
        call_profile.add_settings('automatic_streaming', {'streamingMode': 'automatic'})

        meeting.api.update_cospace(meeting.provider_ref2, {
            'streamUrl': recording.stream_url or self.get_stream_url(meeting.provider_ref),
            'callProfile': call_profile.commit(),
        })

        recording.recording_id = recording.recording_id or recording.pk  # maybe set by schedule
        recording.activate(commit=True)

    def close_call(self, meeting: Meeting, recording: MeetingRecording, recorder_id=None):

        call_profile = meeting.api._call_profile('cospace', meeting.provider_ref2)

        call_profile.pop_settings('automatic_streaming')
        call_profile.add_settings('stream_manual_streaming', {'streamingMode': 'manual'})

        meeting.api.update_cospace(meeting.provider_ref2, {'callProfile': call_profile.commit()})

        calls, count = meeting.api.get_clustered_calls(cospace=meeting.provider_ref2)
        for call in calls:
            try:
                meeting.api.update_call(call['id'], {'streaming': 'false'})
            except NotFound:
                pass

        call_profile.pop_settings('stream_manual_streaming')
        call_profile.commit()

        recording.deactivate(commit=True)

    def adhoc_record(self, api, call_id, **kwargs):

        call, api = api.get_clustered_call(call_id)[0]

        call_profile = api._call_profile('call', call_id, cospace=call['cospace'])
        call_profile.add_settings('stream_manual_streaming', {'streamingMode': 'manual'})

        try:
            api.update_call(call_id, {'callProfile': call_profile.commit()})
            api.update_call(call_id, {'streaming': 'true'})
        except NotFound:
            raise

    def adhoc_stop_record(self, api, call_id, **kwargs):

        call, api = api.get_clustered_call(call_id)[0]

        call_profile = api._call_profile('call', call_id, cospace=call['cospace'])
        call_profile.add_settings('stream_manual_streaming', {'streamingMode': 'manual'})

        try:
            api.update_call(call_id, {'callProfile': call_profile.commit()})
            api.update_call(call_id, {'streaming': 'false'})
        except NotFound:
            pass

        call_profile.pop_settings('stream_manual_streaming')
        call_profile.commit()


class PexipRTMPStreamAPI(RTMPStreamAPI):
    def dialout(self, meeting: Meeting, recording: MeetingRecording):

        api: PexipAPI = meeting.api
        leg_id = api.start_stream(
            meeting.get_connection_data()['uri'],
            recording.stream_url or self.get_stream_url(meeting.provider_ref),
        )

        recording.recording_id = recording.recording_id or recording.pk  # maybe set by schedule
        recording.recording_id2 = leg_id
        recording.activate(commit=True)

    def close_call(self, meeting: Meeting, recording: MeetingRecording, recorder_id=None):

        api: PexipAPI = meeting.api
        api.hangup_call_leg(recording.recording_id2)
        recording.deactivate(commit=True)

    def adhoc_record(
        self,
        api: PexipAPI,
        call_id,
        *,
        local_alias: str = None,
        cospace: dict = None,
        stream_url: str = None,
        stream_presentation_url: str = None,
        **kwargs
    ):

        numeric_id = call_id
        if cospace and cospace.get('call_id'):
            numeric_id = cospace['call_id']

        return api.start_stream(
            local_alias or api.get_sip_uri(numeric_id),
            stream_url or self.get_stream_url(call_id),
            stream_presentation_url,
        )

    def adhoc_stop_record(
        self, api: PexipAPI, call_id, *, stream_url=None, stream_presentation_url=None, **kwargs
    ):
        find_urls = [
            url
            for url in (stream_url, stream_presentation_url, self.get_stream_url(call_id))
            if url
        ]

        legs = [l for l in api.get_call_legs(call_id)[0] if l.get('remote') in find_urls]
        for leg in legs:
            api.hangup_participant(leg['id'])
