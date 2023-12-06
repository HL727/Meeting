from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from address.consts import TYPES
from address.models import Group, AddressBook, Source, Item
from endpoint.view_mixins import CustomerFilteredPrimaryKeyField


class SourceSerializer(serializers.ModelSerializer):

    class Meta:
        model = Source
        fields = (
            'id',
            'title',
            'type',
            'prefix',
            'last_sync',
            'sync_errors',
        )

        read_only_fields = ('id', 'prefix', 'last_sync', 'sync_errors')


class CreateSourceSerializer(serializers.Serializer):

    title = serializers.CharField(required=False, max_length=255, allow_blank=True)
    type = serializers.ChoiceField(choices=TYPES)
    prefix = serializers.CharField(required=False, allow_blank=True, max_length=200)


class AddressBookOnUpdateMixin:

    @property
    def fields(self):
        "nested context is not available in __init__"
        fields = super().fields

        if 'address_book' not in fields:
            return fields

        context = self.context or (self.root and self.root.context) or {}
        action = context.get('view') and context['view'].action

        if action not in ('partial_update', 'update', 'create', 'bulk_create'):
            fields.pop('address_book', None)
        return fields


class GroupSerializer(AddressBookOnUpdateMixin, serializers.ModelSerializer):

    source = serializers.CharField(source='source.type', read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = Group
        read_only_fields = ('source', 'parent')
        fields = (
            'id',
            'title',
            'source',
            'is_editable',
            'parent',
            'address_book',  # variable in __init__
        )


class GroupEditSerializer(GroupSerializer):

    def validate_parent(self, group):
        if not group or not group.is_editable:
            raise serializers.ValidationError(_('Parent is not editable'))
        return group

    def validate(self, data):
        obj = self.instance
        if obj and not obj.is_editable:
            raise serializers.ValidationError(_('Group is not editable'))
        return data

    class Meta(GroupSerializer.Meta):
        read_only_fields = tuple(r for r in GroupSerializer.Meta.read_only_fields if r != 'parent')


class ItemSerializer(AddressBookOnUpdateMixin, serializers.ModelSerializer):

    address_book = serializers.IntegerField(source='group.address_book_id', read_only=True)

    group_path = serializers.CharField(write_only=True, required=False, allow_blank=True)
    is_editable = serializers.SerializerMethodField(read_only=True)

    def validate_group_path(self, value):
        value = (value or '').strip().strip('/')
        if not value:
            return ''

        if not all(v.strip() for v in value.split('/')):
            raise serializers.ValidationError('Group names must be separated by / and not empty')
        return value

    def validate_group(self, group):
        if not group.is_editable:
            raise serializers.ValidationError(_('Group is not editable'))
        return group

    def validate(self, attrs):
        if attrs.get('group_path'):
            if attrs.get('group'):
                raise serializers.ValidationError({'group': 'Only one of group and group_path can be set'})

            if not self.root or not self.root.initial_data.get('group'):
                raise serializers.ValidationError({'group_path': 'group path is only valid in bulk'})

        if not (attrs.get('group_path') or attrs.get('group')):
            if not self.root or not self.root.initial_data.get('group'):
                raise serializers.ValidationError({'group': 'group or group_path must be set'})
        return attrs

    def _populate_group(self, validated_data):
        root_group = None
        if self.root and self.root.validated_data.get('group'):
            root_group = self.root.validated_data['group']

        group_path = validated_data.pop('group_path', None)
        if group_path:
            if not root_group:
                raise serializers.ValidationError({'group_path': 'No root group found'})

            validated_data['group'], created = Group.objects.get_or_create_by_path(root_group, group_path, customer=self.context['customer'])
        elif not validated_data.get('group'):
            validated_data['group'] = root_group

    def create(self, validated_data):
        self._populate_group(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._populate_group(validated_data)
        return super().update(instance, validated_data)

    def get_is_editable(self, obj) -> bool:
        if 'manual_groups' in self.context:
            return obj.group_id in self.context['manual_groups']
        return obj.is_editable

    class Meta:
        model = Item
        fields = (
            'id',
            'type',
            'group',
            'title',
            'description',
            'sip',
            'h323',
            'h323_e164',
            'tel',
            'is_editable',
            'group_path',
            'address_book',  # variable in __init__
        )
        extra_kwargs = {
            'group': {'required': False},
        }


class ItemBulkSerializer(serializers.Serializer):

    group = CustomerFilteredPrimaryKeyField(queryset=Group.objects.all(), required=False, allow_null=True)
    items = ItemSerializer(many=True)

    def validate_group(self, value):
        items = self.initial_data.get('items') or []
        if not value and any(item and not item.get('group') for item in items):
            raise serializers.ValidationError({'group': 'group must be set if not specified with id for item'})
        return value

    def validate_empty_values(self, attrs):
        self.validate_group(attrs.get('group'))
        return super().validate_empty_values(attrs)

    def create(self, validated_data):
        items = ItemSerializer(context=self.context, data=validated_data['items'], many=True)
        items.bind('', self)
        items.is_valid()
        result = items.save()
        return {'items': result}


class AddressBookListSerializer(serializers.ModelSerializer):

    class Meta:
        model = AddressBook
        fields = (
            'id',
            'title',
            'type',
            'external_edit_url',
        )


class AddressBookSerializer(serializers.ModelSerializer):

    sources = SourceSerializer(many=True, read_only=True)
    groups = GroupSerializer(source='all_groups', many=True, read_only=True)
    soap_search_url = serializers.CharField(source='get_soap_url', read_only=True)

    class Meta:
        model = AddressBook
        fields = (
            'id',
            'title',
            'type',
            'external_url',
            'external_edit_url',
            'sources',
            'groups',
            'soap_search_url',
        )
        read_only_fields = ('is_external',)
