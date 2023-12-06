from datetime import date, timedelta

from django.db import models
from django.db.models.aggregates import Sum
from rest_framework import serializers

from policy_rule.models import PolicyRule, PolicyRuleHitCount
from provider.api.pexip.serializers import ConferenceSerializer
from provider.exceptions import DuplicateError, ResponseError


class PexipProxySerializer(serializers.Serializer):

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    address = serializers.CharField()
    port = serializers.IntegerField(default=443)
    description = serializers.CharField(allow_blank=True)


class AzureTenantSerializer(serializers.Serializer):

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    tenant_id = serializers.CharField(write_only=True)


class TeamsProxySerializer(PexipProxySerializer):

    azure_tenant = AzureTenantSerializer()


class MSSipSerialiser(PexipProxySerializer):
    transport = serializers.ChoiceField(default='tcp', choices=[(x, x) for x in [
        'tcp',
        'tls',
    ]])


class GMSAccessTokenSerializer(serializers.Serializer):

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    token = serializers.CharField(write_only=True)


class PolicyRuleSerializer(serializers.ModelSerializer):

    hit_count = serializers.SerializerMethodField()
    hit_count_long = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not isinstance(self.instance, models.Model) or not self.instance.pk:
            self.fields['cluster'].read_only = True

    class Meta:
        model = PolicyRule
        read_only_fields = ('external_id', 'in_sync')
        exclude = ()

    def _get_hit_count(self, obj, cache_key, since_date):
        if not obj.pk:
            return 0
        if cache_key in self.context and obj.pk:
            return self.context[cache_key].get(obj.pk, 0)
        return PolicyRuleHitCount.objects.filter(rule=obj, date__gte=since_date) \
                   .aggregate(total=Sum('count'))['total'] or 0

    def get_hit_count(self, obj):
        return self._get_hit_count(obj, 'hit_count', since_date=date.today())

    def get_hit_count_long(self, obj):
        return self._get_hit_count(obj, 'hit_count_long', since_date=date.today() - timedelta(days=6 * 30))

    def validate(self, attrs):
        if not attrs.get('match_incoming_calls') and not attrs.get('match_outgoing_calls'):
            raise serializers.ValidationError({'match_incoming_calls': 'Incoming or outgoing must be checked'})
        return attrs

    def save(self, **kwargs):
        try:
            return super().save(cluster=self.context['cluster'])
        except (ResponseError, DuplicateError) as e:
            try:
                data = e.args[1].json()
                data = data.get('gateway_routing_rule') or data
            except (AttributeError, ValueError):
                data = {'__all__': 'Invalid response format from server'}
            raise serializers.ValidationError(data)


class PolicyRuleTraceSerializer(serializers.Serializer):

    local_alias = serializers.CharField()
    remote_alias = serializers.CharField()
    call_direction = serializers.CharField(default='dial_in', required=False, allow_blank=True)
    protocol = serializers.CharField(default='sip', required=False, allow_blank=True)
    is_registered = serializers.BooleanField(required=False)
    location = serializers.CharField(required=False, allow_blank=True)


class PolicyRuleTraceResponseSerializer(serializers.Serializer):

    conference = ConferenceSerializer()
    rules = PolicyRuleSerializer(many=True, required=False)


