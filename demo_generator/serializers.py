from django.utils.translation import ngettext

from rest_framework import serializers

from rest_framework.exceptions import PermissionDenied

from endpoint.models import Endpoint
from customer.models import Customer
from provider.models.provider import Provider

from statistics.models import Server, ServerTenant, Tenant


class DemoGeneratorCallsSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    participants = serializers.IntegerField(required=False, default=2)
    days = serializers.IntegerField(required=False, default=1)
    calls = serializers.IntegerField(required=False, default=10)
    randomize_meeting_room = serializers.BooleanField(required=False)
    generate_for_endpoints = serializers.BooleanField(required=False)
    endpoint_percent = serializers.FloatField(required=False, default=10.0)

    cospaces = serializers.JSONField(required=False)
    endpoints = serializers.PrimaryKeyRelatedField(queryset=Endpoint.objects.all(), many=True, required=False)
    provider = serializers.PrimaryKeyRelatedField(queryset=Provider.objects.all(), required=False)
    server = serializers.PrimaryKeyRelatedField(queryset=Server.objects.all(), required=False)
    endpoint_server = serializers.PrimaryKeyRelatedField(queryset=Server.objects.all(), required=False)

    def validate(self, data):
        from django.conf import settings

        if not settings.ENABLE_DEMO:
            raise PermissionDenied()

        customer = data['customer']
        api = customer.get_api()
        provider = customer.get_provider()

        data['provider'] = provider
        data['server'] = provider.get_statistics_server()

        if data.get('randomize_meeting_room'):
            data['cospaces'] = api.find_cospaces('')[0]

        if data.get('generate_for_endpoints') and not data.get('endpoints'):
            data['endpoints'] = Endpoint.objects.filter(customer=customer)

        if data.get('endpoints') and data.get('generate_for_endpoints') and data.get('endpoint_percent') > 0.0:
            data['endpoint_percent'] = data['endpoint_percent'] / 100

            endpoint_server = Server.objects.get_endpoint_server(customer)

            data['endpoint_server'] = endpoint_server
            tenant = Tenant.objects.get_or_create(guid=customer.tenant_id)[0]
            ServerTenant.objects.get_or_create(tenant=tenant, server=endpoint_server)
        else:
            data['endpoint_percent'] = 0.0

        return data


class DemoGeneratorHeadCountSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    days = serializers.IntegerField(required=False, default=1)
    endpoints = serializers.PrimaryKeyRelatedField(queryset=Endpoint.objects.all(), many=True, required=False)

    def validate(self, data):
        from django.conf import settings

        if not settings.ENABLE_DEMO:
            raise PermissionDenied()

        if not data.get('endpoints'):
            data['endpoints'] = Endpoint.objects.filter(customer=data['customer'])

        return data


class DemoGeneratorResponseSerializer(serializers.Serializer):
    details = serializers.JSONField()
