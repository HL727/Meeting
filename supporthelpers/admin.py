from django.contrib import admin

from django.contrib.auth.admin import UserAdmin

from django.contrib.auth.models import User
from .models import CustomerPermission


class CustomerPermissionInline(admin.TabularInline):
    model = CustomerPermission


class NewUserAdmin(UserAdmin):
    pass

NewUserAdmin.inlines = UserAdmin.inlines + [CustomerPermissionInline]

admin.site.unregister(User)
admin.site.register(User, NewUserAdmin)

# Register your models here.
