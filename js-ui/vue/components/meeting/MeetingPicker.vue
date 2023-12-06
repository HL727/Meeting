<script>
import { $gettext } from '@/vue/helpers/translate'

import { itemListSearchPrefix } from '@/consts'
import AjaxPicker from '@/vue/components/base/AjaxPicker'
import { nowSub } from '@/vue/helpers/datetime'

export default {
    name: 'MeetingPicker',
    inheritAttrs: false,
    props: {
        navigate: { type: Boolean },
    },
    methods: {
        navigateSearchAll(search) {
            this.$router.push({
                name: 'meetings_list',
                query: { ...this.extraParams, cospace_id: itemListSearchPrefix + (search || '') },
            })
        },
        navigateSingle(item) {
            if (!item || !item.id) return
            return this.$router.push(item.details_url)
        },
    },
    render(createElement) {
        const props = {
            placeholder: (this.$attrs.placeholder || $gettext('Välj bokning')) + '...',
            ...this.$attrs,
            ...this.$props,
            returnObject: this.navigate || this.$attrs.returnObject,
            itemText: 'title',
            itemSubtitle: 'ts_start',
            searchUrl: 'meeting/',
            searchQuery: 'title',
            extraParams: {
                ts_start: nowSub({hours: 1}),
            },
        }

        const listeners = !props.navigate
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
