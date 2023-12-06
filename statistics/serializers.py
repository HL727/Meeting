from typing import Type, Mapping, Any

from django.utils.translation import gettext_lazy as _
from django.forms import Form
from rest_framework import serializers

from endpoint.models import Endpoint
from endpoint.view_mixins import CustomerFilteredPrimaryKeyField

from room_analytics.forms import HeadCountStatsForm

from .forms import StatsForm
from .models import Call, Leg, Server


class CallSerializer(serializers.ModelSerializer):

    debug_url = serializers.SerializerMethodField()

    def get_debug_url(self, obj):
        return Call.get_debug_url(obj)

    class Meta:
        model = Call
        fields = (
            'id',
            'guid',
            'cospace',
            'ou',
            'ts_start',
            'ts_stop',
            'leg_count',
            'duration',
            'total_duration',
            'debug_url',
        )


class LegModelSerializer(serializers.ModelSerializer):

    cospace = serializers.CharField(source='call.cospace')
    debug_url = serializers.CharField(source='get_debug_url')

    class Meta:
        model = Leg
        fields = (
            'target',
            'local',
            'remote',
            'guid',
            'cospace',
            'ou',
            'org_unit',
            'ts_start',
            'ts_stop',
            'is_guest',
            'debug_url',
        )


class LegSerializer(LegModelSerializer):

    cospace = serializers.CharField(source='call__cospace')
    debug_url = serializers.SerializerMethodField()
    org_unit = serializers.IntegerField()

    def get_debug_url(self, obj):
        return Leg.get_debug_url(obj)


class PlotlySerializer(serializers.Serializer):

    data = serializers.ListField(child=serializers.DictField())
    layout = serializers.DictField()


class CallStatisticsSettingsChoicesSerializer(serializers.Serializer):

    tenant = serializers.ListField(child=serializers.ListField(child=serializers.CharField()))
    server = serializers.ListField(child=serializers.DictField(child=serializers.CharField()))


class CallStatisticsSettingsSerializer(serializers.Serializer):

    choices = CallStatisticsSettingsChoicesSerializer()


class CallStatisticsGraphsSerializer(serializers.Serializer):

    per_day = PlotlySerializer()
    sametime = PlotlySerializer()


class CallStatisticsDebugResponseSerializer(serializers.Serializer):
    calls = CallSerializer(many=True)
    legs = LegSerializer(many=True)
    loaded = serializers.BooleanField()
    has_data = serializers.BooleanField()
    excel_debug_report_url = serializers.CharField(required=False)


class CallStatisticsDataSerializer(serializers.Serializer):

    calls = CallSerializer(many=True, required=False)
    legs = LegSerializer(many=True, required=False)
    errors = serializers.DictField(required=False)
    summary = serializers.DictField()
    graphs = serializers.DictField()
    defer_load = serializers.BooleanField()
    loaded = serializers.BooleanField()
    has_data = serializers.BooleanField()

    pdf_report_url = serializers.CharField(required=False)
    excel_report_url = serializers.CharField(required=False)
    excel_debug_report_url = serializers.CharField(required=False)

    choices = CallStatisticsSettingsChoicesSerializer(required=False)


class StatisticsServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Server
        exclude = ()


class ReparseStatisticsSerializer(serializers.Serializer):

    days = serializers.IntegerField(min_value=1, default=90, required=False)


class RematchStatisticsSerializer(serializers.Serializer):

    days = serializers.IntegerField(min_value=1, default=90, required=False)
    force_rematch = serializers.BooleanField(
        default=False,
        required=False,
        help_text='Re-match calls/legs that already have been matched to a customer',
    )


class FormValidatorMixin:

    default_form_class: Type[Form] = HeadCountStatsForm
    form: Form = None
    context: Mapping[str, Any]

    def validate(self, attrs):

        form_class = self.context.get('form_class') or self.default_form_class

        form = form_class(data=attrs,
                          customer=self.context['customer'],
                          user=self.context['request'].user
                          )

        self.form = form

        if not form.is_valid():
            raise serializers.ValidationError({k: list(v) for k, v in form.errors.items()})

        return attrs


class CallStatisticsSerializer(FormValidatorMixin, serializers.Serializer):

    default_form_class = StatsForm

    ts_start = serializers.DateTimeField()
    ts_stop = serializers.DateTimeField()
    ou = serializers.CharField(required=False)
    tenant = serializers.CharField(required=False)
    cospace = serializers.CharField(required=False)
    member = serializers.CharField(required=False)
    server = serializers.CharField(required=False)
    protocol = serializers.ChoiceField(choices=Leg.PROTOCOLS, required=False)
    multitenant = serializers.BooleanField(required=False)
    only_gateway = serializers.BooleanField(required=False)
    organization = serializers.IntegerField(required=False)
    debug = serializers.BooleanField(initial=False, required=False)
    endpoints = CustomerFilteredPrimaryKeyField(queryset=Endpoint.objects.all(), many=True)


class HeadCountStatisticsSerializer(FormValidatorMixin, serializers.Serializer):

    default_form_class = HeadCountStatsForm

    ts_start = serializers.DateTimeField()
    ts_stop = serializers.DateTimeField()

    only_hours = serializers.CharField(label=_('Endast timmar (mån=1, sön=7)'), initial='7-17', required=False)
    only_days = serializers.CharField(label=_('Endast dagar (mån=1, sön=7)'), initial='1-5', required=False)
    as_percent = serializers.BooleanField(label=_('Visa som procent av rumskapacitet'), required=False)
    ignore_empty = serializers.BooleanField(label=_('Ignorera tider med tomt rum'), required=False)
    fill_gaps = serializers.BooleanField(label=_('Fyll saknade tider med 0-värden'), required=False)

    organization = serializers.IntegerField(required=False)
    endpoints = CustomerFilteredPrimaryKeyField(queryset=Endpoint.objects.all(), many=True, required=False)


class HeadCountStatisticsGraphsSerializer(serializers.Serializer):

    empty = serializers.BooleanField(required=False)
    per_hour = serializers.DictField()
    per_day = serializers.DictField()
    per_date = serializers.DictField()
    now = serializers.DictField()


class HeadCountStatisticsResponseSerializer(serializers.Serializer):
    graphs = HeadCountStatisticsGraphsSerializer()
    loaded = serializers.BooleanField()
    has_data = serializers.BooleanField()
