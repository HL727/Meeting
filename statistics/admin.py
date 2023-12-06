from django.contrib import admin
from django.utils.html import format_html

from .models import DomainTransform, DomainRewrite, Server


class RewriteInline(admin.TabularInline):

    model = DomainRewrite


class DomainTransformAdmin(admin.ModelAdmin):

    inlines = [RewriteInline]


class ServerAdmin(admin.ModelAdmin):

    list_display = ('name', 'customer', 'get_type_display', 'get_cdr_url')
    list_filter = ('customer',)

    readonly_fields = ('csv_export', 'get_cdr_url')

    def csv_export(self, obj: Server):

        return format_html(
            '<a target="_blank" href="{}">Export calls</a> | <a target="_blank" href="{}">Export legs</a>',
            obj.get_export_path('call'),
            obj.get_export_path('leg'),
        ) + format_html(
            ' | <a target="_blank" href="{}">Import calls</a> | <a target="_blank" href="{}">Import legs</a>',
            obj.get_import_path('call'),
            obj.get_import_path('leg'),
        )


admin.site.register(Server, ServerAdmin)
admin.site.register(DomainTransform, DomainTransformAdmin)
