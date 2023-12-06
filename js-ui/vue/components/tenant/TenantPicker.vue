<script>
import { $gettext } from '@/vue/helpers/translate'

import CustomerPicker from './CustomerPicker'
import { normalizeProps } from '@/vue/helpers/vue'

export default {
    name: 'TenantPicker',
    inheritAttrs: false,

    render(createElement) {
        const attrs = normalizeProps(this.$attrs)
        const props = {
            itemValue: attrs.tenantField || $gettext('acano_tenant_id'),
            onlyWithTenant: true,
            providerId: attrs.providerId,
            ...attrs,
            ...this.$props,
        }

        return createElement(CustomerPicker, { props, attrs: props, on: this.$listeners }, this.$children)
    },
}
</script>
