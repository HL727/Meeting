from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest

from license import license_allow_another
from provider.admin import PasswordAdmin

from .models import Endpoint


class EndpointAdmin(PasswordAdmin):

    list_display = ('title', 'customer', 'get_connection_type_display')
    list_filter = ('customer', 'connection_type')
    search_fields = ('title', 'customer__title', 'product_name')
    model = Endpoint
    readonly_fields = (
        'webex_registration',
        'pexip_registration',
        'event_secret_key',
    )

    def has_add_permission(self, request: HttpRequest) -> bool:

        if not super().has_add_permission(request):
            return False

        return license_allow_another('epm:endpoint')


if settings.ENABLE_EPM:
    admin.site.register(Endpoint, EndpointAdmin)
