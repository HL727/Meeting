from rest_framework import serializers

from api_key.models import OAuthCredential
from api_key.serializers import OAuthCredentialSerializer
from .models import MSGraphCredentials


class MSGraphCredentialsSerializer(serializers.ModelSerializer):

    oauth_credential = OAuthCredentialSerializer(required=True)
    token_update_url = serializers.SerializerMethodField()
    name = serializers.CharField(source='__str__', read_only=True)

    def get_token_update_url(self, obj):
        return obj.oauth_credential.get_absolute_url() if obj.oauth_credential_id else ''

    def create(self, validated_data):
        data = validated_data.copy()

        oauth_credential_data = data.pop('oauth_credential')
        oauth_credential_data['type'] = OAuthCredential.MSGRAPH

        serializer = OAuthCredentialSerializer(data=oauth_credential_data, context=self.context)
        serializer.is_valid()
        data['oauth_credential'] = serializer.save()

        return super().create(data)

    class Meta:
        model = MSGraphCredentials
        fields = ('id', 'name', 'username', 'oauth_credential', 'customer', 'last_sync', 'last_incremental_sync', 'last_sync_error', 'token_update_url', 'is_working', 'enable_sync')
        read_only_fields = ('id', 'customer', 'last_sync', 'last_incremental_sync', 'last_sync_error', 'is_working')
