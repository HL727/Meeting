from django.contrib import admin
from .models import Message, DefaultMessage


class MessageAdmin(admin.ModelAdmin):

    list_display = ('title', 'type', 'customer', 'active', 'ts_created', 'ts_updated')
    list_filter = ('type', 'customer', 'active')


admin.site.register(Message, MessageAdmin)

admin.site.register(DefaultMessage)

