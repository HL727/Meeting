import json
import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from address.models import AddressBook
from endpoint.docs import EndpointConfigurationValueSerializer, EndpointDialInfoSerializer
from endpoint.models import Endpoint
from endpoint.serializers import RunCommandSerializer
from endpoint.view_mixins import (
    CustomerFilteredPrimaryKeyField,
    CustomerOrGlobalFilteredPrimaryKeyField,
)
from endpoint_branding.models import EndpointBrandingProfile
from endpoint_provision.models import EndpointFirmware, EndpointTask, EndpointTemplate
from roomcontrol.models import RoomControl, RoomControlTemplate
from shared.utils import prettify_xml


class EndpointFirmwareSerializer(serializers.ModelSerializer):

    model = serializers.CharField(label=EndpointFirmware._meta.get_field('model').verbose_name, required=False)
    models = serializers.ListField(label=EndpointFirmware._meta.get_field('model').verbose_name,
                                   required=False, child=serializers.CharField())
    is_global = serializers.BooleanField(label=_('Är global'), required=False)

    def validate(self, attrs):
        models = attrs.pop('models', None) or []  # allow multiple models for create new
        if self.context.get('view') and self.context['view'].action == 'create':
            attrs['models'] = models
        if not models and not attrs.get('model'):
            raise serializers.ValidationError({'model': 'model or models must be provided', 'models': 'model or models must be provided'})
        if not attrs.get('model') and models:
            attrs['model'] = models.pop(0)

        if not self.context.get('request') or not self.context['request'].user.is_staff:
            attrs.pop('is_global', None)

        return attrs

    def create(self, validated_data):

        models = validated_data.pop('models', None) or []
        obj = super().create(validated_data)

        if models:  # create copy
            obj2 = EndpointFirmware.objects.get(pk=obj.pk)
            for model in models:
                obj2.pk = None
                obj2.model = model
                obj2.save()

        return obj

    def update(self, instance, validated_data):
        validated_data.pop('models', None)
        return super().update(instance, validated_data)

    class Meta:
        model = EndpointFirmware
        fields = (
            'id',
            'title',
            'orig_file_name',
            'is_global',
            'manufacturer',
            'model',
            'models',
            'version',
            'ts_created',
            'file',
        )
        read_only_fields = ('id', 'orig_file_name', 'ts_created')


class EndpointFirmwareCopySerializer(serializers.Serializer):

    models = serializers.ListField(
        label=EndpointFirmware._meta.get_field('model').verbose_name, child=serializers.CharField()
    )
    is_global = serializers.BooleanField(label=_('Är global'), required=False)

    def validate(self, attrs):

        if not self.context.get('request') or not self.context['request'].user.is_staff:
            attrs.pop('is_global', None)

        return attrs


class EndpointTaskListSerializer(serializers.ModelSerializer):

    endpoint_title = serializers.SerializerMethodField(read_only=True)
    user = serializers.CharField(source='provision.user')

    def get_endpoint_title(self, obj):
        return '--deleted--' if obj.endpoint is None else str(obj.endpoint)

    class Meta:
        model = EndpointTask
        fields = (
            'id',
            'provision',
            'status',
            'error',
            'endpoint',
            'endpoint_title',
            'action',
            'ts_created',
            'ts_last_attempt',
            'ts_completed',
            'ts_schedule_attempt',
            'tries',
            'user',
        )


class EndpointTaskSerializer(EndpointTaskListSerializer):

    provision_content = serializers.SerializerMethodField()

    def get_provision_content(self, obj: EndpointTask):
        if not obj.endpoint:
            return 'Endpoint deleted'

        if obj.endpoint.is_cisco:
            return self.get_cisco_provision_content(obj)
        elif obj.endpoint:
            return self.get_poly_provision_content(obj)
        else:
            return 'Unsupported endpoint'

    def get_cisco_provision_content(self, obj: EndpointTask):

        from endpoint_provision.views_tms_provision import get_endpoint_tms_response_context

        context = get_endpoint_tms_response_context(
            obj.endpoint,
            [obj],
            is_initial=False,
            constraint_ts=obj.ts_completed,
            ignore_constraints=True,
            allow_chained_service=False,
        )

        result = []
        if context.get('Configuration'):
            result.append('<Configuration>{}</Configuration>'.format(context.get('Configuration') or '').replace(' internal="true" xmlns=""', '').replace(' item="1">', '>'))
        if context.get('Command'):
            result.append('<Commands>{}</Commands>'.format(context.get('Command') or ''))
        if context.get('Software'):
            result.append('<Software>{}</Software>'.format(context.get('Software') or ''))

        if not result:
            return '<Empty />'

        xml = re.sub(
            r'<([A-z]*Pass(word|phrase))>\s*[^<]+</\1>', r'<\1>******</\1>', '\n'.join(result)
        )

        return prettify_xml('<ProvisionData>{}</ProvisionData>'.format(xml))

    def get_poly_provision_content(self, obj: EndpointTask):

        from endpoint_provision.views_poly_provision import PolyPassiveProvisionBase

        xml = PolyPassiveProvisionBase.get_endpoint_instance(
            endpoint=obj.endpoint, tasks=[self]
        ).get_response_content(include_default_configuration=False)

        xml = re.sub(
            r' ([A-z]*pass(word|phrase))="[^"]+"',
            r'\1="******"',
            xml,
        )

        return xml

    class Meta(EndpointTaskListSerializer.Meta):
        fields = EndpointTaskListSerializer.Meta.fields + ('provision_content', 'result')


class SerializedDictListField(serializers.ListField):

    def to_representation(self, value):
        if isinstance(value, str):
            if not value:
                return []
            value = json.loads(value)
        return super().to_representation(value)

    def to_internal_value(self, data):
        return data


class EndpointTemplateSerializer(serializers.ModelSerializer):

    settings = SerializedDictListField(required=False)
    commands = SerializedDictListField(required=False)

    def validate(self, attrs):
        if int(bool(attrs.get('settings'))) + int(bool(attrs.get('commands'))) != 1:
            raise serializers.ValidationError(
                {'settings': 'one of settings or commands must be provided'}
            )
        return attrs

    class Meta:
        model = EndpointTemplate
        fields = (
            'id',
            'name',
            'manufacturer',
            'model',
            'settings',
            'commands',
            'ts_created',
        )
        read_only_fields = ('id', 'ts_created')


class ProvisionBodySerializer(serializers.Serializer):

    endpoints = CustomerFilteredPrimaryKeyField(queryset=Endpoint.objects.all(), many=True)

    constraint = serializers.ChoiceField(choices=(('night', 'Natt'),), allow_blank=True, allow_null=True, required=False)
    addressbook = CustomerFilteredPrimaryKeyField(queryset=AddressBook.objects.all(), required=False, allow_null=True)
    firmware = CustomerOrGlobalFilteredPrimaryKeyField(queryset=EndpointFirmware.objects.all(), required=False, allow_null=True)
    statistics = serializers.BooleanField(required=False, allow_null=True)
    passive = serializers.BooleanField(required=False, allow_null=True)
    clear_room_controls = serializers.BooleanField(required=False, allow_null=True)
    room_controls_delete_operation = serializers.BooleanField(required=False, allow_null=True)
    room_controls = CustomerFilteredPrimaryKeyField(queryset=RoomControl.objects.all(), many=True, required=False, allow_null=True)
    room_control_templates = CustomerFilteredPrimaryKeyField(queryset=RoomControlTemplate.objects.all(), many=True, required=False, allow_null=True)
    configuration = EndpointConfigurationValueSerializer(allow_null=True, many=True, required=False)
    commands = RunCommandSerializer(allow_null=True, many=True, required=False)
    branding_profile = CustomerFilteredPrimaryKeyField(queryset=EndpointBrandingProfile.objects.all(), required=False, allow_null=True)
    head_count = serializers.BooleanField(required=False, allow_null=True)
    presence = serializers.BooleanField(required=False, allow_null=True)
    allow_personal_room_analytics = serializers.BooleanField(required=False)
    dial_info = EndpointDialInfoSerializer(required=False, allow_null=True)
    set_password = serializers.BooleanField(required=False, allow_null=True)
    password = serializers.CharField(required=False, allow_null=True)
    current_password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    standard_password = serializers.BooleanField(required=False, allow_null=True)
    events = serializers.BooleanField(required=False, allow_null=True)
    xapi_text = serializers.CharField(required=False, allow_null=True)
    repeat = serializers.BooleanField(required=False, allow_null=True)
    schedule = serializers.DateTimeField(required=False, allow_null=True)
