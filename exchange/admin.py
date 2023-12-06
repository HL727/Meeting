from django.conf import settings
from django.contrib import admin

from calendar_invite.admin import CalendarInline
from provider.admin import PasswordAdmin
from .models import EWSCredentials


class EWSCredentialsAdmin(PasswordAdmin):
    readonly_fields = ('is_working', 'last_modified_time', 'last_sync_error')
    list_display = ('username', 'customer',)
    list_filter = ('customer',)
    inlines = [CalendarInline]


if settings.EPM_ENABLE_CALENDAR:
    admin.site.register(EWSCredentials, EWSCredentialsAdmin)
