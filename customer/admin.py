from django.conf import settings
from django.contrib import admin
from reversion.admin import VersionAdmin

from policy.admin import CustomerPolicyInline
from provider.admin import CustomerClusterSettingsInline
from provider.models.provider import Provider
from .models import CustomerMatch, CustomerKey, Customer


class CustomerMatchAdmin(VersionAdmin):

    search_fields = ('customer__title', 'prefix_match', 'suffix_match', 'regexp_match')
    list_display = ('customer', 'cluster',  'room_count', 'prefix_match', 'suffix_match', 'regexp_match', 'match_mode', 'priority')
    list_filter = ('cluster', )
    readonly_fields = ('room_count',)
    ordering = ('priority', 'id')


class CustomerMatchInline(admin.TabularInline):

    model = CustomerMatch

    def get_extra(self, request, obj=None, **kwargs):
        return 2 if not obj else 0


class CustomerKeyInline(admin.TabularInline):

    model = CustomerKey
    min_num = 0
    extra = 0


class CustomerAdmin(VersionAdmin):

    if settings.ENABLE_CORE:
        inlines = [CustomerKeyInline, CustomerClusterSettingsInline, CustomerMatchInline, CustomerPolicyInline]

    search_fields = ('title',)
    list_display = ('title', 'acano_tenant_id', 'lifesize_provider')
    list_filter = ('lifesize_provider',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'lifesize_provider':
            kwargs['queryset'] = Provider.objects.filter(type__in=Provider.CLUSTERED_TYPES)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


if settings.ENABLE_CORE:
    admin.site.register(CustomerMatch, CustomerMatchAdmin)
admin.site.register(Customer, CustomerAdmin)
