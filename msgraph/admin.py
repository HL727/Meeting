from django.conf import settings
from django.contrib import admin

from calendar_invite.admin import CalendarInline
from msgraph.models import MSGraphCredentials
from provider.admin import PasswordAdmin


class MSGraphCredentialsAdmin(PasswordAdmin):
    readonly_fields = ('is_working', 'username', 'last_modified_time', 'last_sync_error')
    list_display = ('customer', 'username')
    list_filter = ('customer',)
    inlines = [CalendarInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'oauth_credential':
            kwargs['required'] = True
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    kwargs = {
        'username': {'blank': True},
        'oauth_credential': {'blank': False},  # FIXME
    }


if settings.EPM_ENABLE_CALENDAR:
    admin.site.register(MSGraphCredentials, MSGraphCredentialsAdmin)
