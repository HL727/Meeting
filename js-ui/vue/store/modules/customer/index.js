import { idMap } from '@/vue/helpers/store'

export default {
    state() {
        return {
            customers: {},
        }
    },
    actions: {
        async getCustomers({ commit }) {
            const response = await this.api().get('customer/')
            commit('setCustomers', response)
            return response
        },
    },
    mutations: {
        setCustomers(state, customers) {
            state.customers = idMap(customers)
        },
    },
    namespaced: true,
}
