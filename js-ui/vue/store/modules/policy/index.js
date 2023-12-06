import { idMap } from '@/vue/helpers/store'

export default {
    state() {
        return {
            limits: {},
            usage: {},
        }
    },
    getters: {
        limits(state) {
            return Object.values(state.limits)
        },
        customerUsage(state) {
            const result = {}
            Object.values(state.usage).forEach(limit => {
                if (!result[limit.customer]) result[limit.customer] = {}
                result[limit.customer][limit.cluster] = limit
            })
            return result
        },
        clusterUsage(state) {
            const result = {}
            Object.values(state.usage).forEach(limit => {
                if (!result[limit.cluster]) result[limit.cluster] = {}
                result[limit.cluster][limit.customer] = limit
            })
            return result
        },
    },
    actions: {
        async getCustomerLimits({commit}) {
            const response = await this.api().get('customer_policy/')
            commit('setLimits', response)
            return response
        },
        async getCustomerUsage({commit}) {
            const response = await this.api().get('customer_policy_state/')
            commit('setUsage', response)
            return response
        },
    },
    mutations: {
        setLimits(state, limits) {
            state.limits = idMap(limits, 'id')
        },
        setUsage(state, usages) {
            state.usage = idMap(usages, 'id')
        },
    },
    namespaced: true,
}
