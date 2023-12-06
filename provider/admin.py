from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from django import forms
from reversion.admin import VersionAdmin

from license import license_allow_another
from policy.models import ClusterPolicy
from .models.acano import AcanoCluster
from .models.pexip import PexipCluster
from .models.provider import ClusterSettings, Provider, Cluster, VideoCenterProvider, LdapProvider, \
    SeeviaProvider, TandbergProvider
from .models.provider_data import ClearSeaAccount
from .models.vcs import VCSEProvider


class ClusterSettingsBaseInline(admin.StackedInline):
    def get_exclude(self, request, obj=None):
        exclude = super().get_exclude(request, obj=obj) or ()

        is_pexip = self.check_is_pexip(request, obj)
        if not is_pexip:
            exclude += ('dial_out_location', 'theme_profile')

        return exclude

    def check_is_pexip(self, request, obj=None):

        from customer.models import Customer
        if obj and isinstance(obj, Customer):
            provider = obj.get_provider()
            return provider and provider.is_pexip
        elif obj and getattr(obj, 'is_pexip', None):
            return True
        elif obj and hasattr(obj, 'cluster') and getattr(obj.cluster, 'is_pexip', None):
            return True

        return False

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field == 'remove_expired_meeting_rooms':
            if self.check_is_pexip(request):
                kwargs['choices'] = ClusterSettings.PEXIP_PROVISION_CHOICES
            else:
                kwargs['choices'] = ClusterSettings.OTHER_PROVISION_CHOICES

        return super().formfield_for_choice_field(db_field, request, **kwargs)


class CustomerClusterSettingsInline(ClusterSettingsBaseInline):

    model = ClusterSettings
    verbose_name = _('klusterinställning')
    verbose_name_plural = _('klusterinställningar')

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if not obj else 0

    def get_queryset(self, request):
        return super().get_queryset(request).filter(customer__isnull=False)


class ClusterSettingsInline(ClusterSettingsBaseInline):

    model = ClusterSettings
    exclude = ('customer', )
    min_num = 1
    max_num = 1
    verbose_name = _('klusterinställning')
    verbose_name_plural = _('klusterinställningar')


class ClusterCustomerSettingsInline(CustomerClusterSettingsInline):
    verbose_name = _('kundspecifik inställning')
    verbose_name_plural = _('kundspecifika inställningar')

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if not obj else 0


class PexipClusterInline(admin.StackedInline):

    model = PexipCluster
    fk_name = 'provider_ptr'
    extra = 0
    min_num = 0
    fields = ('default_customer',)
    can_delete = False
    max_num = 1


class AcanoClusterInline(admin.StackedInline):

    model = AcanoCluster
    fk_name = 'provider_ptr'
    extra = 0
    min_num = 0
    can_delete = False
    fields = ('clear_chat_interval', 'set_call_id_as_uri')


class ClusterPolicyInline(admin.StackedInline):

    model = ClusterPolicy
    extra = 0
    min_num = 1


class ClusterAdmin(VersionAdmin):
    # TODO override modelform to filter types

    fields = ('title', 'type', 'internal_domains')
    if settings.ENABLE_CORE:
        fields += ('auto_update_statistics', 'use_local_database', 'use_local_call_state')
    inlines = [PexipClusterInline, AcanoClusterInline, ClusterSettingsInline]
    if settings.ENABLE_CORE:
        inlines.extend([ClusterCustomerSettingsInline, ClusterPolicyInline])
    if not settings.ENABLE_CORE:
        exclude = ('auto_update_statistics', 'use_local_database', 'use_local_call_state')

    def get_fields(self, request, obj=None):
        result = super().get_fields(request, obj=obj)

        if obj and obj.pk:
            return [f for f in result if f != 'type']
        return result

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj=obj, change=change, **kwargs)
        try:
            if form.base_fields.get('type'):
                form.base_fields['type'].choices = [
                    (c, Cluster.TYPES.get_title(c)) for c in Cluster.CLUSTERED_TYPES
                ]
        except AttributeError:
            if settings.DEBUG:
                raise
        return form

    def has_add_permission(self, request: HttpRequest) -> bool:
        if not super().has_add_permission(request):
            return False

        return license_allow_another('core:cluster')

    def get_inline_instances(self, request: HttpRequest, obj: Cluster = None):
        inlines = super().get_inline_instances(request, obj=obj)
        result = []
        for inline in inlines:
            if isinstance(inline, PexipClusterInline):
                if not obj or not obj.is_pexip:
                    continue
            if isinstance(inline, AcanoClusterInline):
                if not obj or not obj.is_acano:
                    continue

            result.append(inline)

        return result


class PasswordAdmin(admin.ModelAdmin):
    def get_form(self, request, obj=None, **kwargs):
        kwargs['widgets'] = {
            'password': forms.TextInput(attrs={'type': 'password'}),
            'secret': forms.TextInput(attrs={'type': 'password'}),
        }
        return super().get_form(request, obj, **kwargs)


class ProviderAdmin(PasswordAdmin, VersionAdmin):

    list_display = ('title', 'get_subtype_display', 'cluster')
    readonly_fields = ('options',)
    exclude = ('type', 'auto_update_statistics', 'web_host', 'phone_ivr')
    list_filter = ('cluster',)

    def has_add_permission(self, request: HttpRequest) -> bool:
        if not super().has_add_permission(request):
            return False

        return license_allow_another('core:mcu')

    def get_queryset(self, request):
        return super().get_queryset(request)\
            .exclude(type__in=Provider.CLUSTERED_TYPES)\
            .exclude(type__in=Provider.VIRTUAL_TYPES)


if settings.ENABLE_CORE:
    admin.site.register(Provider, ProviderAdmin)
    admin.site.register(Cluster, ClusterAdmin)
    admin.site.register(VideoCenterProvider, PasswordAdmin)

if settings.DEBUG:
    admin.site.register(ClearSeaAccount, PasswordAdmin)

admin.site.register(LdapProvider, PasswordAdmin)
admin.site.register(SeeviaProvider, PasswordAdmin)
admin.site.register(VCSEProvider, PasswordAdmin)
admin.site.register(TandbergProvider)

admin.site.site_title = _('Mividas backend-administration')
admin.site.site_header = _('Mividas backend-administration')
