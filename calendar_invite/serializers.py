from rest_framework import serializers
from .models import Calendar


class CalendarSerializer(serializers.ModelSerializer):

    class Meta:
        model = Calendar
        fields = ('id', 'username', 'endpoint', 'cached_name', 'is_working', 'ts_last_sync')
        read_only_fields = ('id', 'cached_name', 'ts_last_sync', 'is_working')
