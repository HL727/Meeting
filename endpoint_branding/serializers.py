from django.utils.translation import gettext_lazy as _
from drf_extra_fields.fields import HybridImageField
from rest_framework import serializers

from endpoint.view_mixins import CustomerRelationMixin
from endpoint_branding.models import EndpointBrandingFile, EndpointBrandingProfile


class BrandingFileSerializer(CustomerRelationMixin, serializers.ModelSerializer):

    file = HybridImageField(label=_('Base64-encoded image'), allow_empty_file=True, use_url=True)

    class Meta:
        model = EndpointBrandingFile
        fields = ('type', 'file', 'use_standard')


class BrandingProfileSerializer(CustomerRelationMixin, serializers.ModelSerializer):

    files = BrandingFileSerializer(many=True, required=False)

    def create(self, validated_data):
        files = validated_data.pop('files', ())

        instance = super().create(validated_data)

        self._save_files(instance, files)
        return instance

    def update(self, instance, validated_data):
        files = validated_data.pop('files', ())

        super().update(instance, validated_data)
        self._save_files(instance, files)
        return instance

    def _save_files(self, instance, files):

        for f in files:
            file_kwargs = {}
            if f.get('use_standard'):
                file_kwargs = {'file': None}
            elif f['file']:
                file_kwargs = {'file': f['file']}

            obj, created = EndpointBrandingFile.objects.update_or_create(profile=instance, type=f['type'], customer=instance.customer,
                                                            defaults=dict(use_standard=bool(f.get('use_standard')), **file_kwargs))

            if f['file']:
                obj.file.save(f['file'].name, f['file'])
                obj.save()

    class Meta:
        model = EndpointBrandingProfile
        fields = ('id', 'name', 'files')

