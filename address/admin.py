from django.conf import settings
from django.contrib import admin
from django.utils.translation import gettext as _
from django.utils.html import format_html

from .models import Item, Group, AddressBook
from mptt.admin import MPTTModelAdmin


class ItemInline(admin.TabularInline):

    model = Item


class AddressBookAdmin(admin.ModelAdmin):

    list_display = ('title', 'customer', 'get_soap_url', 'items', 'links')
    list_filter = ('customer',)
    search_fields = ('customer__title', 'title')

    def items(self, obj):
        return Item.objects.filter(group__address_book=obj).count()

    def links(self, obj):
        export_button = format_html('<a class="button" href="{}">{}</a>',
                                    obj.get_absolute_url(),
                                    _('Visa'))
        view_button = format_html('<a class="button" href="{}">{}</a>',
                                  '/json-api/address_book/{}/export/?customer={}'.format(obj.pk, obj.customer_id),
                                  _('Export'))

        return format_html('{} {}', export_button, view_button)


class GroupAdmin(MPTTModelAdmin):

    inlines = [ItemInline]
    list_display = ('title', 'customer')
    list_filter = ('customer',)
    search_fields = ('customer__title', 'title')


class ItemAdmin(admin.ModelAdmin):

    list_display = ('title', 'group', 'customer')
    list_filter = ('customer',)
    search_fields = ('customer__title', 'title')


if settings.ENABLE_EPM:
    admin.site.register(AddressBook, AddressBookAdmin)

if settings.DEBUG:
    admin.site.register(Group, GroupAdmin)
    admin.site.register(Item, ItemAdmin)
