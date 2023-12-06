import { singleGet } from '@/vue/helpers/store'
import { replaceQuery } from '@/vue/helpers/url'

export default {
    actions: {
        singleGet,
        async search({ dispatch }, params) {
            return dispatch('singleGet', replaceQuery('meeting/', params))
        },
    },
    mutations: {},
    namespaced: true,
}
