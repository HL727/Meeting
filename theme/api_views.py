from rest_framework import viewsets, permissions
from rest_framework.response import Response
from customer.view_mixins import CustomerAPIMixin
from theme.models import Theme
from theme.serializers import ThemeSerializer


class ThemeSettingsViewSet(CustomerAPIMixin, viewsets.ModelViewSet):
    queryset = Theme.objects.all()
    serializer_class = ThemeSerializer

    permission_classes = [permissions.IsAdminUser | permissions.DjangoModelPermissions]

    def create(self, request, *args, **kwargs):
        return Response({'error': 'Creation is disabled'}, status=400)

    def get_object(self):
        return Theme.objects.get_or_create(pk=1)[0]
