from django import forms
from customer.models import Customer
from statistics.utils.leg_collection import populate_legs, merge_duplicate_legs
from .models import Call, Server, Leg
from datetime import timedelta
from mptt.forms import TreeNodeChoiceField
from django.utils.translation import gettext_lazy as _, ngettext_lazy as _n

from django.utils.timezone import now
from django.conf import settings
from django.db.models import Q
from organization.models import CoSpaceUnitRelation, UserUnitRelation, OrganizationUnit



def get_latest():
    try:
        last = Call.objects.filter(ts_start__isnull=False).order_by('-ts_start')[0].ts_start
    except Exception:
        last = now()
    return last


def get_prev():
    return (get_latest() or now()) - timedelta(days=10)


# TODO separate StatsForm to another for multitenant analytics, too many "if multitenant"

class StatsForm(forms.Form):

    ts_start = forms.DateTimeField(label=_('Starttid'), initial=get_prev)
    ts_stop = forms.DateTimeField(label=_('Sluttid'), initial=now)
    ou = forms.CharField(label=_('Grupp'), required=False)
    tenant = forms.ChoiceField(label=_('Tenant'), choices=[('Alla', '')], required=False)
    cospace = forms.CharField(label=_n('Mötesrum', 'Mötesrum', 1), required=False)
    member = forms.CharField(label=_('Deltagare'), required=False)
    server = forms.ChoiceField(label=_('Server'), choices=(), required=False)
    protocol = forms.ChoiceField(label=_('Protokoll'), choices=Leg.PROTOCOLS, required=False)
    multitenant = forms.BooleanField(label=_('Använd aktiv kund'), required=False)
    only_gateway = forms.BooleanField(label=_('Endast gateway'), required=False)
    organization = TreeNodeChoiceField(label=_('Organisation'), queryset=OrganizationUnit.objects.all(), required=False)

    def __init__(self, *args, customer=None, **kwargs):

        self.customer = customer or None
        self.user = kwargs.pop('user', None)

        super().__init__(*args, **kwargs)

        tenants, enable_tenants = self.get_ldap_tenants()
        if not enable_tenants:
            self.fields.pop('tenant', None)
        else:
            self.fields['tenant'].choices = tenants
            self.fields['tenant'].widget.choices = tenants

        self.fields['server'].choices = self.get_server_choices()

        self.fields['organization'].queryset = OrganizationUnit.objects.filter(
            customer__in=Customer.objects.get_for_user(self.user) if self.user else [customer]
        )

        if self.user.is_staff:
            self.fields['organization'].queryset = OrganizationUnit.objects.all()

        if not settings.ENABLE_ORGANIZATION:
            self.fields.pop('organization')

        if not getattr(settings, 'ENABLE_GROUPS', False):
            self.fields.pop('ou')

    def _base_get_server_queryset(self):

        if self.user and self.data.get('multitenant'):
            return Server.objects.filter_for_user(self.user)
        return Server.objects.filter_for_customer(self.customer)

    def get_server_queryset(self):
        if self.user and self.data.get('multitenant'):
            return self._base_get_server_queryset()
        return self._base_get_server_queryset().exclude(type=Server.ENDPOINTS)

    def get_server_order(self):
        return {
            Server.PEXIP: 0,
            Server.ACANO: 5,
            Server.VCS: 10,
        }

    def get_servers(self):
        result = []
        all_tenants = self.get_tenants()[1]

        first_endpoint_server = True
        order = self.get_server_order()

        # type first then id
        servers = sorted(
            self.get_server_queryset(),
            key=lambda x: (order.get(x.type, 99), x.latest_calls[0], -x.latest_calls[1]),
        )
        for server in servers:

            if server.is_acano:
                tenants = all_tenants['acano']
            elif server.is_pexip:
                tenants = all_tenants['pexip']
            elif server.is_endpoint:
                if not first_endpoint_server:
                    continue

                first_endpoint_server = False
                tenants = all_tenants['endpoint']
            else:
                tenants = []

            cur = {
                'id': server.pk,
                'title': _('Endpoint') if server.is_endpoint else str(server),
                'type': server.type,
                'tenants': tenants,
            }
            result.append(cur)

        return result

    def get_server_choices(self):
        return [(server['id'], server['title']) for server in self.get_servers()]

    def clean_server(self):
        value = str(self.cleaned_data.get('server', '')).lstrip('0')

        if not value:
            return None
        try:
            return self.get_server_queryset().get(pk=value)
        except Server.DoesNotExist:
            raise forms.ValidationError('Server invalid')

    def get_tenants(self):

        if not self.data.get('multitenant'):
            customers = [self.customer]
        elif self.user and not self.user.is_staff:
            customers = Customer.objects.get_for_user(self.user).exclude(acano_tenant_id='', pexip_tenant_id='')
        else:
            customers = None

        result = []

        enable_tenants = customers and len(customers) > 1

        if not customers:
            customers = Customer.objects.all()
            result = [('', 'Alla')]

            if len(customers) <= 1:
                enable_tenants = False
            else:
                enable_tenants = True
                result += [('none', 'Standard-tenant')]

        grouped = {
            'acano': result[:],
            'pexip': result[:],
            'endpoint': [],
        }

        endpoint_servers = {s.customer_id: s for s in Server.objects.filter(type=Server.ENDPOINTS)}

        for customer in customers:
            if customer.acano_tenant_id:
                grouped['acano'].append((customer.acano_tenant_id, str(customer)))
                result.append((customer.acano_tenant_id, str(customer)))
            if customer.pexip_tenant_id:
                grouped['pexip'].append((customer.pexip_tenant_id, str(customer)))
                result.append((customer.pexip_tenant_id, str(customer)))

            if endpoint_servers.get(customer.pk):
                cur_key ='endpoint.{}.{}'.format(endpoint_servers[customer.pk].pk, str(customer.pk))
                grouped['endpoint'].append((cur_key, str(customer)))  # server overridden in clean()
                result.append((cur_key, str(customer)))

        return result, grouped, enable_tenants

    def get_ldap_tenants(self):
        tenants, grouped, enable_tenants = self.get_tenants()
        return tenants, enable_tenants

    def clean_tenant(self):
        value = self.cleaned_data.get('tenant')

        valid = [l[0] for l in self.get_ldap_tenants()[0]]
        if 'endpoint.' in (value or '') and value in self.get_tenants()[1]['endpoint']:
            return value

        if not self.data.get('multitenant') and self.customer:
            return self.customer.acano_tenant_id or self.customer.pexip_tenant_id

        if len(valid) == 1 or not value:
            return valid[0]

        if value not in valid:
            raise forms.ValidationError(_('Du har inte behörighet för denna tenant'))
        return value

    def clean(self):
        cleaned = self.cleaned_data
        if '.' in (cleaned.get('tenant') or ''):
            server_id, customer_id = cleaned['tenant'].split('.', 2)[1:]
            cleaned['server'] = self.get_server_queryset().get(pk=server_id, customer=customer_id)
            cleaned['tenant'] = 'none'

        if cleaned.get('ts_start') and cleaned.get('ts_stop'):
            if cleaned['ts_start'] > cleaned['ts_stop']:
                raise forms.ValidationError({'ts_stop': 'End time must be after start time'})
        return cleaned

    def get_calls(self):
        calls = self.get_calls_and_legs()[0]
        return calls

    def get_legs(self, populate=True, trim_times=None):
        legs = self.get_calls_and_legs()[1]
        if populate:
            return populate_legs(legs, trim_times=trim_times)
        return legs

    def get_calls_and_legs(self):

        if self.is_valid():
            data = self.cleaned_data
        elif self.data:
            return Call.objects.none(), Leg.objects.none()
        else:
            tenants = self.get_ldap_tenants()[0]
            data = {
                'ts_start': get_prev(),
                'ts_stop': get_latest(),
                'ou': '',
                'tenant': tenants[0][0][0] if tenants else '',
                'cospace': '',
                'member': '',
            }

        if not data.get('server'):
            try:
                data['server'] = self.get_server_queryset()[0]
            except IndexError:
                return Call.objects.none(), Leg.objects.none()

        servers = [data['server']]

        if data['server'].is_combined:
            servers = list(data['server'].combine_servers.all())

        calls = Call.objects.filter(server__in=servers).order_by('ts_start')
        legs = Leg.objects.filter(server__in=servers, should_count_stats=True).order_by('ts_start')

        ts_kwargs = {}
        if data['ts_start']:
            ts_kwargs['ts_stop__gte'] = data['ts_start']
        if data['ts_stop']:
            ts_kwargs['ts_start__lte'] = data['ts_stop']

        calls = calls.filter(**ts_kwargs)
        legs = legs.filter(**ts_kwargs)

        leg_call_filters = Q()

        if not ts_kwargs:
            calls = calls[:100]
            legs = legs[:100]

        if data.get('organization'):
            orgs = data['organization'].get_descendants(include_self=True)

            calls = calls.distinct().filter(
                Q(org_unit__in=orgs) |
                Q(org_unit__isnull=True, cospace_id__in=CoSpaceUnitRelation.objects.filter(unit__in=orgs).values_list('provider_ref')) |
                Q(org_unit__isnull=True, legs__target__in=UserUnitRelation.objects.filter(unit__in=orgs).values_list('user_jid')) |
                Q(org_unit__isnull=True, legs__endpoint__org_unit__in=orgs)
            )

            leg_call_filters &= (
                Q(org_unit__in=orgs) |
                Q(org_unit__isnull=True, call__cospace_id__in=CoSpaceUnitRelation.objects.filter(unit__in=orgs).values_list('provider_ref')) |
                Q(org_unit__isnull=True, target__in=UserUnitRelation.objects.filter(unit__in=orgs).values_list('user_jid')) |
                Q(org_unit__isnull=True, endpoint__org_unit__in=orgs)
            )

        if data.get('cospace'):
            calls = calls.filter(Q(cospace_id=data['cospace']) | Q(cospace__icontains=data['cospace']))
            leg_call_filters &= Q(call__cospace_id=data['cospace']) | Q(call__cospace__icontains=data['cospace'])

        if data['member'] == 'guest':
            calls = calls.distinct().filter(legs__is_guest=True)
            legs = legs.filter(is_guest=True)
        elif data.get('member', '').startswith('='):  # only requested target
            calls = calls.distinct().filter(legs__target=data['member'][1:])
            legs = legs.filter(target__contains=data['member'].lstrip('='))
        elif data['member']:
            calls = calls.distinct().filter(legs__target__contains=data['member'][1:])
            legs = legs.filter(target__contains=data['member'].lstrip('='))

        if data.get('protocol'):
            calls = calls.distinct().filter(legs__protocol=data['protocol'])
            legs = legs.filter(protocol=data['protocol'])

        if data.get('only_gateway'):
            calls = calls.distinct().filter(legs__service_type='gateway')
            legs = legs.filter(service_type='gateway')

        if data.get('endpoints') is not None:
            calls = calls.distinct().filter(legs__endpoint__in=data['endpoints'])
            legs = legs.filter(endpoint__in=data['endpoints'])
        elif data['server'].is_endpoint:
            calls = calls.distinct().filter(legs__endpoint__isnull=False)
            legs = legs.filter(endpoint__isnull=False)

        if data.get('ou'):
            calls = calls.distinct().filter(legs__ou=data['ou'] if data['ou'] != 'default' else '')
            legs = legs.filter(ou=data['ou'] if data['ou'] != 'default' else '')

        ENABLE_UNION = False  # TODO conflicts with values_list/select_related etc
        union_leg_tenants = []  # fetch legs matching tenant filter in call belonging to another tenant

        if not data.get('multitenant'):
            tenants = set()
            if any(s.is_pexip for s in servers) and self.customer.pexip_tenant_id:
                tenants.add(self.customer.pexip_tenant_id)
            if any(s.is_acano for s in servers) and self.customer.acano_tenant_id:
                tenants.add(self.customer.acano_tenant_id)

            if not tenants:
                tenants.add('')
            calls = calls.distinct().filter(legs__tenant__in=tenants)

            if ENABLE_UNION:
                leg_call_filters &= Q(call__tenant__in=tenants)
                union_leg_tenants = tenants
            else:
                leg_call_filters &= Q(call__tenant__in=tenants) | Q(tenant__in=tenants)

        elif data.get('tenant'):
            tenant_id = '' if data['tenant'] == 'none' else data['tenant']
            calls = calls.distinct().filter(legs__tenant=tenant_id)
            if ENABLE_UNION:
                leg_call_filters &= Q(call__tenant=tenant_id)
                union_leg_tenants = [tenant_id]
            else:
                leg_call_filters &= Q(call__tenant=tenant_id) | Q(tenant=tenant_id)

        legs_before_call_filter = legs
        legs = legs.filter(leg_call_filters)

        if ENABLE_UNION and union_leg_tenants:
            union_legs_qs = legs_before_call_filter.exclude(call__tenant__in=union_leg_tenants).filter(tenant__in=union_leg_tenants)
            legs = legs.order_by().union(union_legs_qs.order_by()).order_by('ts_start')

        if data['server'].is_combined or data['server'].type == Server.ENDPOINTS:
            merged_legs, duplicates = merge_duplicate_legs(legs.order_by('ts_start').select_related('call'), default_domain=data['server'].default_domain)
            return calls, merged_legs
        return calls, legs.order_by('ts_start')

