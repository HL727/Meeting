from django.core.cache import cache
from rest_framework import serializers

from .models import Customer, CustomerKey, CustomerMatch
from provider.models.provider import Provider, VideoCenterProvider


class CustomerSerializer(serializers.ModelSerializer):

    mcu_provider = serializers.PrimaryKeyRelatedField(source='lifesize_provider', queryset=Provider.objects.all(), required=False, allow_null=True)
    recording_provider = serializers.PrimaryKeyRelatedField(source='videocenter_provider', queryset=VideoCenterProvider.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Customer
        fields = ('id', 'title', 'shared_key', 'mcu_provider', 'recording_provider', 'streaming_provider', 'enable_core', 'enable_epm', 'acano_tenant_id')
        read_only_fields = ('id',)


class CustomerAdminSerializer(CustomerSerializer):

    usage = serializers.SerializerMethodField(read_only=True)

    def get_usage(self, obj):
        cache_key = 'customeradmin.serializer.usage.{}'.format(obj.pk)
        cached = cache.get(cache_key)
        if cached:
            return cached

        result = self.get_usage_real(obj)
        cache.set(cache_key, result, 90)
        return result

    def get_usage_real(self, obj):

        if 'usage_count' in self.context:
            counts = self.context['usage_count']
        else:
            counts = Customer.objects.get_usage_counts([obj])

        result = {}
        for k in counts:
            result[k] = counts[k].get(obj.pk)

        return result

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + ('usage', 'acano_tenant_id', 'pexip_tenant_id')


class CustomerNameOnlySerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer
        fields = ('id', 'title')


class CustomerKeySerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomerKey
        fields = ('customer', 'shared_key', 'active')


class CustomerMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerMatch
        fields = ('cluster', 'customer', 'prefix_match', 'suffix_match', 'regexp_match')
