from rest_framework import viewsets, permissions

from calendar_invite.models import Calendar
from calendar_invite.serializers import CalendarSerializer
from endpoint.view_mixins import CustomerRelationMixin


class CalendarViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer
