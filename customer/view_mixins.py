import json
from typing import List, TYPE_CHECKING, Dict, Optional

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, Http404
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic.base import ContextMixin
from rest_framework.request import Request
from rest_framework.views import APIView

from customer.utils import get_customers_from_request, get_customer_from_request, set_customer, \
    user_has_all_customers

if TYPE_CHECKING:
    from customer.models import Customer
    from provider.ext_api.base import MCUProvider


class LoginRequiredMixin(View):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        return login_required(view)


class CustomerMixin(ContextMixin, View):
    """
    Customer and api/tenant-permission helpers.
    Make sure to check customer.middleware.* as well for some initialization logic
    """
    request: HttpRequest  # type: ignore[misc]
    _customer: 'Customer'
    _customer_loaded = False
    _customers: List['Customer']
    _api: Dict[bool, 'MCUProvider']

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @property
    def customer(self) -> 'Customer':
        if not self._customer_loaded:
            self._customer = self._get_customer()
            self._customer_loaded = True
        return self._customer

    @customer.setter
    def customer(self, value: 'Customer'):
        self._customer = value

    _has_all_customers_cache = None

    def _has_all_customers(self, request=None) -> bool:

        request = request or self.request
        if not request.user.is_authenticated:
            return False
        if self._has_all_customers_cache is None:
            self._has_all_customers_cache = user_has_all_customers(request.user)
        return self._has_all_customers_cache

    def _has_customer_permission(self, customer):
        customer_id = customer.id if hasattr(customer, 'id') else customer
        return any(c.id == customer_id for c in self._get_customers())

    def _get_customers(self, request=None):

        if not getattr(self, '_customers', None):
            customers = get_customers_from_request(request or self.request)
            self._customers = customers

        return sorted(self._customers, key=lambda x: x.title.lower())

    def _get_customer(self, request=None, customer_id=None):

        return get_customer_from_request(request or self.request, customer_id=customer_id)

    def _set_customer(self, customer):
        set_customer(self.request, customer)

    def _check_tenant_customer(self, tenant_id, do_raise=True, change=False):

        cur_tenant_id = self._get_tenant_id()

        tenant_id = tenant_id or ''

        if cur_tenant_id == tenant_id:
            return self.customer

        for customer in self._get_customers():
            customer_tenants = {customer.acano_tenant_id, customer.pexip_tenant_id}
            if len(customer_tenants) > 1 and '' in customer_tenants:
                customer_tenants = {t for t in customer_tenants if t}  # block standard tenant access

            if tenant_id in customer_tenants:
                if change:
                    self._set_customer(customer)
                return customer

        if do_raise:
            if not (self.request.user.is_staff and self._has_all_customers()):
                raise Http404()

    def _get_api(self, force_reload=False, allow_cached_values=False):
        """
        :rtype: MCUProvider
        """
        cached = getattr(self, '_api', None) or {}
        if cached.get(bool(allow_cached_values)) and not force_reload:
            return cached[bool(allow_cached_values)]

        customer = self._get_customer()
        provider = customer.get_provider()
        if not provider or not (provider.is_acano or provider.is_pexip):
            raise AssertionError('Couldnt get provider for customer')
        api = provider.get_api(customer)
        api.allow_cached_values = allow_cached_values
        self._api = {**cached, bool(allow_cached_values): api}
        return api

    def _get_tenant_id(self, api=None) -> str:
        try:
            api = api or self._get_api()
        except AssertionError:
            customer = self._get_customer()
            return customer.acano_tenant_id or customer.pexip_tenant_id or ''

        return api.get_tenant_id()

    def _check_dynamic_provider_api(self, provider_id=None) -> Optional[str]:
        if provider_id is None:
            provider_id = self.request.GET.get('provider')

        if provider_id and not self._has_all_customers():
            provider = self.customer.get_provider()
            if str(provider.pk) != str(provider_id):
                raise Http404()  # forbidden

        if not provider_id:
            return False
        return provider_id

    def _get_dynamic_provider_api(self, provider_id=None, allow_cached_values=False):
        """
        :rtype: (Provider, MCUProvider, str)
        """
        from provider.models.provider import Provider

        provider_id = self._check_dynamic_provider_api(provider_id=provider_id)
        if not provider_id:
            api = self._get_api(allow_cached_values=allow_cached_values)
            return api.cluster, api, self._get_tenant_id(api)

        provider = get_object_or_404(Provider, pk=provider_id)
        all_customers = [self.customer] + list(self._get_customers())

        valid_customers = [c for c in all_customers if c.lifesize_provider_id == provider.pk]
        if not valid_customers and provider.is_standard:
            valid_customers = [c for c in all_customers if c.lifesize_provider_id is None]

        if valid_customers:
            customer = valid_customers[0]
        else:
            from customer.models import Customer
            customer = self.customer or Customer.objects.first()

        api = provider.get_api(customer, allow_cached_values=allow_cached_values)
        return provider, api, None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.customer
        context['customer'] = customer
        context['customers'] = self._get_customers()
        context['customers_json'] = json.dumps([dict(pk=customer.pk, title=customer.title, acano_tenant_id=customer.acano_tenant_id, pexip_tenant_id=customer.pexip_tenant_id) for customer in self._get_customers()])
        context['epm_hostname'] = settings.EPM_HOSTNAME
        return context


class CustomerAPIMixin(CustomerMixin, APIView):

    request: Request  # type: ignore[misc]

    def get_serializer_context(self):

        context = {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self,
            'customer': self.customer,
        }
        try:
            context.update(super().get_serializer_context())
        except AttributeError:
            pass

        return context
