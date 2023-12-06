from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.views import View
from django.utils.translation import gettext as _

from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from organization.models import OrganizationUnit

from django.http import HttpResponse

if TYPE_CHECKING:
    pass


class ItemListMixin(View):
    PREFIX_FOR_MATCH_ALL = '__MATCH_ALL__'

    def populate_items_context(self, context, q, items_key):
        context['PREFIX_FOR_MATCH_ALL'] = ItemListMixin.PREFIX_FOR_MATCH_ALL

        if q.startswith(ItemListMixin.PREFIX_FOR_MATCH_ALL):
            q = q.split(ItemListMixin.PREFIX_FOR_MATCH_ALL, 1)[1]
        else:
            q = ''

        context['filter'] = q

        offset = self.request.GET.get('offset') or 0
        if offset:
            offset = int(offset)

        if self.request.GET.get('organization_unit'):
            org_unit = OrganizationUnit.objects.get(pk=self.request.GET.get('organization_unit'))
            extra_context = self.get_org_unit_filter_context(org_unit, offset, items_key, q)
        else:
            extra_context = self.get_item_list_context(offset, items_key, q)

        context.update(extra_context)

    def get_item_list_context(self, offset, items_key, q):

        context = {}

        items, context['count'] = self.get_items(self._get_api(), q, offset, self.customer.acano_tenant_id)

        url = self.request.GET.copy()
        if context['count'] > offset + len(items):
            url['offset'] = offset + len(items)
            context['next_url'] = url.urlencode()
        if offset:
            url['offset'] = max(0, offset - 10)
            context['prev_url'] = url.urlencode()
        context['page_from'] = offset + 1
        context['page_to'] = offset + len(items)
        context[items_key] = items

        return context

    def get_org_unit_filter_context(self, organization_unit, offset, items_key, q):

        api = self._get_api()
        next_page_of_unfiltered_items, total_number_of_items = self.get_items(api, q, offset, self.customer.acano_tenant_id)
        current_offset = offset
        min_items_per_page = len(next_page_of_unfiltered_items)

        filtered_items = []
        is_there_more = True

        context = {}

        org_units = organization_unit.get_descendants(include_self=True)

        while len(filtered_items) < min_items_per_page:
            next_page = self.filter_items_for_org_unit(next_page_of_unfiltered_items, org_units)

            filtered_items += next_page
            current_offset += len(next_page_of_unfiltered_items)
            if current_offset >= total_number_of_items or not next_page_of_unfiltered_items:
                is_there_more = False
                break
            next_page_of_unfiltered_items, _ = self.get_items(api, q, current_offset, self.customer.acano_tenant_id)

        context[items_key] = filtered_items

        url = self.request.GET.copy()

        context['organization_unit'] = organization_unit

        if is_there_more:
            url['offset'] = current_offset
            context['next_url'] = url.urlencode()

        if offset > 0:
            url['offset'] = 0
            context['first_url'] = url.urlencode()

        return context

    def get_items(self, api, q, offset, tenant):
        raise NotImplementedError('Must implement in user of ItemListMixin')

    def filter_items_for_org_unit(self, items, org_units):
        raise NotImplementedError('Must implement in user of ItemListMixin')


class TrackChangesMixin(LoginRequiredMixin, CustomerMixin):

    form = None

    def get(self, request, *args, **kwargs):
        if request.GET.get('date_start'):
            self.form = self.form_class(request.GET, tenant_id=self.customer.acano_tenant_id)
        else:
            self.form = self.form_class(
                tenant_id=self.customer.acano_tenant_id,
                initial={
                    'date_start': date.today() - timedelta(days=8),
                    'date_stop': date.today() - timedelta(days=1)
                })

        if request.GET.get('excel_export'):
            response = HttpResponse(content_type="application/ms-excel")
            response['Content-Disposition'] = 'attachment; filename={}-{}.xls'.format(self.excel_export_basename, date.today())
            self.form.excel_export().save(response)
            return response

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form
        context['additions'] = self.form.get_additions()
        context['removals'] = self.form.get_removals()
        return context


class SettingsProductMixin(View):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['vuetify_themes'] = settings.VUETIFY_THEMES
        context['product'] = get_product_name()
        return context


def get_product_name():
    if settings.ENABLE_CORE and settings.ENABLE_EPM:
        return _('Mividas Core och Mividas Rooms')
    elif settings.ENABLE_CORE:
        return _('Mividas Core')
    elif settings.ENABLE_EPM:
        return _('Mividas Rooms')
    return ''
