<script>
import { $gettext } from '@/vue/helpers/translate'

import TreeViewPicker from '@/vue/components/tree/TreeViewPicker'
import GroupTree from './GroupTree'

export default {
    name: 'GroupPicker',
    functional: true,
    props: {
        itemText: { type: String, default: 'title' },
        label: { type: String, default: $gettext('Välj grupp') },
    },
    render(createElement, context) {
        const props = {
            ...context.props,
            treeComponent: GroupTree,
        }
        return createElement(TreeViewPicker, { ...context.data, props }, context.children)
    },
}
</script>
