from rest_framework import serializers

from api_key.models import OAuthCredential
from exchange.forms import EWSOauthSetupForm


class OAuthCredentialSerializer(serializers.ModelSerializer):

    name = serializers.CharField(source='__str__', read_only=True)
    has_secret = serializers.SerializerMethodField()

    def get_has_secret(self, obj):
        return bool(obj.secret)

    def validate(self, attrs):
        if not self.context.get('customer'):
            raise KeyError('Customer must be provided to serializer context!')

        if self.instance and self.instance.customer_id:
            pass
        else:
            attrs['customer'] = self.context['customer']

        if attrs.get('type') == OAuthCredential.EXCHANGE:
            form = EWSOauthSetupForm(attrs, instance=self.instance, customer=self.context['customer'])
        else:
            form = EWSOauthSetupForm(attrs, instance=self.instance, customer=self.context['customer'])
        if not form.is_valid():
            raise serializers.ValidationError(form.errors)
        return attrs

    class Meta:
        model = OAuthCredential
        fields = ('id', 'name', 'username', 'client_id', 'tenant_id', 'secret', 'use_app_authorization', 'type', 'has_secret', 'callback_url')
        read_only_fields = ('id', 'callback_url')
        write_only_fields = ('secret',)

        extra_kwargs = {
            'password': {'write_only': True}
        }
