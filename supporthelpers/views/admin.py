from collections import defaultdict

from django.views.generic import TemplateView
from django.shortcuts import redirect

from ..forms import TenantForm, TenantSyncForm

from django.http import HttpResponse
from django.db.models import Q

from customer.models import Customer, CustomerKey
from provider.exceptions import ResponseError, NotFound
import urllib.request, urllib.parse, urllib.error

from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class TenantView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'supporthelpers/tenants.html'

    ad_base = '(&(objectCategory=person)(objectClass=user)(!(cn=admin))(!(cn=acano))(!(cn=Guest))(!(cn=krbtgt))(!(cn=Gäst))(%s))'

    ivr_files = '''
    ivr_background.jpg
    ivr_id_entry.wav
    ivr_id_incorrect_final_attempt.wav
    ivr_id_incorrect_goodbye.wav
    ivr_id_incorrect_try_again.wav
    ivr_timeout.wav
    ivr_welcome.wav
    '''

    call_files = '''
    background.jpg
    call_join_confirmation.wav
    call_join.wav
    call_outgoing_welcome.wav
    cospace_join_confirmation.wav
    cospace_join.wav
    cospace_outgoing_welcome.wav
    disconnected.wav
    meeting_ended.wav
    only_participant.wav
    passcode_entry.wav
    passcode_incorrect_final_attempt.wav
    passcode_incorrect_goodbye.wav
    passcode_incorrect_try_again.wav
    timeout.wav
    waiting_for_host.wav
    welcome.wav
    '''

    _key_cache = None
    sync_form: TenantSyncForm = None

    def _get_keys(self):
        if self._key_cache:
            return self._key_cache

        keys = defaultdict(list)
        keys[None] = list(CustomerKey.objects.filter(active=True).exclude(customer__acano_tenant_id='').values_list('shared_key', flat=True))

        for tenant_id, key in CustomerKey.objects.filter(active=True).exclude(customer__acano_tenant_id='').values_list('customer__acano_tenant_id', 'shared_key'):
            keys[tenant_id].append(key)

        self._key_cache = keys
        return keys

    def get_ou_query(self, tenant_id=None):

        keys = self._get_keys()[tenant_id or None][:]

        ad_base = self.ad_base

        if tenant_id:
            if not keys:
                keys = ['test']
            neg = '!(|%s)' % ''.join('(ou=%s)' % ou for ou in keys if ou and '.' not in ou)
            return ad_base % neg
        else:
            if not keys:
                keys = ['NO_CUSTOMER']
            join = '|%s' % ''.join('(ou=%s)' % ou for ou in sorted(keys) if ou and '.' not in ou)
            return ad_base % join

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)
        assert provider.is_acano

        context['form'] = getattr(self, 'form', None) or TenantForm(api)

        if api:
            from datastore.models.customer import Tenant
            tenants = [t.to_dict() for t in Tenant.objects.filter(provider=api.cluster, is_active=True)]

            if self.request.GET.get('q'):
                q = self.request.GET['q']
                tenants = [t for t in tenants if q in t['name'].lower()]

            ldapsources = {s.get('tenant', ''): s for s in context['form'].get_ldap_sources().sources}

            all_customers = list(Customer.objects
                                 .filter(Q(lifesize_provider=api.cluster) | Q(lifesize_provider__isnull=True))
                                 .prefetch_related('lifesize_provider'))

            tenant_customers = []
            for t in tenants:
                customers = [c for c in all_customers if c.acano_tenant_id == t['id'] and c.get_provider() == api.cluster]

                source = ldapsources.pop(t['id'], {})
                tenant_customers.append((t, customers, self.get_ou_query(t['id']), source))

            context['tenants'] = tenant_customers

            callbrandings = api.get_callbrandings()
            ivrbrandings = api.get_ivrbrandings()

            context['callbrandings'] = callbrandings
            context['ivrbrandings'] = ivrbrandings
            context['ldapsources'] = list(ldapsources.values())
            context['systemprofiles'] = api.get_systemprofiles()

        context['default_ad'] = self.get_ou_query()
        context['sync_form'] = getattr(self, 'sync_form', None) or TenantSyncForm(prefix='sync')
        return context

    def _update_callbranding_profile(self, request):
        return HttpResponse('TODO') # TODO

        id = request.POST.get('id')
        field = request.POST.get('type')

        location = request.POST.get('location')
        invite = request.POST.get('invite')

        assert id and location
        assert field in ('callbranding', 'invite')

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)

        api.update_callbranding(id=id, location=location, invite=invite)

    def _remove(self, request):

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)

        def _try_delete(prefix, ids):
            for guid in ids:
                try:
                    api.delete('{}/{}'.format(prefix, guid))
                except NotFound:
                    pass

        _try_delete('tenants', request.POST.getlist('tenant'))
        _try_delete('callBrandingProfiles', request.POST.getlist('callbranding'))
        _try_delete('ivrBrandingProfiles', request.POST.getlist('ivrbranding'))
        _try_delete('ldapSources', request.POST.getlist('ldapsource'))

        return redirect(request.get_full_path())

    def post(self, request, *args, **kwargs):

        from provider.ext_api.acano import AcanoAPI

        api: AcanoAPI

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)
        if not provider.is_acano:
            raise AssertionError('Not CMS server')

        if request.POST.get('post_action') == 'remove':
            return self._remove(request)
        if request.POST.get('post_action') == 'sync':
            self.sync_form = TenantSyncForm(request.POST, prefix='sync')
            if self.sync_form.is_valid():
                name_conflict = self.sync_form.cleaned_data.get('name_conflict')
                api.sync_tenant_customers(name_conflict=name_conflict)
            return self.get(request, *args, **kwargs)

        elif request.POST.get('post_action') == 'update_callbranding':
            return self._update_callbranding_profile(request)

        form = TenantForm(api, request.POST)

        if form.is_valid():
            form.save()
            return redirect(request.get_full_path())

        self.form = form
        return self.get(request, *args, **kwargs)

