from datetime import timedelta

from django.utils.timezone import now
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from customer.models import CustomerMatch, Customer
from policy_auth.models import PolicyAuthorizationOverride, PolicyAuthorization


class PolicyAuthorizationOverrideSerializer(serializers.ModelSerializer):

    user = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = PolicyAuthorizationOverride
        read_only_fields = ('user',)
        exclude = ('customer',)
        extra_kwargs = {
            'cluster': {'required': False},
        }


class PolicyAuthorizationSerializer(serializers.ModelSerializer):
    """
    Specify active time using either `valid_from` and `valid_to`, or `timeout`.
    Cluster and customer will be determined automatically from user permission and local_alias.
    Admins must have already set the number series for the `local_alias` to require authorization
    """

    user = serializers.CharField(source='user.username', read_only=True)
    timeout = serializers.IntegerField(write_only=True, allow_null=True, required=False, help_text='Countdown until this authorization expires in seconds')
    is_active = serializers.BooleanField(read_only=True)

    def validate(self, validated_data):
        c = validated_data.copy()
        if c.get('timeout'):
            if c.get('valid_from') and c.get('valid_to'):
                raise serializers.ValidationError({'timeout': 'timeout, valid_from and valid_to can\'t all be provided at the same time'})
            if c.get('valid_to'):
                c['valid_from'] = c['valid_to'] - timedelta(seconds=c['timeout'])
            else:
                c['valid_to'] = (c.get('valid_from') or now()) + timedelta(seconds=c['timeout'])

            c.pop('timeout')
        elif not c.get('valid_to'):
            raise serializers.ValidationError(
                {'valid_from': 'Please pass valid_to or timeout, or use override for permanent posts'})

        if not c.get('valid_from'):
            c['valid_from'] = now()

        if c['valid_from'] > c['valid_to']:
            raise serializers.ValidationError(
                {'valid_to': 'valid_to must be greater than valid_from'})

        customer = CustomerMatch.objects.match(obj={'local_alias': c['local_alias']}, cluster=c.get('cluster'))
        if not customer:
            raise serializers.ValidationError({'local_alias': 'local_alias does not match any customer rules'})

        if customer and not c.get('cluster'):
            c['cluster'] = customer.get_provider()

        if customer.get_provider() != c['cluster'] or not c['cluster']:
            raise serializers.ValidationError({'cluster': 'Customer does not use specified cluster'})

        if not any(c == customer for c in Customer.objects.get_for_user(self.context['request'].user)):
            raise PermissionDenied({'local_alias': 'Permission denied for customer owning local_alias'})

        if c.get('source') and not c.get('external_id') and len(c.get('source') or '') == 36:
            c['external_id'] = c.pop('source')  # move guid to source field

        c['customer'] = customer
        c['user'] = self.context['request'].user
        return c

    class Meta:
        model = PolicyAuthorization
        exclude = ()
        read_only_fields = ('customer', 'first_use', 'created', 'user', 'usage_count')

        extra_kwargs = {
            'cluster': {'required': False},
            'valid_from': {'required': False, 'allow_null': True, 'default': None},
            'valid_to': {'required': False, 'allow_null': True},
        }

    def update(self, instance, validated_data):
        validated_data['customer'] = validated_data.get('customer') or self.context['customer']
        return super().update(instance, validated_data)

    def create(self, validated_data):
        validated_data['customer'] = validated_data.get('customer') or self.context['customer']
        return super().create(validated_data)
