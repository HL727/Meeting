from rest_framework import viewsets, permissions
from rest_framework.decorators import action

from endpoint.view_mixins import CustomerRelationMixin
from .serializers import MSGraphCredentialsSerializer
from .models import MSGraphCredentials


class MSGraphCredentialsViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = MSGraphCredentials.objects.all()
    serializer_class = MSGraphCredentialsSerializer

    def get_queryset(self):
        return self.queryset.filter()  # dont filter to customer. use filter to clear cache

    @action(detail=True, methods=['POST'])
    def sync(self, request, pk=None):
        from msgraph.tasks import poll_msgraph_single
        poll_msgraph_single(self.get_object())
        return self.retrieve(request, pk=pk)
