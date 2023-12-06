import enum

from rest_framework import serializers
from rest_framework.fields import empty

from datastore.models.pexip import EndUser
from endpoint.view_mixins import CustomerFilteredPrimaryKeyField
from organization.models import OrganizationUnit
from organization.serializers import OrganizationUnitMixin
from django.utils.translation import gettext_lazy as _

from provider.api.pexip.consts import GuestLayout, HostLayout


class ConferenceAliasUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    alias = serializers.CharField()
    active = serializers.BooleanField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        "first check for duplicates. may still happen during api request"
        from datastore.models.pexip import Conference

        alias = attrs.get('alias') or ''
        if alias and attrs.get('active'):
            conference = self.context.get('conference')
            alias_match = Conference.objects.match({'local_alias': alias})
            if alias_match and (not conference or alias_match.cid != conference.cid):
                raise serializers.ValidationError({'alias': 'Alias already exists'})

        if alias:
            attrs = self.validate_domain(attrs)
        return attrs

    def validate_domain(self, attrs):
        alias = attrs.get('alias') or ''

        if alias.isdigit():
            return attrs

        c_settings = self.context['cluster'].get_cluster_settings(self.context['customer'])
        main_domain = c_settings.get_main_domain()

        valid_domains = {main_domain, *c_settings.get_additional_domains()}

        user_is_staff = self.context['request'].user.is_staff

        changed_alias = True

        if attrs.get('id'):
            from datastore.models.pexip import ConferenceAlias
            try:
                existing = ConferenceAlias.objects.filter(provider=self.context['cluster'], aid=attrs['id'], is_active=True)[0].to_dict()
            except IndexError:
                changed_alias = True
            else:
                changed_alias = (existing['alias'], existing['id']) != (attrs.get('alias'), attrs.get('id'))

        if '@' in alias:
            domain = alias.split('@', 1)[1]
            if domain not in valid_domains and not user_is_staff:
                if changed_alias:
                    raise serializers.ValidationError('Domain must be {}'.format(main_domain))
            attrs['alias'] = alias.rstrip('@')  # staff may use "text@" for empty domain
        elif main_domain and changed_alias:
            attrs['alias'] = '{}@{}'.format(alias, main_domain)

        return attrs


class ConferenceAliasSerializer(ConferenceAliasUpdateSerializer):
    id = serializers.IntegerField(required=False, read_only=True)
    creation_time = serializers.DateTimeField(required=False, read_only=True)


class ConferenceSerializer(OrganizationUnitMixin, serializers.Serializer):
    id = serializers.IntegerField(required=False, read_only=True)
    service_type = serializers.CharField()

    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)

    pin = serializers.CharField(required=False, allow_blank=True)

    allow_guests = serializers.BooleanField(required=False)
    guest_pin = serializers.CharField(required=False, allow_blank=True)
    primary_owner_email_address = serializers.EmailField(required=False, allow_blank=True)

    web_url = serializers.CharField(read_only=True, required=False)

    tenant = serializers.CharField(required=False, allow_blank=True)  # TODO read only?

    call_id = serializers.IntegerField(required=False, allow_null=True)

    ivr_theme = serializers.CharField(required=False, allow_blank=True)

    guest_view = serializers.ChoiceField(
        choices=[(c.name, c.value) for c in GuestLayout],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    host_view = serializers.ChoiceField(
        choices=[(c.name, c.value) for c in HostLayout],
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    aliases: ConferenceAliasSerializer = ConferenceAliasSerializer(many=True, required=False)

    call_id_generation_method = serializers.ChoiceField(choices=[('random', 'Slumpa'), ('increase', 'Nästa i nummerföljd')],
                                                        required=False, allow_null=True, allow_blank=True, write_only=True)

    def __init__(self, instance=None, data=empty, **kwargs):
        super().__init__(instance=instance, data=data, **kwargs)
        if not self.context.get('request') or not self.context.get('request').user.is_staff:
            self.fields.pop('ivr_theme', None)

    def get_api_data(self):
        return self.validated_data

    def validate_call_id(self, value):
        if not value:
            return None

        if not self.context.get('request') or not self.context.get('request').user.is_staff:
            pass

        return value

    def validate_name(self, name):
        "first check for duplicates. may still happen during api request"
        from datastore.models.pexip import Conference

        conference = self.context.get('conference')
        existing = Conference.objects.match(name, cluster=self.context['cluster'])

        if existing and (not conference or existing.cid != conference.cid):
            raise serializers.ValidationError(_('Name already exists'))
        return name

    def validate_tenant(self, value):
        if not value:
            return
        from customer.models import Customer

        customer = Customer.objects.find_customer(
            pexip_tenant_id=value, cluster=self.context.get('cluster')
        )
        if not customer:
            raise serializers.ValidationError('Invalid tenant id')
        return value

    def validate(self, attrs):
        if attrs.get('guest_pin') and not attrs.get('pin'):
            raise serializers.ValidationError({'pin': 'PIN-kod för host måste fyllas i ifall gäst-PIN är aktiverad'})

        from provider.ext_api.pexip import PexipAPI

        api: PexipAPI = self.context['api']

        default_ivr_theme = api.get_settings(self.context['customer']).get_theme_profile()
        if not attrs.get('ivr_theme') or not self.context['request'].user.is_staff:
            attrs['ivr_theme'] = default_ivr_theme or ''

        if not attrs.get('ivr_theme'):
            attrs.pop('ivr_theme', None)

        return attrs

    def save_organization(self, conference_id, validated_data=None):

        data = validated_data if validated_data is not None else self.validated_data
        organization = self.get_organization(data)

        from provider.models.pexip import PexipSpace
        if organization:
            PexipSpace.objects.update_or_create(cluster=self.context['cluster'], external_id=conference_id,
                                                defaults={'organization_unit': organization})
        else:
            PexipSpace.objects.filter(cluster=self.context['cluster'], external_id=conference_id).update(organization_unit=None)

        return organization


class ConferenceBulkCreateSerializer(serializers.Serializer):

    conferences = ConferenceSerializer(many=True)
    send_email = serializers.BooleanField(required=False)
    service_type = serializers.CharField(required=False)

    call_id_generation_method = serializers.ChoiceField(choices=[('random', 'Slumpa'), ('increase', 'Nästa i nummerföljd')],
                                               required=False, allow_null=True, allow_blank=True)
    start_call_id = serializers.IntegerField(required=False, allow_null=True)

    organization_unit = CustomerFilteredPrimaryKeyField(queryset=OrganizationUnit.objects.all(),
                                                        allow_empty=True, allow_null=True, required=False)

    def validate(self, attrs):
        if not attrs.get('call_id_generation_method'):
            if any(not c.get('alias') for c in attrs['conferences']):
                raise serializers.ValidationError({'generate_call_id': 'call_id_generation_method must be set if empty aliases are specified'})

        if not self.context.get('request') or not self.context.get('request').user.is_staff:
            attrs.pop('start_call_id', None)

        return attrs


class ConferenceUpdateSerializer(ConferenceSerializer):
    aliases = ConferenceAliasUpdateSerializer(many=True, required=False)

    def get_api_data(self):
       result = {**self.validated_data}
       result.pop('aliases', None)  # update using separate methods
       result.pop('organization_unit', None)  # update using separate methods
       result.pop('organization_path', None)  # update using separate methods
       return result


class EndUserSerializer(serializers.ModelSerializer):

    id = serializers.IntegerField(source='uid')
    email = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    tenant = serializers.SerializerMethodField()

    organization_unit = CustomerFilteredPrimaryKeyField(queryset=OrganizationUnit.objects.all(),
                                                        allow_empty=True, allow_null=True, required=False)

    def get_tenant(self, obj):
        return obj.tenant.tid if obj.tenant else ''

    class Meta:
        model = EndUser
        fields = ('id', 'email', 'name', 'primary_email_address', 'uuid', 'sync_tag', 'avatar_url',
                  'first_name', 'last_name', 'display_name', 'description', 'tenant', 'organization_unit')


class UpdateEndUserSerializer(serializers.Serializer):

    tenant = serializers.CharField(allow_blank=True)
