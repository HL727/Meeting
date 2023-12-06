from rest_framework import serializers

from endpoint.consts import TASKSTATUS
from endpoint.models import Endpoint
from endpoint.view_mixins import CustomerFilteredPrimaryKeyField
from endpoint_provision.models import EndpointProvision


class EndpointTaskListFilterSerializer(serializers.Serializer):
    endpoint = CustomerFilteredPrimaryKeyField(queryset=Endpoint.objects.all(), required=False, allow_empty=True, allow_null=True)
    provision = CustomerFilteredPrimaryKeyField(queryset=EndpointProvision.objects.all(), required=False, allow_empty=True, allow_null=True)
    status = serializers.ChoiceField(choices=tuple((ts.value, ts.name) for ts in TASKSTATUS), required=False, allow_blank=True, allow_null=True)
    changed_since = serializers.DateTimeField(required=False, allow_null=True)
    order_by = serializers.ChoiceField(choices=('created', 'change'), required=False, allow_blank=True)
