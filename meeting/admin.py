from reversion.admin import VersionAdmin

from django.conf import settings
from django.contrib import admin

from meeting.models import Meeting


class MeetingAdmin(VersionAdmin):

    search_fields = ('title',)
    list_filter = ('customer', 'ts_start')
    list_display = ('title', 'ts_start', 'ts_stop')
    date_hierarchy = 'ts_start'


if settings.DEBUG:
    if settings.ENABLE_CORE:
        admin.site.register(Meeting, MeetingAdmin)
