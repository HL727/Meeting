from django.contrib import admin
from . import models


class BackendInline(admin.TabularInline):

    model = models.BackendAdministrator


class PortalInline(admin.TabularInline):

    model = models.PortalAdministrator


class VideoCenterInline(admin.TabularInline):

    model = models.VideoCenterAdministrator


class OrgAdmin(admin.ModelAdmin):

    inlines = [BackendInline, PortalInline, VideoCenterInline]


admin.site.register(models.AdminOrganization, OrgAdmin)
