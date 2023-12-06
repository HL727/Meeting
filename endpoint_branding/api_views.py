from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from endpoint.view_mixins import CustomerRelationMixin
from endpoint_branding.models import EndpointBrandingFile, EndpointBrandingProfile
from endpoint_branding.serializers import BrandingFileSerializer, BrandingProfileSerializer


class BrandingProfileViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = BrandingProfileSerializer
    queryset = EndpointBrandingProfile.objects.all()

    @action(methods=['GET'], detail=False)
    def types(self, request):
        labels = EndpointBrandingFile.BrandingType.labels
        help_texts = EndpointBrandingFile.BrandingType.help_texts
        return Response(
            [
                {
                    'id': v.value,
                    'name': v.name,
                    'label': labels.get(v.value),
                    'help_text': help_texts.get(v.value),
                }
                for v in EndpointBrandingFile.BrandingType
            ]
        )

    class Meta:
        model = EndpointBrandingProfile


class BrandingFileViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = BrandingFileSerializer

    queryset = EndpointBrandingFile.objects.all()

    class Meta:
        model = EndpointBrandingFile
