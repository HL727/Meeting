from typing import Type, Sequence, Tuple

from django.forms import forms
from django.urls import reverse

from customer.view_mixins import CustomerMixin
from statistics.forms import StatsForm
from statistics.graph import get_graph, get_sametime_graph
from statistics.models import Call
from statistics.utils.leg_collection import get_valid_relations, populate_legs, LegCollection
from statistics.utils.report import summarize


class CallStatisticsReportMixin(CustomerMixin):

    form_class: Type[forms.Form] = StatsForm
    excel_url_name = 'stats_excel'
    debug_excel_url_name = 'stats_excel_debug'
    pdf_url_name = 'stats_pdf'

    form = None

    def get_serializer_context(self):
        try:
            context = super().get_serializer_context()
        except AttributeError:
            context = {}

        context['form_class'] = self.form_class
        return context

    def get_form_data(self):
        GET_values = self.request.GET.copy()
        GET_values.pop('customer', None)
        GET_values.pop('ajax', None)

        return GET_values

    def get_form(self):

        data = self.get_form_data()
        if data:
            form = self.form_class(data, user=self.request.user, customer=self.customer)
            form.is_valid()
        else:
            form = self.form_class(user=self.request.user, customer=self.customer)

        self.form = form
        return form

    def get_graphs(self, legs: LegCollection, as_json=False, **kwargs):

        return {
            'graph': get_graph(legs, as_json=as_json, **kwargs),
            'sametime_graph': get_sametime_graph(legs, as_json=as_json, **kwargs),
        }

    def get_settings_data(self):
        form = self.form_class(self.request.GET or None, user=self.request.user, customer=self.customer)
        return {
            'choices': {
                'tenant': list(form.get_ldap_tenants()[0]),
                'server': list(form.get_servers()),
            }
        }

    def get_call_data(self, form) -> Tuple[Sequence[Call], LegCollection]:
        calls, legs = form.get_calls_and_legs()
        print('=========CALLS=====', calls)
        if self._has_all_customers():
            valid_relations = None
        else:
            valid_relations = get_valid_relations(user=self.request.user)

        c = form.cleaned_data if form.is_valid() else {}
        leg_collection = LegCollection.from_legs(legs, valid_relations=valid_relations,
                                                 trim_times=(c.get('ts_start'), c.get('ts_stop')))

        return calls, leg_collection

    def allow_debug_stats(self, form=None):
        if self.request.user.is_staff:
            return True

        if not form or not form.is_valid():
            return False

        if form.cleaned_data['server'].is_endpoint and not form.cleaned_data['multitenant']:
            from endpoint.models import CustomerSettings

            c_settings = CustomerSettings.objects.get_for_customer(self._get_customer())
            return c_settings.enable_user_debug_statistics
        return False

    def get_stats_data(self, as_json=False, target_graphs=None, debug=False):
        print('=========STATS DATA==========')
        context = {}

        form = self.get_form()
        if form.is_valid():
            cleaned = form.cleaned_data
        else:
            cleaned = {}

        if debug and not self.allow_debug_stats(form):
            debug = False

        if len(form.get_ldap_tenants()) <= 1 or cleaned or as_json:
            calls, legs = self.get_call_data(form)
            defer_load = False
        else:
            calls = []  # dont load for admins without click
            legs = LegCollection.from_legs([])
            defer_load = True

        if target_graphs in (True, None):
            context['graphs'] = self.get_graphs(legs, as_json=as_json)

            if target_graphs:
                return context, form

        context.update({
            'calls': [],
            'legs': [],
            'loaded': not form.errors and not defer_load,
            'has_data': bool(legs),
            'summary': summarize(legs, ou=cleaned.get('ou'), ts_start=cleaned.get('ts_start'), ts_stop=cleaned.get('ts_stop')),
            'debug_calls': debug,
            'defer_load': defer_load,
        })

        if form.errors:
            context.update({
                'errors': dict(form.errors),
            })

        if not as_json or debug:
            context.update({
                'calls': calls,
                'legs': legs,
            })

        if as_json:
            context['summary'] = {k: v
                                  for k, v in context['summary'].compact_dict().items()
                                  if k in {'cospace', 'user', 'target_group', 'cospace_total'}
                                  }

        context.update(self.get_settings_data())

        context['pdf_report_url'] = '{}?{}'.format(
            reverse(self.pdf_url_name), self.request.META['QUERY_STRING'].replace('ajax=1', '').replace('&&', ''))

        context['excel_report_url'] = '{}?{}'.format(
            reverse(self.excel_url_name), self.request.META['QUERY_STRING'].replace('ajax=1', '').replace('&&', ''))

        if self.allow_debug_stats(form):
            context['excel_debug_report_url'] = '{}?{}'.format(
                reverse(self.debug_excel_url_name), self.request.META['QUERY_STRING'].replace('ajax=1', '').replace('&&', ''))

        return context, form
