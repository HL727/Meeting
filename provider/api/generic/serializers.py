from rest_framework import serializers
from django.utils.translation import ugettext_lazy as _
from rest_framework.fields import empty

from organization.serializers import OrganizationUnitMixin


class GenericUserSerializer(serializers.Serializer):
    id = serializers.CharField()
    jid = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField()
    email = serializers.CharField()
    tenant = serializers.CharField(label=_('Tenant ID'))


class GenericCospaceTransform:

    pexip_transform = {
        'name': 'name',
        'stream_url': 'stream_url',
        'password': 'guest_pin',
        'moderator_password': 'pin',
    }

    acano_transform = {
        'name': 'name',
        'stream_url': 'stream_url',
        'password': 'passcode',
        'moderator_password': 'moderator_passcode',
        'call_id': 'callId',
    }

    def transform_to_api(self, api):
        if api.cluster.is_pexip:
            return self.transform_to_pexip()
        else:
            return self.transform_to_acano()

    def transform_to_generic(self, transform_map):
        result = {}
        for k1, k2 in transform_map.items():
            if k1 in self.initial_data:
                result[k2] = self.validated_data[k1]

        return result

    def transform_to_pexip(self):

        result = self.transform_to_generic(self.pexip_transform)

        if 'moderator_password' in self.initial_data:
            result['allow_guests'] = bool(self.validated_data.get('moderator_password'))

        return result

    def transform_to_acano(self):

        result = self.transform_to_generic(self.acano_transform)

        if self.initial_data.get('moderator_password'):
            result['allow_guests'] = True

        return result

    @classmethod
    def transform_from_api(cls, data, api, extend=False):
        if api.cluster.is_pexip:
            result = cls.transform_from_generic(data, cls.pexip_transform)
        else:
            result = cls.transform_from_generic(data, cls.acano_transform)
        if extend:
            result = {**data, **result}
        return result

    @classmethod
    def transform_from_generic(cls, data, transform_map):
        result = {}
        for k2, k1 in transform_map.items():
            if k1 in data:
                result[k2] = data[k1]

        return result


class GenericCoSpaceSerializer(GenericCospaceTransform, serializers.Serializer):

    id = serializers.CharField()
    cospace = serializers.CharField(required=False)
    name = serializers.CharField()
    uri = serializers.CharField(required=False)
    call_id = serializers.CharField(required=False)
    password = serializers.CharField(required=False)
    owner_email = serializers.CharField(required=False)
    stream_url = serializers.CharField(required=False)
    auto_generated = serializers.BooleanField(required=False)

    web_url = serializers.CharField(required=False)
    sip_uri = serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs['cospace']:
            attrs['cospace'] = attrs['id']
        return attrs

    @classmethod
    def load(cls, data, api, **kwargs):
        return cls(data=cls.transform_from_api(data, api), **kwargs)

    def transform(self, api=None):
        self.is_valid(raise_exception=True)
        return self.transform_from_api(self.input_data, api or self.context['api'])


class GenericCoSpaceUpdateSerializer(GenericCospaceTransform, serializers.Serializer):

    id = serializers.CharField(read_only=True)
    name = serializers.CharField()
    password = serializers.CharField(required=False)
    moderator_password = serializers.CharField(required=False)
    stream_url = serializers.CharField(required=False)

    def transform(self, api=None):
        self.is_valid(raise_exception=True)
        return self.transform_to_api(api or self.context['api'])


class GenericCallSerializer(serializers.Serializer):

    id = serializers.CharField()
    cospace = serializers.CharField()
    name = serializers.CharField()
    tenant = serializers.CharField()
    url = serializers.CharField()


class GenericCallLegSerializer(serializers.Serializer):

    id = serializers.CharField()
    cospace = serializers.CharField()
    name = serializers.CharField()
    tenant = serializers.CharField()
    url = serializers.CharField()


class GenericCreateCallLegSerializer(serializers.Serializer):

    call_id = serializers.CharField(required=False)
    local = serializers.CharField(required=False, help_text='CoSpace Id for CMS, full alias with domain for pexip')
    call_type = serializers.ChoiceField(choices=[
                                                    ('audio', 'Bara ljud'),
                                                    ('video', 'Huvudvideo + presentation'),
                                                    ('video-only', 'Bara huvudvideo'),
                                                    ('streaming', 'Streaming')
                                                ],
                                        help_text='Option to set call type for pexip',
                                        default='video', required=False, allow_null=True, allow_blank=True)

    role = serializers.CharField(required=False)
    remote = serializers.CharField()
    remote_presentation = serializers.CharField(required=False, allow_blank=True)

    system_location = serializers.CharField(
        required=False, help_text='Required for pexip', allow_blank=True
    )

    automatic_routing = serializers.BooleanField(
        required=False,
        default=True,
    )

    protocol = serializers.ChoiceField(
        required=False,
        default='sip',
        choices=[(x, x) for x in ["h323", "mssip", "sip", "rtmp", "gms", "teams"]],
    )

    def __init__(self, instance=None, data=empty, **kwargs):
        super().__init__(instance=instance, data=data, **kwargs)
        if not self.context.get('request') or not self.context.get('request').user.is_staff:
            self.fields.pop('system_location', None)

        if self.context.get('api') and not self.context['api'].cluster.is_pexip:
            self.fields.pop('system_location', None)

    def validate(self, attrs):
        if not attrs.get('call_id') and not attrs.get('local'):
            raise serializers.ValidationError({'local': 'Local alias or call id must be provided'})

        if self.context.get('api') and self.context['api'].cluster.is_pexip:
            from provider.ext_api.pexip import PexipAPI

            api: PexipAPI = self.context['api']
            default_location = api.get_settings(self.context['customer']).get_dial_out_location()
            if not attrs.get('system_location') or not self.context['request'].user.is_staff:
                attrs['system_location'] = default_location or ''

            if not attrs.get('system_location'):
                attrs.pop('system_location', None)
            if attrs.get('automatic_routing'):
                attrs.pop('protocol', None)
        elif attrs.get('remote_presentation'):
            raise serializers.ValidationError(
                {
                    'remote_presentation': 'Presentation URL is only available for Pexip RTMP-streaming'
                }
            )

        return attrs


class BulkSetOrganizationUnitSerializer(OrganizationUnitMixin):

    ids = serializers.ListField(child=serializers.CharField())


class BulkSetTenantSerializer(serializers.Serializer):

    ids = serializers.ListField(child=serializers.CharField())
    tenant = serializers.CharField(required=True, allow_blank=True)


class CallControlFlagSerializer(serializers.Serializer):

    value = serializers.BooleanField()
