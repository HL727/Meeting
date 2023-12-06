import Vue from 'vue'
import Vuetify from 'vuetify/lib'
import VDataFooter from 'vuetify/lib/components/VDataIterator/VDataFooter'
import './scss/vuerify-extend.scss'
import VDataTablePaginated from '@/vue/components/base/VDataTablePaginated'

Vue.use(Vuetify)

Vue.component('VDataTablePaginated', VDataTablePaginated)

try {
    VDataFooter.options.props.itemsPerPageOptions.default = () => [5, 10, 20, 50, 100, -1]
} catch (e) {
    // eslint-disable-next-line no-console
    console.log('Could not override datatable page item options')
}

const theme = window.MIVIDAS && window.MIVIDAS.themes ? {
    theme: {
        themes: window.MIVIDAS.themes,
    }
} : undefined

export default new Vuetify({
    ...theme,
    icons: {
        iconfont: 'mdi', // 'mdi' || 'mdiSvg' || 'md' || 'fa' || 'fa4'
        values: {
            search: 'mdi-magnify',
        },
    },
})
