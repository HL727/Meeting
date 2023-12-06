from django.conf import settings
from django.contrib import admin

from tracelog.models import ActiveTraceLog


class ActiveTraceLogAdmin(admin.ModelAdmin):

    list_display = ('__str__', 'is_active', 'ts_start')
    readonly_fields = ('user', 'ts_created')
    if settings.ENABLE_EPM:
        autocomplete_fields = ('customer', 'endpoint')
    else:
        autocomplete_fields = ('customer',)


admin.site.register(ActiveTraceLog, ActiveTraceLogAdmin)
