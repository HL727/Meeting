<script>
import TreeViewPicker from '@/vue/components/tree/TreeViewPicker'
import OrganizationTree from '@/vue/components/organization/OrganizationTree'
import { normalizeProps } from '@/vue/helpers/vue'

export default {
    name: 'OrganizationPicker',
    inheritAttrs: false,

    computed: {
        organizations() {
            return this.$store.getters['organization/tree']
        },
    },
    mounted() {
        if (this.$attrs.value) {
            this.$store.dispatch('organization/refreshUnits')
        }
    },
    render(createElement) {
        const attrs = normalizeProps(this.$attrs)

        const props = {
            label: this.$attrs.label || '',
            treeComponent: OrganizationTree,
            itemText: 'name',
            items: this.organizations,
            ...attrs,
            ...this.$props,
        }
        return createElement(TreeViewPicker, { props, attrs: props, on: this.$listeners }, this.$children)
    },
}
</script>
