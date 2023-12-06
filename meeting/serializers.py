from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from endpoint.models import Endpoint
from endpoint.serializers import EndpointSerializer
from endpoint.view_mixins import CustomerFilteredPrimaryKeyField
from meeting.models import Meeting
from organization.models import OrganizationUnit


class MeetingSerializer(serializers.ModelSerializer):

    details_url = serializers.CharField(source='get_debug_details_url')
    endpoints = EndpointSerializer(many=True, read_only=True)
    was_activated = serializers.BooleanField(read_only=True, source='ts_activated')

    class Meta:
        model = Meeting
        fields = (
            'id',
            'title',
            'ts_start',
            'ts_stop',
            'ts_unbooked',
            'customer',
            'type_str',
            'creator',
            'details_url',
            'endpoints',
            'was_activated',
        )


class MeetingResponseSerializer(serializers.Serializer):
    results = MeetingSerializer(many=True)
    count = serializers.IntegerField()


class MeetingFilterSerializer(serializers.Serializer):
    """
    Port of `supporthelpers.forms.MeetingFilterForm`
    """

    title = serializers.CharField(label=_('Fritextfilter, rubrik'), required=False)
    creator = serializers.CharField(label=_('Fritextfilter, användare'), required=False)

    ts_start = serializers.DateTimeField(label=_('Tidpunkt, fr.o.m.'), required=True)
    ts_stop = serializers.DateTimeField(label=_('Tidpunkt, t.o.m.'), required=False)
    organization = CustomerFilteredPrimaryKeyField(queryset=OrganizationUnit.objects.none(), required=False)

    all_customers = serializers.BooleanField(label=_('Visa alla kunder'), initial=False, required=False)
    only_endpoints = serializers.BooleanField(label=_('Endast med endpoints'), initial=False, required=False)
    only_active = serializers.BooleanField(label=_('Endast aktiva'), initial=False, required=False)
    include_external = serializers.BooleanField(label=_('Inkludera externa möten'), initial=True, required=False)
    endpoint = CustomerFilteredPrimaryKeyField(queryset=Endpoint.objects.all(), required=False)

    def get_meetings(self):
        # TODO: Not tested
        from supporthelpers.forms import MeetingFilterForm

        return MeetingFilterForm(
            user=self.context['request'].user,
            customer=self.context['customer'],
            data=self.validated_data,
        ).get_meetings()
