from rest_framework import viewsets

from .models import OrganizationUnit
from .serializers import OrganizationUnitSerializer
from endpoint.view_mixins import CustomerRelationMixin


class OrganizationUnitViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = OrganizationUnitSerializer
    queryset = OrganizationUnit.objects.all().order_by('name')

    def perform_create(self, serializer):
        serializer.save(customer=self._get_customer())

