<script>
import { $gettext } from '@/vue/helpers/translate'

import AjaxPicker from '@/vue/components/base/AjaxPicker'
import { replaceQuery } from '@/vue/helpers/url'
import { idMap } from '@/vue/helpers/store'

import { normalizeProps } from '@/vue/helpers/vue'

export default {
    name: 'CustomerPicker',
    inheritAttrs: false,
    props: {
        navigate: { type: Boolean },
        onlyWithTenant: { type: Boolean },
        providerId: { type: Number, required: false, default: null },
        tenantField: { type: String, default: 'acano_tenant_id' },
        queries: { type: Object, default: () => ({}) },
        settingsLink: { type: Boolean },
    },
    computed: {
        items() {
            const result = Object.values(this.$store.state.site.customers)
                .map(c => {

                    const result = {
                        acano_tenant_text: !c.acano_tenant_id
                            ? ''
                            : `CMS-tenant (${c.acano_tenant_id.substr(0, 8)})...`,
                        pexip_tenant_text: !c.pexip_tenant_id
                            ? ''
                            : `Pexip-tenant (${c.pexip_tenant_id.substr(0, 8)}...`,
                    }

                    const tenantField = this.tenantField ? this.tenantField.replace('_id', '_text') : null
                    return {
                        ...c,
                        ...result,
                        tenant_text: (tenantField && result[tenantField]) || result.pexip_tenant_text || result.acano_tenant_text,
                    }
                })
                .sort((a, b) => a.title.toString().localeCompare(b.title))

            if (this.providerId) {
                return result.filter(c => c.provider === this.providerId)
            }

            if (!this.onlyWithTenant || result.length <= 1) {
                return result
            }

            const tenantMap = idMap(result, this.tenantField)

            const def = { [this.$attrs.itemValue || 'id']: '', ...result[''], title: $gettext('Standardtenant') }
            if (tenantMap['']) {
                delete tenantMap['']
                return [def, ...Object.values(tenantMap)]
            }
            return Object.values(tenantMap)
        },
        customer() {
            return this.$store.state.site.customers[this.$store.state.site.customerId]
        },
    },
    methods: {
        navigateSingle(item) {
            if (!item || !item.id) return

            location.href = replaceQuery(location.href, { customer: item.id, check_customer: 1 })
        },
    },
    render(createElement) {
        const attrs = normalizeProps(this.$attrs)
        const extraListeners = {}

        if (this.settingsLink) {
            attrs.appendOuterIcon = 'mdi-settings'
            extraListeners['click:append-outer'] = () => {
                window.open(`/admin/provider/customer/${this.customer.id}/change/`)
            }
        }

        const props = {
            value: this.customer,
            label: attrs.label || '',
            localItems: this.items,
            returnObject: this.navigate || attrs.returnObject,
            itemText: 'title',
            itemSubtitle: 'tenant_text',
            itemValue: attrs.itemValue || 'id',
            searchUrl: '',
            inputAttrs: { ...attrs, noFilter: false },
            ...attrs,
        }

        const listeners = !this.navigate
            ? {
                ...this.$listeners,
                ...extraListeners,
            }
            : {
                input: this.navigateSingle.bind(this),
                ...this.$listeners,
                ...extraListeners,
            }
        return createElement(AjaxPicker, { props, on: listeners }, this.$children)
    },
}
</script>
