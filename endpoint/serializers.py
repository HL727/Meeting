from io import BytesIO

from django.conf import settings
from django.db.models import Q
from django.utils.text import slugify
from django.utils.timezone import make_naive, now
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from timezone_field.rest_framework import TimeZoneSerializerField

from meeting.models import Meeting
from organization.models import OrganizationUnit

from .consts import CALLCONTROL_ACTIONS
from .ext_api.cisco_ce import CiscoCEProviderAPI
from .models import CustomerSettings, Endpoint, EndpointSIPAlias, EndpointStatus
from .view_mixins import CustomerFilteredPrimaryKeyField


class StatusListSerializer(serializers.ModelSerializer):

    class Meta:
        model = EndpointStatus
        fields = (
            'status',
            'software_version',
            'has_warnings',
        )


class EndpointListSerializer(serializers.ModelSerializer):

    status_code = serializers.IntegerField(source='status.status', read_only=True)
    status = StatusListSerializer(read_only=True)

    class Meta:
        model = Endpoint
        read_only_fields = ('status', 'serial_number', 'product_name', 'has_head_count')
        fields = (
            'id',
            'status',
            'org_unit',
            'status_code',
            'connection_type',
            'title',
            'sip',
            'h323_e164',
            'manufacturer',
            'ip',
            'product_name',
            'mac_address',
            'serial_number',
            'is_new',
            'location',
            'webex_registration',
            'pexip_registration',
            'room_capacity',
            'has_head_count'
        )


class StatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = EndpointStatus
        fields = (
            'status',
            'software_version',
            'software_release',
            'uptime',
            'presence',
            'head_count',
            'air_quality',
            'humidity',
            'temperature',
            'active_meeting',
            'has_warnings',
            'ts_last_check',
            'ts_last_online',
            'ts_last_provision',
            'ts_last_provision_document',
            'ts_last_event',
        )


class EndpointSerializer(serializers.ModelSerializer):

    status_code = serializers.IntegerField(source='status.status', read_only=True)
    status = StatusSerializer(read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email_address = serializers.CharField(read_only=True)

    organization_path = serializers.CharField(required=False, write_only=True, allow_blank=True, allow_null=True)

    sip_aliases: 'serializers.StringRelatedField[EndpointSIPAlias]' = serializers.StringRelatedField(many=True, read_only=True)

    validate_connection = serializers.BooleanField(required=False, allow_null=True, write_only=True)
    timezone = TimeZoneSerializerField(required=False, allow_null=True)
    has_password = serializers.SerializerMethodField(read_only=True)

    def get_has_password(self, obj: Endpoint) -> bool:
        return bool(obj.password and obj.password != '__try__')

    def validate(self, attrs):
        org_path = attrs.pop('organization_path', '')
        if org_path:
            customer = self.instance.customer if self.instance else self.context.get('customer')
            if not customer:
                raise ValueError('Customer not set in serializer. Make sure context is passed to serializer')
            attrs['org_unit'] = OrganizationUnit.objects.get_or_create_by_full_name(org_path, customer)[0]

        conn = {k: attrs.get(k, getattr(self.instance, k, None)) for k in ('ip', 'hostname', 'connection_type')}
        if not (conn.get('ip') or conn.get('hostname')):
            if conn.get('connection_type') != Endpoint.CONNECTION.PASSIVE:
                raise serializers.ValidationError({'connection_type': _('Endast passiv anslutning är tillåten utan ip och hostname')})
        return attrs

    def create(self, validated_data):
        validated_data.pop('validate_connection', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('validate_connection', None)
        return super().update(instance, validated_data)

    class Meta:
        model = Endpoint
        read_only_fields = ('status', 'product_name', 'has_head_count', 'timezone')

        extra_kwargs = {
                           'ip': {'allow_blank': True},
                       }
        fields = (
            'id',
            'status_code',
            'org_unit',
            'title',
            'hostname',
            'api_port',
            'sip',
            'h323',
            'h323_e164',
            'manufacturer',
            'dial_protocol',
            'ip',
            'connection_type',
            'room_capacity',
            'username',
            'proxy',
            'product_name',
            'mac_address',
            'serial_number',
            'serial_number',
            'location',
            'has_head_count',
            'hide_from_addressbook',

            'organization_path',
            'timezone',

            'email_address',
            'sip_aliases',
            'personal_system',
            'owner_email_address',

            'validate_connection',
            'webex_registration',
            'pexip_registration',
            'track_ip_changes',
            'external_manager_service',

            'is_new',

            # extra
            'status',
            'password',
            'has_password',
        )


class EndpointUpdateSerializer(serializers.ModelSerializer):
    endpoints = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)

    class Meta:
        model = Endpoint
        fields = (
            'endpoints',
            'org_unit',
            'room_capacity',
            'location',
            'password'
        )

class EndpointBulkUpdateListSerializer(serializers.ListSerializer):

    def validate(self, attrs):
        if 'customer' not in self.context:
            raise ValueError('Customer not in serializer context')

        existing_maps = self.get_existing_endpoint_maps(attrs)
        error_ids, to_update = self.handle_data(existing_maps, attrs)

        if error_ids:
            raise serializers.ValidationError({'id': error_ids})

        return to_update

    def get_existing_endpoint_maps(self, data):

        customer = self.context['customer']

        def _value_map(key, lst):
            return {x[key]: x for x in lst if x.get(key)}

        existing = Endpoint.objects.filter(customer=customer).filter(
            Q(mac_address__in=_value_map('mac_address', data).keys())
            | Q(pk__in=_value_map('id', data).keys())
            | Q(serial_number__in=_value_map('serial_number', data).keys())
        )

        def _attr_map(key, lst):
            return {getattr(x, key): x for x in lst if getattr(x, key)}

        return {
            'id': _attr_map('id', existing),
            'mac_address': _attr_map('mac_address', existing),
            'serial_number': _attr_map('serial_number', existing),
        }

    @staticmethod
    def handle_data(existing_map, attrs):
        # match id/mac/serial to existing objects
        errors = []
        result = []

        for data in attrs:
            if data.get('id'):  # invalid id breaks directly
                obj = existing_map.get(data['id'])
                if not obj:
                    errors.append(data['id'])
                    continue
            else:  # try to match
                mac = existing_map['mac_address'].get(data.get('mac_address'))
                serial = existing_map['serial_number'].get(data.get('serial_number'))

                obj = mac or serial

            result.append({
                **data,
                'instance': obj,
            })

        return errors, result

    def save_list(self, validated_data):
        endpoints = []
        for data in validated_data:
            serializer = EndpointBulkUpdateSerializer(instance=data.pop('instance'), context=self.context, partial=True)
            if serializer.instance:  # TODO create if no match?
                serializer.update(serializer.instance, data)
                endpoints.append(serializer.data)
            else:
                endpoints.append({**data, 'unmatched': True})

        return endpoints


class EndpointBulkUpdateSerializer(EndpointSerializer):
    "See EndpointBulkUpdateListSerializer for the real functionality as in Meta.list_serializer_class"
    id = serializers.IntegerField(required=False)
    unmatched = serializers.BooleanField(required=False, read_only=True)

    save_list = EndpointBulkUpdateListSerializer.save_list  # only for reference

    class Meta(EndpointSerializer.Meta):

        fields = ('id', 'unmatched') + EndpointSerializer.Meta.fields
        list_serializer_class = EndpointBulkUpdateListSerializer


class EndpointBookingsSerializer(serializers.ModelSerializer):

    endpoints = serializers.SerializerMethodField(read_only=True)

    def get_endpoints(self, obj):
        serializer = EndpointSerializer(obj.endpoints.filter(customer=obj.customer), many=True)
        return serializer.data

    class Meta:
        model = Meeting
        fields = ('title', 'ts_start', 'ts_stop', 'creator', 'sip_uri', 'endpoints')
        read_only_fields = ('sip_uri',)


class CustomerSettingsSerializer(serializers.ModelSerializer):

    passwords = serializers.ListField(write_only=True, required=False)
    domains = serializers.ListField(write_only=True, required=False)
    ip_nets = serializers.ListField(write_only=True, required=False)
    has_sip_proxy_password = serializers.BooleanField(source='sip_proxy_password', read_only=True)
    provision_domain = serializers.SerializerMethodField(read_only=True)

    def validate_ca_certificates(self, value: str):
        if value and value.strip():
            try:
                CiscoCEProviderAPI.validate_ca_certificates(value.strip(), raise_exception=True)
            except Exception:
                raise serializers.ValidationError('Could not validate certificates')
        return value

    def get_provision_domain(self, obj):
        return settings.EPM_HOSTNAME

    class Meta:
        model = CustomerSettings
        fields = (
            'id',
            'booking_time_before',
            'default_address_book',
            'default_portal_address_book',
            'default_branding_profile',
            'default_proxy',
            'dial_protocol',
            'http_feedback_slot',
            'passwords',
            'sip_proxy',
            'sip_proxy_username',
            'sip_proxy_password',
            'has_sip_proxy_password',
            'provision_domain',
            'h323_gatekeeper',
            'ip_nets',
            'domains',
            'provision_path',
            'enable_obtp',
            'external_manager_service',
            'enable_user_debug_statistics',
            'secret_key',
            'proxy_password',
            'ca_certificates',
            'night_first_hour',
            'night_last_hour',
        )
        read_only_fields = ('id',)
        extra_kwargs = {
            'sip_proxy_password': {'write_only': True},
        }


class EndpointExcelExportSerializer(serializers.Serializer):

    endpoints = serializers.ListSerializer(child=CustomerFilteredPrimaryKeyField(queryset=Endpoint.objects.all()))

    def validate(self, attrs):

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active

        ws.append([str(h) for h in [
            _('ID'),
            _('Namn'),
            _('IP'),
            _('SIP'),
            _('E-mail'),
            _('Produkt'),
            _('H323'),
            _('e.164'),
            _('Organisation'),
            _('Status'),
            _('MAC-adress'),
            _('Serienummer'),
            _('Plats'),
            _('Firmware'),
            _('Senaste online'),
        ]])

        for endpoint in attrs['endpoints']:
            ws.append([
                endpoint.id,
                endpoint.title,
                endpoint.ip,
                endpoint.sip,
                endpoint.email_address,
                endpoint.product_name,
                endpoint.h323,
                endpoint.h323_e164,
                endpoint.org_unit.full_name if endpoint.org_unit_id else '',
                endpoint.status.get_status_display(),
                endpoint.mac_address,
                endpoint.serial_number,
                endpoint.location,
                endpoint.status.software_version,
                make_naive(endpoint.status.ts_last_online) if endpoint.status.ts_last_online else '',
            ])

        fd = BytesIO()
        wb.save(fd)
        fd.seek(0)

        filename = attrs.get('filename', '').strip()
        if not filename:
            filename = 'endpoints-{}'.format(now()).replace(':', '')

        return {
            'filename': '{}.xlsx'.format(slugify(filename)),
            'fd': fd,
        }


class RunCommandSerializer(serializers.Serializer):

    command = serializers.ListField(child=serializers.CharField())
    arguments = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True),
        required=False,
        allow_empty=True,
    )
    body = serializers.CharField(allow_blank=True, required=False, allow_null=True)


class CallControlSerializer(serializers.Serializer):

    ACTION_CHOICES = tuple((x, x) for x in CALLCONTROL_ACTIONS)

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    argument = serializers.CharField(required=False, allow_blank=True)


class EndpointLegSerializer(serializers.Serializer):

    ts_start = serializers.DateTimeField()
    ts_stop = serializers.DateTimeField()
    remote = serializers.CharField()
    guid = serializers.CharField()
    call_guid = serializers.CharField(source='call__guid')


class EndpointCommandsFileSerializer(serializers.Serializer):

    valuespace = serializers.FileField()
    command = serializers.FileField()


class StatusUpSerializer(serializers.Serializer):

    error_code = serializers.IntegerField(default=200, required=False)
    warnings_code = serializers.IntegerField(default=200, required=False)


class StatusUpResponseSerializer(serializers.Serializer):

    status = serializers.ChoiceField(
        choices=(('OK', 'OK'), ('WARNING', 'WARNING'), ('ERROR', 'ERROR'))
    )
