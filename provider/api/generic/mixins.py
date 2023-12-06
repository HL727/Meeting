from customer.view_mixins import CustomerAPIMixin


class DynamicAPIMixin(CustomerAPIMixin):

    def _get_api(self, force_reload=False, allow_cached_values=True):
        """
        :rtype: provider.ext_api.base.CallControlProvider
        """
        if not self.request.GET.get('provider'):
            return super()._get_api(force_reload=force_reload, allow_cached_values=allow_cached_values)

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=allow_cached_values)
        return api
