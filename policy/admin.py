from django.conf import settings
from django.contrib import admin
from . import models
from .models import ExternalPolicy


class CustomerPolicyInline(admin.TabularInline):

    model = models.CustomerPolicy
    min_num = 0
    extra = 0


class CustomerPolicyAdmin(admin.ModelAdmin):

    search_fields = ('customer__title',)
    list_display = ('customer', 'date_start', 'participant_normal_limit', 'participant_gateway_limit', 'participant_limit', 'participant_hard_limit', 'soft_limit_action', 'hard_limit_action')
    list_editable = ('date_start', 'participant_normal_limit', 'participant_gateway_limit', 'participant_hard_limit')
    ordering = ('customer', '-date_start')


class ExternalPolicyInline(admin.TabularInline):
    model = ExternalPolicy
    extra = 0


class ClusterPolicyAdmin(admin.ModelAdmin):

    inlines = [ExternalPolicyInline]
    list_display = ('cluster', 'soft_limit_action', 'hard_limit_action', 'url')
    list_filter = ('cluster',)

    def soft_limit_action(self, obj):
        return obj.get_soft_limit_action_display()
    soft_limit_action.short_description = 'Soft limit actoin'

    def hard_limit_action(self, obj):
        return obj.get_hard_limit_action_display()
    hard_limit_action.short_description = 'Hard limit actoin'

    def url(self, obj):
        return obj.get_absolute_url()
    url.short_description = 'Pexip intern url'


if settings.ENABLE_CORE:
    admin.site.register(models.CustomerPolicy, CustomerPolicyAdmin)
    admin.site.register(models.ClusterPolicy, ClusterPolicyAdmin)



