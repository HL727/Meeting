from rest_framework import serializers

from tracelog.models import ActiveTraceLog


class ActiveTraceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActiveTraceLog
        exclude = ()
        read_only_fields = ('user', 'ts_created')
