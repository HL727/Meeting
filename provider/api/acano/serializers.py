from rest_framework import serializers
from provider.exceptions import NotFound
from django.utils.translation import ugettext_lazy as _

from endpoint.view_mixins import CustomerFilteredPrimaryKeyField
from organization.models import OrganizationUnit, CoSpaceUnitRelation
from organization.serializers import OrganizationUnitMixin


class CoSpaceBaseSerializer(OrganizationUnitMixin, serializers.Serializer):
    id = serializers.CharField(required=False, read_only=True)
    name = serializers.CharField(label=_('Namn'))
    uri = serializers.CharField(label=_('URI'), required=False, allow_blank=True)
    call_id = serializers.IntegerField(label=_('Call ID'), required=False, allow_null=True)
    passcode = serializers.CharField(label=_('PIN-kod'), required=False, allow_blank=True)
    owner_jid = serializers.CharField(label=_('Ägare'), required=False, allow_blank=True, allow_null=True)

    owner_email = serializers.CharField(label=_('Koppla till e-postadress'), write_only=True,
                                        required=False, allow_blank=True,
                                        help_text=_('Fylls automatiskt i från ägare'))

    def validate_name(self, value):
        # deprecated
        if not value and self.initial_data.get('title'):
            return self.initial_data.get('title')
        return value

    def validate_owner_jid(self, value):
        from datastore.models.acano import User

        if not value:
            return ''

        if '@' not in value:
            raise serializers.ValidationError('Invalid username, should be in format user.name@example.org')

        if not User.objects.filter(provider=self.context['api'].cluster,
                                   username=value):
            try:
                self.context['api'].find_user(value)
            except NotFound:
                raise serializers.ValidationError(_('Could not find user'))
        return value

    def save_organization(self, cospace_id, validated_data=None):

        data = validated_data if validated_data is not None else self.validated_data
        organization = self.get_organization(data)

        if organization:
            CoSpaceUnitRelation.objects.get_or_create(provider_ref=cospace_id, unit=organization)
        else:
            CoSpaceUnitRelation.objects.filter(provider_ref=cospace_id).delete()


class CoSpaceSerializer(CoSpaceBaseSerializer):
    group = serializers.CharField(label=_('Koppla till grupp'), required=False, allow_blank=True)

    enable_call_profile = serializers.BooleanField(required=False)
    call_profile = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    enable_call_leg_profile = serializers.BooleanField(required=False)
    call_leg_profile = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    force_encryption = serializers.BooleanField(label=_('Kräv kryptering'), required=False, help_text=_('Ev. deltagare utan stöd kommer inte kunna ansluta'))
    enable_chat = serializers.BooleanField(label=_('Aktivera chat'), required=False, initial=True)

    lobby_pin = serializers.CharField(label=_('Separat PIN-kod för moderator'), required=False)

    stream_url = serializers.CharField(label=_('Stream URL'), required=False, allow_blank=True)
    ts_auto_remove = serializers.DateTimeField(label=_('Radera efter tidpunkt'), required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.conf import settings
        if not getattr(settings, 'ENABLE_GROUPS', False):
            self.fields.pop('group', None)

        if not getattr(settings, 'ENABLE_ORGANIZATION', False):
            self.fields.pop('org_unit', None)

        customer = self.context.get('customer')
        if customer and not (customer.enable_streaming or customer.enable_recording):
            self.fields.pop('stream_url', None)

    def get_form_data(self):
        "serialize data for use in legacy CoSpaceForm"
        data = self.validated_data.copy()
        data['title'] = data.pop('name')
        data['password'] = data.pop('passcode', '')
        data['organization_unit'] = self.get_organization(data)
        if data.get('lobby_pin'):
            data['lobby'] = True
        if data.get('call_profile'):
            data['custom_call_profile'] = True
        if data.get('call_leg_profile'):
            data['custom_call_leg_profile'] = True
        return data


class CoSpaceCreateSerializer(CoSpaceSerializer):

    call_id_generation_method = serializers.ChoiceField(choices=[('random', 'Slumpa'), ('increase', 'Nästa i nummerföljd')],
                                                    required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('call_id_generation_method'):
            if not attrs.get('call_id'):
                raise serializers.ValidationError({'generate_call_id': 'call_id_generation_method must be set if empty call_ids are specified'})

        return attrs


class CoSpaceBulkCreateSerializer(serializers.Serializer):

    cospaces = CoSpaceBaseSerializer(many=True)
    send_email = serializers.BooleanField(required=False)

    call_id_generation_method = serializers.ChoiceField(choices=[('random', 'Slumpa'), ('increase', 'Nästa i nummerföljd')],
                                                        required=False, allow_null=True, allow_blank=True)
    start_call_id = serializers.IntegerField(required=False, allow_null=True)

    organization_unit = CustomerFilteredPrimaryKeyField(queryset=OrganizationUnit.objects.all(),
                                                        allow_empty=True, allow_null=True, required=False)

    def validate(self, attrs):
        if not attrs.get('call_id_generation_method'):
            if any(not c.get('call_id') for c in attrs['cospaces']):
                raise serializers.ValidationError({'generate_call_id': 'call_id_generation_method must be set if empty call_ids are specified'})

        if not self.context.get('request') or not self.context.get('request').user.is_staff:
            attrs.pop('start_call_id', None)
        return attrs

