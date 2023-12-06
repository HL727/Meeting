from django.conf import settings
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from calendar_invite.models import Calendar, CalendarItem, Credentials


class CustomerFilteredEndpointsMixin:

    def _get_customer_from_object(self, object_id):
        try:
            return self.parent_model.objects.filter(pk=object_id).values_list('customer', flat=True).first()
        except Exception:
            return self.model.objects.filter(pk=object_id).values_list('customer', flat=True).first()

    def get_endpoint_foreignkey_kwargs(self, request):

        from endpoint.models import Endpoint
        customer_id = None

        object_id = request.resolver_match and request.resolver_match.kwargs.get('object_id')
        if object_id:
            customer_id = self._get_customer_from_object(object_id)

        if not customer_id and request.GET.get('customer__id__exact'):
            customer_id = request.GET.get('customer__id__exact')
        elif request.GET.get('credentials__id__exact'):
            customer_id = Credentials.objects.filter(pk=request.GET.get('credentials__id__exact')).values_list('customer', flat=True).first()

        if customer_id:
            return Endpoint.objects.distinct().filter(customer=customer_id).order_by('title')

        return Endpoint.objects.distinct().filter(customer__calendar__isnull=False).order_by('title')

    def get_field_queryset(self, db, db_field, request):
        if db_field == 'endpoint':
            queryset = self.get_endpoint_foreignkey_kwargs(request)
            if queryset:
                return queryset
        return super().get_field_queryset(db, db_field, request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "endpoint":
            queryset = self.get_endpoint_foreignkey_kwargs(request)
            if queryset:
                kwargs['queryset'] = queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CalendarInline(CustomerFilteredEndpointsMixin, admin.TabularInline):
    model = Calendar
    extra = 1
    readonly_fields = ('is_working',)

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('username')


class CalendarAdmin(CustomerFilteredEndpointsMixin, admin.ModelAdmin):

    list_display = ('username', 'endpoint', 'cached_name', 'is_working', 'customer')
    list_filter = ('credentials', 'customer',)
    search_fields = ('username', 'endpoint__title')

    readonly_fields = ('cached_name', 'cached_path', 'folder_id', 'credentials', 'is_working', 'customer')

    def get_list_editable(self):
        pass

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return Calendar.objects.all().select_related('credentials', 'customer', 'endpoint')



class CalendarItemAdmin(admin.ModelAdmin):
    list_display = ('meeting_title', 'credentials', 'short_item_id')
    list_filter = ('credentials',)

    def meeting_title(self, obj):
        return obj.meeting.title

    def short_item_id(self, obj):
        return obj.item_id[:20]


if settings.EPM_ENABLE_CALENDAR:
    admin.site.register(Calendar, CalendarAdmin)
    if settings.DEBUG:
        admin.site.register(CalendarItem, CalendarItemAdmin)
