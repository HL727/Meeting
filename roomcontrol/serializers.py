from rest_framework import serializers

from endpoint.view_mixins import CustomerFilteredPrimaryKeyField
from .models import RoomControl, RoomControlFile, RoomControlTemplate


class RoomControlFileSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = RoomControlFile
        fields = (
            'id',
            'name'
        )


class RoomControlTemplateInlineSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = RoomControlTemplate
        fields = (
            'id',
            'title',
            'description',
            'controls',
            'ts_created'
        )
        read_only_fields = ('id', 'ts_created')


class RoomControlSerializer(serializers.HyperlinkedModelSerializer):
    files = RoomControlFileSerializer(many=True)
    url_export = serializers.SerializerMethodField()
    templates = RoomControlTemplateInlineSerializer(many=True, required=False)
    endpoints = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    def get_url_export(self, control):
        return control.get_export_url()

    class Meta:
        model = RoomControl
        view_name = 'roomcontrol-detail'
        fields = (
            'id',
            'title',
            'description',
            'ts_created',
            'url',
            'url_export',
            'files',
            'endpoints',
            'templates'
        )
        read_only_fields = ('id', 'ts_created', 'url', 'url_export')


class RoomControlUpdateSerializer(RoomControlSerializer):

    files = serializers.ListField(child=serializers.FileField())

    def create(self, validated_data):
        files = validated_data.pop('files', None) or []

        instance = super().create(validated_data)
        for filename, content in files:
            instance.add_file(filename, content)

        instance.export_zip_all()
        return instance

    def update(self, instance, validated_data):
        files = validated_data.pop('files', None)

        instance = super().update(instance, validated_data)

        if files is not None:
            RoomControlFile.objects.filter(control=instance).delete()
            for filename, content in files:
                instance.add_file(filename, content)

            instance.export_zip_all()
        return instance

    def validate_files(self, value):
        try:
            return RoomControlFile.objects.validate_files(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class RoomControlAddFilesSerializer(serializers.Serializer):

    files = serializers.ListField(child=serializers.FileField())

    def create(self, validated_data):
        files = validated_data.pop('files', None) or []

        for filename, content in files:
            self.instance.add_file(filename, content)
        self.instance.export_zip_all()
        return self.instance

    def update(self, instance, validated_data):
        files = validated_data.pop('files', None) or []

        for filename, content in files:
            instance.add_file(filename, content)
        instance.export_zip_all()
        return self.instance

    def validate_files(self, value):
        try:
            return RoomControlFile.objects.validate_files(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class RoomControlExportUrlSerializer(serializers.Serializer):
    controls = CustomerFilteredPrimaryKeyField(queryset=RoomControl.objects.all(), many=True)


class RoomControlTemplateSerializer(serializers.HyperlinkedModelSerializer):

    # controls = RoomControlSerializer(many=True, required=False)
    controls = CustomerFilteredPrimaryKeyField(queryset=RoomControl.objects.all(), many=True)
    endpoints = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    url_export = serializers.SerializerMethodField()

    def get_url_export(self, control):
        return control.get_export_url()

    class Meta:
        model = RoomControlTemplate
        view_name = 'roomcontrol-template-detail'
        fields = (
            'id',
            'title',
            'description',
            'url_export',
            'controls',
            'endpoints',
            'ts_created'
        )
        read_only_fields = ('id', 'ts_created', 'url_export', 'controls')


class RoomControlTemplateCreateSerializer(RoomControlTemplateSerializer):
    controls = serializers.ListField(child=serializers.IntegerField(), write_only=True)
