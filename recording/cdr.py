import requests
from django.conf import settings

from provider.models.provider import VideoCenterProvider
from .models import AcanoRecording, AcanoStream
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from statistics import models as statistics
import json


def parse_cdr(record, cluster=None):

    parser = AcanoCDRParser(record, cluster=cluster)
    result = []
    for node in record:
        cur = parser.parse(node)
        result.append(cur)

    return result


class AcanoCDRParser:
    def __init__(self, record, cluster=None):
        self.record = record
        self.cluster = cluster

    def parse(self, node):

        type = self.record.get('type')

        if type == 'recordingStart':
            return self.parse_recording_start(node)
        elif type == 'recordingEnd':
            return self.parse_recording_end(node)
        elif type == 'streamingStart':
            return self.parse_streaming_start(node)
        elif type == 'streamingEnd':
            return self.parse_streaming_end(node)

    def get_call(self, guid: str):
        return statistics.Call.objects.filter(guid=guid, server__cluster=self.cluster).first()

    def parse_recording_start(self, node):

        if node.get('time'):
            ts_start = parse_datetime(self.record.get('time'))
        else:
            ts_start = now()

        recording_id = node.get('id')

        data = {
            'path': node.findtext('./path', '').strip(),
            'call_id': node.findtext('./call', '').strip(),
            'call_leg_id': node.findtext('./callLeg', '').strip(),
            'ts_start': ts_start,
        }
        call_data = self.get_call(data['call_id'])
        if call_data:
            data.update({
                'tenant_id': call_data.tenant,
                'cospace_id': call_data.cospace_id,
                'title': call_data.cospace,
                'targets': json.dumps(self._get_targets_from_call(call_data)),
            })

        return AcanoRecording.objects.get_or_create(recording_id=recording_id, defaults=data)[0]

    def parse_recording_end(self, node):

        if node.get('time'):
            ts_stop = parse_datetime(self.record.get('time'))
        else:
            ts_stop = now()

        recording_id = node.get('id')

        recording = AcanoRecording.objects.filter(recording_id=recording_id).first()
        if recording:
            recording.ts_stop = ts_stop
            call_data = self.get_call(recording.call_id)
            if call_data:
                targets = json.loads(recording.targets or '[]')
                targets.extend(self._get_targets_from_call(call_data))
                recording.targets = json.dumps(list(set(targets)))
            recording.save()

            self._send_meeting_embed_callbacks(recording)
            return recording

    def parse_streaming_start(self, node):

        if node.get('time'):
            ts_start = parse_datetime(self.record.get('time'))
        else:
            ts_start = now()

        stream_id = node.get('id')

        data = {
            'stream_url': node.findtext('./streamUrl', '').strip(),
            'call_id': node.findtext('./call', '').strip(),
            'call_leg_id': node.findtext('./callLeg', '').strip(),
            'ts_start': ts_start,
        }

        call_data = self.get_call(data['call_id'])
        if call_data:
            data.update({
                'tenant_id': call_data.tenant,
                'cospace_id': call_data.cospace_id,
                'targets': json.dumps(self._get_targets_from_call(call_data)),
            })

        return AcanoStream.objects.get_or_create(stream_id=stream_id, defaults=data)[0]

    def parse_streaming_end(self, node):

        if node.get('time'):
            ts_stop = parse_datetime(self.record.get('time'))
        else:
            ts_stop = now()

        stream_id = node.get('id')

        stream = AcanoStream.objects.filter(stream_id=stream_id).first()
        if stream:
            stream.ts_stop = ts_stop
            call_data = statistics.Call.objects.filter(guid=stream.call_id).first()
            if call_data:
                targets = json.loads(stream.targets or '[]')
                targets.extend(self._get_targets_from_call(call_data))
                stream.targets = json.dumps(list(set(targets)))
            stream.save()

            return stream

    def _get_targets_from_call(self, call):

        if not call:
            return []

        return list(set(call.legs.all().values_list('target', flat=True)))

    def _send_meeting_embed_callbacks(self, recording):
        from recording.models import MeetingRecording
        from sentry_sdk import capture_exception

        if recording.ts_start and recording.ts_stop and (recording.ts_stop - recording.ts_start).total_seconds() < 15:
            return  # TODO send error?

        stream_url = ''
        stream_id = ''

        for r in MeetingRecording.objects.filter(meeting__provider_ref2=recording.cospace_id):
            if r.meeting.ts_stop >= recording.ts_start and r.meeting.ts_start <= recording.ts_stop:
                if r.provider.is_acano_native:
                    stream_url = r.stream_url
                    stream_id = r.recording_id

            try:
                r.meeting.recording_embed_callback()
            except Exception:
                capture_exception()

        if not stream_url and not stream_id:
            from datastore.models import acano as ds

            stream_url = (
                ds.CoSpace.objects.filter(cid=recording.cospace_id)
                .values_list('stream_url')
                .first()
                or ''
            )

        # mividas video

        data = {
                'tenant_id': recording.tenant_id or 'default',
                'title': recording.title,
                'cospace_id': recording.cospace_id,
                'recording_id': recording.recording_id,
                'path': '{}.mp4'.format(recording.path),
                'ts_start': str(recording.ts_start),
                'ts_stop': str(recording.ts_stop),
                'stream_key': stream_url or stream_id,
                'done': '1',
        }

        for server in VideoCenterProvider.objects.filter(
            type=VideoCenterProvider.MIVIDAS_STREAMING,
            customer__lifesize_provider=self.cluster,
        ):
            requests.post('https://{}/api/v1/cms_callback/'.format(server), data)
