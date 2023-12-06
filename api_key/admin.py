from django.conf import settings
from django.contrib import admin

from api_key.models import OAuthCredential, BookingAPIKey
from exchange.models import EWSCredentials
from msgraph.models import MSGraphCredentials
from provider.admin import PasswordAdmin


class MSGraphCredentialsInline(admin.TabularInline):
    model = MSGraphCredentials
    extra = 0
    max_num = 1

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'username':
            kwargs['required'] = False
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class EWSCredentialsInline(admin.TabularInline):
    model = EWSCredentials
    extra = 0
    max_num = 1


class OAuthCredentialAdmin(PasswordAdmin):
    def get_exclude(self, request, obj=None):
        excludes = self.exclude or ()
        if obj and obj.pk:
            return excludes + ('customer',)
        return excludes

    list_display = ('client_id', 'username', 'customer')
    list_filter = ('customer',)
    inlines = [MSGraphCredentialsInline, EWSCredentialsInline]
    readonly_fields = ('customer',)


class BookingAPIKeyAdmin(admin.ModelAdmin):

    list_display = ('title', 'key', 'enabled')
    list_filter = ('enabled',)
    filter_horizontal = ('limit_customers',)
    readonly_fields = ('ts_created', 'ts_last_used', 'enabled')


if settings.EPM_ENABLE_CALENDAR:
    admin.site.register(OAuthCredential, OAuthCredentialAdmin)
if settings.ENABLE_CORE:
    admin.site.register(BookingAPIKey, BookingAPIKeyAdmin)
