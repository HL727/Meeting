import { singleGet} from '@/vue/helpers/store'

export default {
    state() {
        return {
            users: {},
        }
    },
    actions: {
        singleGet,
        async get({ dispatch }, id) {
            return dispatch('singleGet', `user-pexip/${id}/`)
        },
        async update(context, { id, ...data }) {
            return this.api().patch(`user-pexip/${id}/`, data)
        },
    },
    mutations: {},
    namespaced: true,
}
