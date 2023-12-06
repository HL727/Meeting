from django.conf import settings
from django.contrib import admin

from endpoint_provision.models import EndpointTemplate


class EndpointTemplateAdmin(admin.ModelAdmin):

    list_filter = ('customer',)

    list_display = ('name', 'has_command', 'has_configuration')

    def has_command(self, obj: EndpointTemplate):
        return bool(obj.commands)

    has_command.boolean = True

    def has_configuration(self, obj: EndpointTemplate):
        return bool(obj.settings)

    has_configuration.boolean = True


if settings.ENABLE_EPM:
    admin.site.register(EndpointTemplate, EndpointTemplateAdmin)
