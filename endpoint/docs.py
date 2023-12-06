from rest_framework import serializers

from endpoint.models import Endpoint
from endpoint.view_mixins import CustomerFilteredPrimaryKeyField
from endpoint_provision.models import EndpointFirmware


class EndpointListFilterSerializer(serializers.Serializer):

    mac_address = serializers.CharField(max_length=100, required=False, allow_blank=True)
    serial_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    firmware = serializers.CharField(max_length=100, required=False, allow_blank=True)
    product_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    ip = serializers.IPAddressField(required=False)
    location = serializers.CharField(max_length=100, required=False, allow_blank=True)
    org_unit = serializers.IntegerField(required=False)
    only_new = serializers.BooleanField(initial=None, required=False, allow_null=True)


class ReportSerializer(serializers.Serializer):

    pass


class ReportBodySerializer(serializers.Serializer):

    endpoints = CustomerFilteredPrimaryKeyField(queryset=Endpoint.objects.all(), many=True)
    values = serializers.ListField(child=serializers.ListField(child=serializers.CharField(label='Key for level')))


class BasicResponseSerializer(serializers.Serializer):

    status = serializers.CharField()
    error = serializers.CharField(required=False, allow_blank=True)


class EndpointConfigurationValueSerializer(serializers.Serializer):

    key = serializers.ListField(child=serializers.CharField())
    value = serializers.CharField(allow_blank=True, allow_null=True)


class EndpointSetConfigurationSerializer(serializers.Serializer):

    settings = EndpointConfigurationValueSerializer(many=True)


class EndpointDialInfoSerializer(serializers.Serializer):

    name = serializers.CharField(required=False, allow_blank=True)
    sip = serializers.CharField(required=False, allow_blank=True)
    sip_display_name = serializers.CharField(required=False, allow_blank=True)
    h323 = serializers.CharField(required=False, allow_blank=True)
    h323_e164 = serializers.CharField(required=False, allow_blank=True)
    sip_proxy = serializers.CharField(required=False, allow_blank=True)
    sip_proxy_username = serializers.CharField(required=False, allow_blank=True)
    sip_proxy_password = serializers.CharField(required=False, allow_blank=True)
    h323_gatekeeper = serializers.CharField(required=False, allow_blank=True)


class FilterBodySerializer(serializers.Serializer):
    manufacturer = serializers.ListField(child=serializers.CharField())
    product_name = serializers.ListField(child=serializers.CharField())
    firmware = serializers.ListField(child=serializers.CharField())
    location = serializers.ListField(child=serializers.CharField())


class EndpointStatusSerializer(serializers.Serializer):
    has_direct_connection = serializers.CharField()
    uptime = serializers.CharField()
    status = serializers.CharField()
    incoming = serializers.CharField()
    in_call = serializers.CharField()
    muted = serializers.BooleanField()
    volume = serializers.CharField(allow_null=True)
    inputs = serializers.ListField(child=serializers.DictField())
    presentation = serializers.ListField(child=serializers.DictField())
    call_duration = serializers.CharField()
    upgrade = serializers.CharField()
    warnings = serializers.ListField(child=serializers.CharField())
    diagnostics = serializers.ListField(child=serializers.DictField())

    presence = serializers.BooleanField(allow_null=True)
    head_count = serializers.IntegerField(allow_null=True)
    temperature = serializers.IntegerField(allow_null=True)
    humidity = serializers.IntegerField(allow_null=True)
    air_quality = serializers.IntegerField(allow_null=True)


class EndpointStatusFlagSerializer(serializers.Serializer):

    cached = serializers.ChoiceField(
        choices=(('true', 'Allow cache'), ('force', 'Only cached')), allow_blank=True
    )


class CallControlResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    status = EndpointStatusSerializer()


class SipAliasSerializer(serializers.Serializer):
    sip = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class InstallFirmwareSerializer(serializers.Serializer):
    firmware = CustomerFilteredPrimaryKeyField(queryset=EndpointFirmware.objects.all())
    constraint = serializers.ChoiceField(choices=(('night', 'Natt'),), allow_blank=True, allow_null=True, required=False)


class ResponseSerializer(serializers.Serializer):
    response = serializers.CharField()


class EmptyBodySerializer(serializers.Serializer):
    pass


class SetPasswordsSerializer(serializers.Serializer):
    passwords = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class PasswordsResponseSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    password = serializers.CharField()


class SetCustomerDomainsSerializer(serializers.Serializer):
    domains = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class CustomerDomainsResponseSerializer(serializers.Serializer):
    domain = serializers.CharField()


class SetIpNetSerializer(serializers.Serializer):
    ip_nets = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class IpNetResponseSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    ip_net = serializers.CharField()
