from rest_framework import viewsets, permissions

from endpoint.view_mixins import CustomerRelationMixin
from .serializers import CalendarSerializer
from calendar_invite.models import Calendar


class CalendarViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.GET.get('endpoint'):
            queryset = queryset.filter(endpoint=self.request.GET.get('endpoint'))
        return queryset
