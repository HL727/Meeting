from rest_framework import serializers

from endpoint.view_mixins import CustomerFilteredPrimaryKeyField
from .models import OrganizationUnit


class OrganizationUnitSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrganizationUnit
        fields = (
            'id',
            'name',
            'parent',
        )


class OrganizationUnitMixin(serializers.Serializer):

    organization_path = serializers.CharField(write_only=True, required=False, allow_blank=True)
    organization_unit = CustomerFilteredPrimaryKeyField(queryset=OrganizationUnit.objects.all(),
                                                        allow_empty=True, allow_null=True, required=False)

    def validate_organization_path(self, value):
        value = (value or '').strip().strip('/')
        if not value:
            return ''

        if not all(v.strip() for v in value.split('/')):
            raise serializers.ValidationError('Organization names must be separated by / and not empty')
        return value

    def validate(self, attrs):
        if attrs.get('organization_path'):
            if attrs.get('organization_unit'):
                raise serializers.ValidationError({'organization_unit': 'Only one of organization and organization_path can be set'})

        return attrs

    def _populate_organization(self, validated_data):
        root_organization = None
        if self.root and self.root.validated_data.get('organization_unit'):
            root_organization = self.root.validated_data['organization_unit']

        organization_path = validated_data.pop('organization_path', None)
        if organization_path:
            validated_data['organization_unit'], created = OrganizationUnit.objects.get_or_create_by_full_name(organization_path,
                                                                                                               customer=self.context['customer'],
                                                                                                               parent=root_organization)
        elif not validated_data.get('organization_unit'):
            validated_data['organization_unit'] = root_organization

    def get_organization(self, validated_data=None):
        data = (validated_data if validated_data is not None else self.validated_data).copy()
        self._populate_organization(data)
        return data.get('organization_unit')

    def create(self, validated_data):
        self._populate_organization(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._populate_organization(validated_data)
        return super().update(instance, validated_data)


class OrganizationUnitCreateSerializer(OrganizationUnitMixin):
    pass
