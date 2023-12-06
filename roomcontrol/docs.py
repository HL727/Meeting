from rest_framework import serializers

from endpoint.view_mixins import CustomerFilteredPrimaryKeyField
from roomcontrol.models import RoomControlFile


class PackageSerializer(serializers.Serializer):
    f = serializers.CharField(required=False, allow_blank=True)
    c = serializers.CharField(required=False, allow_blank=True)
    t = serializers.CharField(required=False, allow_blank=True)
    e = serializers.CharField(required=False, allow_blank=True)

    k = serializers.CharField()

class ExportUrlResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    url = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    error = serializers.CharField()


class ExportRoomControlSerializer(serializers.Serializer):
    files = CustomerFilteredPrimaryKeyField(queryset=RoomControlFile.objects.all(), many=True)


class AddFilesSerializer(serializers.Serializer):
    files = serializers.DictField(child=serializers.FileField())

