from rest_framework import serializers

from endpoint_backup.models import EndpointBackup


class EndpointBackupSerializer(serializers.ModelSerializer):

    endpoint_name = serializers.StringRelatedField(source='endpoint')

    class Meta:
        model = EndpointBackup
        fields = (
            'id',
            'ts_created',
            'ts_completed',
            'error',
            'hash',
            'slug',
            'endpoint',
            'endpoint_name',
        )
        read_only_fields = ('id', 'endpoint_name', 'slug')
