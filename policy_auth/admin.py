from django.conf import settings
from django.contrib import admin
from django.utils.timezone import now

from . import models


class PolicyAuthorizationAdmin(admin.ModelAdmin):

    search_fields = ('local_alias',)
    date_hierarchy = 'valid_from'
    list_filter = ('customer', 'cluster', 'source')
    list_display = ('local_alias', 'customer', 'valid_from', 'valid_to', 'check_active', 'check_requirements', 'check_overrides')
    readonly_fields = ('created', 'user', 'source', 'external_id')

    def save_model(self, request, obj, form, change):
        obj.user = obj.user or request.user
        super().save_model(request, obj, form, change)

    # fields
    def check_active(self, obj):
        return obj.valid_from <= now() <= obj.valid_to
    check_active.short_description = 'aktiv'
    check_active.boolean = True

    def check_requirements(self, obj):
        return len(obj.require_fields) > 0
    check_requirements.short_description = 'kriterier'
    check_requirements.boolean = True

    def check_overrides(self, obj):
        return len(obj.settings_override) > 0
    check_overrides.short_description = 'inställningar'
    check_overrides.boolean = True


class PolicyAuthorizationOverrideAdmin(admin.ModelAdmin):

    search_fields = ('local_alias_match', 'remote_list')
    list_filter = ('customer', 'cluster')
    list_display = ('local_alias_match', 'customer', 'addresses', 'check_overrides')

    def addresses(self, obj):
        all_objs = list(obj.match_objects)
        objs = [o['remote_alias'][:15] for o in all_objs if o.get('remote_alias')][:3]

        s = ', '.join(objs[:3])
        if len(all_objs) > len(objs):
            return '{} + {} fler'.format(s, len(all_objs) - len(objs))
        return s

    # fields
    def check_overrides(self, obj):
        return len(obj.settings_override) > 0
    check_overrides.short_description = 'inställningar'
    check_overrides.boolean = True


if settings.ENABLE_CORE:
    admin.site.register(models.PolicyAuthorization, PolicyAuthorizationAdmin)
    admin.site.register(models.PolicyAuthorizationOverride, PolicyAuthorizationOverrideAdmin)
