from rest_framework import viewsets, permissions

from api_key.models import OAuthCredential
from api_key.serializers import OAuthCredentialSerializer
from endpoint.view_mixins import CustomerRelationMixin


class OAuthCredentialViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = OAuthCredential.objects.all()
    serializer_class = OAuthCredentialSerializer

    def get_queryset(self):
        return self.queryset.filter()  # dont filter to customer. use filter to clear cache
