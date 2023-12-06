<script>

import { VDataTable } from 'vuetify/lib'

const defaultItemsPerPageOptions = [5, 10, 20, 50, 100]

export function extendFooterProps(attrs) {
    return {
        itemsPerPageOptions: defaultItemsPerPageOptions,
        ...attrs,
    }
}


export default VDataTable.extend({
    name: 'v-data-table-paginated',
    props: {
        footerProps: {
            type: Object,
            default: extendFooterProps,
        },
        itemsPerPage: {
            type: Number,
            default: 20,
        }
    },
    defaultItemsPerPageOptions: defaultItemsPerPageOptions,
})
</script>
