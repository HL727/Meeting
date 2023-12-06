from rest_framework import serializers

from api_key.models import OAuthCredential
from api_key.serializers import OAuthCredentialSerializer
from .forms import EWSSetupForm
from .models import EWSCredentials


class EWSCredentialsSerializer(serializers.ModelSerializer):

    oauth_credential = OAuthCredentialSerializer(required=False)
    token_update_url = serializers.SerializerMethodField()

    def get_token_update_url(self, obj):
        return obj.oauth_credential.get_absolute_url() if obj.oauth_credential_id else ''

    def create(self, validated_data):
        data = validated_data.copy()

        oauth_credential_data = data.pop('oauth_credential', None)
        if oauth_credential_data:
            oauth_credential_data['type'] = OAuthCredential.EXCHANGE

            serializer = OAuthCredentialSerializer(data=oauth_credential_data, context=self.context)
            serializer.is_valid()
            data['oauth_credential'] = serializer.save()

        return super().create(data)

    def validate(self, attrs):
        form = EWSSetupForm(attrs, instance=self.instance)
        if not form.is_valid():
            raise serializers.ValidationError(form.errors)
        return attrs

    class Meta:
        model = EWSCredentials
        fields = ('id', 'username', 'password', 'oauth_credential', 'server', 'customer', 'last_sync', 'last_incremental_sync', 'last_sync_error', 'token_update_url', 'is_working', 'enable_sync')
        read_only_fields = ('id', 'customer', 'last_sync', 'last_incremental_sync', 'last_sync_error', 'is_working')

        extra_kwargs = {
            'password': {'write_only': True}
        }
