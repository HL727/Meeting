from rest_framework import serializers

from address.models import AddressBook, Source
from endpoint.view_mixins import CustomerFilteredPrimaryKeyField


class ProviderResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class ProvidersResponseSerializer(serializers.Serializer):

    cms = ProviderResponseSerializer(many=True)
    vcs = ProviderResponseSerializer(many=True)
    manual = ProviderResponseSerializer(many=True)


class ErrorSerializer(serializers.Serializer):
    status = serializers.CharField()
    errors = serializers.DictField(child=serializers.CharField())


class AddressBookIdSerializer(serializers.Serializer):
    id = CustomerFilteredPrimaryKeyField(queryset=AddressBook.objects.all())


class SourceIdSerializer(serializers.Serializer):
    id = CustomerFilteredPrimaryKeyField(queryset=Source.objects.all(),
                                         customer_through_field='address_book__customer')


class CopySerializer(serializers.Serializer):
    new_title = serializers.CharField(required=False, allow_blank=True)
    copy_editable_items = serializers.BooleanField(required=False)
