from django.conf import settings
from django.contrib import admin
from .models import RecordingUserAdmin, RecordingUserAlias


class RecordingUserAliasInline(admin.TabularInline):
    model = RecordingUserAlias


class RecordingUserAdminAdmin(admin.ModelAdmin):

    inlines = [RecordingUserAliasInline]

if settings.ENABLE_CORE:
    admin.site.register(RecordingUserAdmin, RecordingUserAdminAdmin)
