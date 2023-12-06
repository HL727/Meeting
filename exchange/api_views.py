from rest_framework import viewsets, permissions
from rest_framework.decorators import action

from endpoint.view_mixins import CustomerRelationMixin
from .serializers import EWSCredentialsSerializer
from .models import EWSCredentials


class EWSCredentialsViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = EWSCredentials.objects.all()
    serializer_class = EWSCredentialsSerializer

    def get_queryset(self):
        return self.queryset.filter()  # dont filter to customer. use filter to clear cache

    @action(detail=True, methods=['POST'])
    def sync(self, request, pk=None):
        from exchange.tasks import poll_ews_single
        poll_ews_single(self.get_object())
        return self.retrieve(request, pk=pk)
