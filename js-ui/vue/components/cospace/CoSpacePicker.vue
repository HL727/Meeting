<script>
import { itemListSearchPrefix } from '@/consts'
import AjaxPicker from '@/vue/components/base/AjaxPicker'
import { normalizeProps } from '@/vue/helpers/vue'

export default {
    name: 'CoSpacePicker',
    inheritAttrs: false,
    props: {
        navigate: { type: Boolean },
    },
    methods: {
        navigateSearchAll(search) {
            this.$router.push({
                name: 'cospaces_list',
                query: { ...this.extraParams, cospace_id: itemListSearchPrefix + (search || '') },
            })
        },
        navigateSingle(item) {
            if (!item || !item.id) return
            return this.$router.push({ name: 'cospaces_details', params: { id: item.id } })
        },
    },
    render(createElement) {
        const attrs = normalizeProps(this.$attrs)
        const props = {
            label: attrs.label || '',
            returnObject: this.navigate || attrs.returnObject,
            itemText: 'name',
            itemSubtitle: 'uri',
            searchUrl: 'cospace/',
            ...attrs,
        }

        const listeners = !this.navigate
            ? this.$listeners
            : {
                input: this.navigateSingle.bind(this),
                'search-all': this.navigateSearchAll.bind(this),
                ...this.$listeners,
            }
        return createElement(AjaxPicker, { props, on: listeners }, this.$children)
    },
}
</script>
