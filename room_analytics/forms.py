from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from mptt.forms import TreeNodeChoiceField

from customer.models import Customer
from endpoint.models import Endpoint
from organization.models import OrganizationUnit
from statistics.forms import StatsForm, get_prev
from statistics.models import Server
from django.utils.timezone import now


class EPMCallStatsForm(StatsForm):

    endpoints = forms.ModelMultipleChoiceField(queryset=Endpoint.objects.none(), required=False)

    def __init__(self, *args, customer, **kwargs):

        self.customer = customer

        super().__init__(*args, customer=customer, **kwargs)

        self.fields['endpoints'].queryset = Endpoint.objects.filter(customer=self.customer)

        for f in ('cospace', 'tenant', 'ou'):
            self.fields.pop(f, None)

    def get_server_queryset(self):
        return self._base_get_server_queryset().exclude(~Q(customer=self.customer), type=Server.ENDPOINTS)

    def get_server_order(self):
        return {
            Server.ENDPOINTS: 0,
            Server.VCS: 1,
            Server.PEXIP: 5,
            Server.ACANO: 5,
        }

    def clean(self):
        cleaned = super().clean()

        if self.cleaned_data.get('tenant'):
            endpoints = Endpoint.objects.filter(
                Q(customer__acano_tenant_id=self.cleaned_data['tenant']) |
                Q(customer__pexip_tenant_id=self.cleaned_data['tenant'])
            )
        else:
            endpoints = self.fields['endpoints'].queryset

        if not cleaned.get('server'):
            try:
                cleaned['server'] = Server.objects.filter_for_customer(self.customer).filter(type__in=(Server.VCS, Server.ENDPOINTS))
            except Server.DoesNotExist:
                pass

        if cleaned.get('endpoints'):
            endpoints = cleaned['endpoints']
        elif cleaned.get('organization'):
            orgs = cleaned['organization'].get_descendants(include_self=True)
            endpoints = endpoints.filter(org_unit__in=orgs)
        return {**cleaned, 'endpoints': endpoints}


class HeadCountStatsForm(forms.Form):

    ts_start = forms.DateTimeField(label=_('Starttid'), initial=get_prev)
    ts_stop = forms.DateTimeField(label=_('Sluttid'), initial=now)

    only_hours = forms.CharField(label=_('Endast timmar (mån=1, sön=7)'), initial='7-17', required=False)
    only_days = forms.CharField(label=_('Endast dagar (mån=1, sön=7)'), initial='1-5', required=False)
    as_percent = forms.BooleanField(label=_('Visa som procent av rumskapacitet'), required=False)
    ignore_empty = forms.BooleanField(label=_('Ignorera tider med tomt rum'), required=False)
    fill_gaps = forms.BooleanField(label=_('Fyll saknade tider med 0-värden'), required=False)

    organization = TreeNodeChoiceField(label=_('Organisation'), queryset=OrganizationUnit.objects.none(), required=False)
    customers = forms.ModelMultipleChoiceField(queryset=Customer.objects.none(), required=False)
    endpoints = forms.ModelMultipleChoiceField(queryset=Endpoint.objects.none(), required=False)

    def __init__(self, *args, customer=None, **kwargs):

        self.customer = customer or None
        self.user = kwargs.pop('user', None)

        if self.user:
            customers = Customer.objects.get_for_user(self.user)
        else:
            customers = Customer.objects.filter(pk=customer.pk)

        self.customers = customers

        super().__init__(*args, **kwargs)

        self.fields['customers'].queryset = customers
        self.fields['endpoints'].queryset = Endpoint.objects.filter(customer__in=customers)
        self.fields['organization'].queryset = OrganizationUnit.objects.filter(
            customer__in=customers,
        )

    def clean(self):
        cleaned = super().clean()

        if self.data.get('endpoints'):
            endpoints = self.data['endpoints']
        elif cleaned.get('organization'):
            org_units = cleaned['organization'].get_descendants(include_self=True)
            endpoints = self.fields['endpoints'].queryset.filter(org_unit__in=org_units)
        elif self.data.get('multitenant'):
            endpoints = Endpoint.objects.filter(customer__in=self.customers)
        else:
            endpoints = Endpoint.objects.filter(customer=self.customer)

        cleaned['endpoints'] = endpoints

        return cleaned

    def get_headcount_graph_kwargs(self):

        c = self.cleaned_data

        from room_analytics.utils.report import GroupedHeadCountStats
        grouper = GroupedHeadCountStats(
            self.cleaned_data['endpoints'],
            c.get('ts_start') or now().replace(hour=0),
            c.get('ts_stop') or now(),
            only_days=c['only_days'],
            only_hours=c['only_hours']
        )

        graph_kwargs = dict(as_percent=c.get('as_percent'), ignore_empty=c.get('ignore_empty', False),
                            fill_gaps=c.get('fill_gaps', False))

        return grouper, graph_kwargs

    def get_headcount_graphs(self, **kwargs):

        grouper, graph_kwargs = self.get_headcount_graph_kwargs()
        return grouper.get_all_graphs(**{**graph_kwargs, **kwargs})

    def get_headcount_graphs_max_values(self, **kwargs):

        grouper, graph_kwargs = self.get_headcount_graph_kwargs()
        return grouper.get_all_graphs_max_values(**{**graph_kwargs, **kwargs})

    def get_all_individual_graphs(self, **kwargs):

        grouper, graph_kwargs = self.get_headcount_graph_kwargs()
        return grouper.get_all_individual_graphs(**{**graph_kwargs, **kwargs})


