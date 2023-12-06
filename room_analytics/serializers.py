from rest_framework import serializers

from endpoint.consts import MeetingStatus
from endpoint.models import EndpointStatus, EndpointMeetingParticipant


class EndpointMeetingSerializer(serializers.ModelSerializer):

    class Meta:
        model = EndpointMeetingParticipant
        fields = (
            'head_count',
            'presence',
            'air_quality',
            'ts_connected',
            'meeting',
            'meeting_status',
        )
        read_only_fields = fields[:]


class EndpointRoomStatusSerializer(serializers.ModelSerializer):

    active_meeting = EndpointMeetingSerializer(required=False, allow_null=True)
    meeting_status = serializers.SerializerMethodField()

    def get_meeting_status(self, obj):
        if not obj.active_meeting_id:
            return MeetingStatus.NO_MEETING
        return obj.active_meeting.meeting_status

    class Meta:
        model = EndpointStatus
        fields = (
            'endpoint',
            'status',
            'presence',
            'head_count',
            'air_quality',
            'temperature',
            'humidity',
            'active_meeting',
            'meeting_status',
        )
        read_only_fields = fields[:]

