
from rest_framework import serializers

from .models import EndpointProxy, EndpointProxyStatusChange


def get_endpoint_count_method(self, obj):
    from endpoint.models import Endpoint

    endpoints = Endpoint.objects.filter(proxy=obj, connection_type=Endpoint.CONNECTION.PROXY)
    return {
        'total': endpoints.count(),
        'online': endpoints.filter(status__status=Endpoint.STATUS.ONLINE).count(),
    }


class EndpointProxyStatusSerializer(serializers.ModelSerializer):

    endpoint_count = serializers.SerializerMethodField(read_only=True)

    get_endpoint_count = get_endpoint_count_method

    class Meta:
        model = EndpointProxy
        fields = (
            'id',
            'name',
            'is_online',
            'last_active',
            'last_connect',
            'endpoint_count',
        )


class EndpointProxySerializer(serializers.ModelSerializer):

    ip_nets = serializers.StringRelatedField(many=True, read_only=True)
    endpoint_count = serializers.SerializerMethodField(read_only=True)

    get_endpoint_count = get_endpoint_count_method

    class Meta:
        model = EndpointProxy
        fields = (
            'id',
            'name',
            'first_ip',
            'last_connect_ip',
            'ip_nets',
            'is_online',
            'last_active',
            'last_connect',
            'ts_created',
            'ts_activated',
            'endpoint_count',
        )
        read_only_fields = tuple(f for f in fields if f not in ('name',))


class EndpointProxyEditSerializer(serializers.ModelSerializer):

    ip_nets = serializers.ListField(write_only=True, required=False)

    class Meta:
        model = EndpointProxy
        fields = (
            'name',
            'ip_nets',
        )


class EndpointProxyStatusChangeSerializer(serializers.ModelSerializer):

    proxy = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = EndpointProxyStatusChange
        fields = (
            'id',
            'proxy',
            'ts_created',
            'is_connect',
            'is_online'
        )
        read_only_fields = tuple(f for f in fields)
