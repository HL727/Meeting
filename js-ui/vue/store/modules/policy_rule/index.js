import { idMap } from '@/vue/helpers/store'
import Vue from 'vue'
import { replaceQuery } from '@/vue/helpers/url'

export default {
    state() {
        return {
            related: {},
            rules: {},
        }
    },
    actions: {
        async getRelatedObjects({ commit }, { provider }) {
            const result = await this.api().get(replaceQuery('provider/related_policy_objects/', { provider }))
            commit('setRelatedObjects', result)
            return result
        },
        async createPolicyRule({ commit }, { provider, ...data }) {
            const result = await this.api().post(replaceQuery('policy_rule/', { provider }), data)
            commit('updateRule', result)
            return result
        },
        async updatePolicyRule({ commit }, { id, data, provider }) {
            const result = await this.api().patch(replaceQuery(`policy_rule/${id}/`, { provider }), data)
            commit('updateRule', result)
            return result
        },
        async deletePolicyRule({ commit }, { id, provider }) {
            const result = await this.api().delete(replaceQuery(`policy_rule/${id}/`, { provider }))
            commit('deleteRule', result)
            return result
        },
        async getPolicyRule({ commit }, { id, provider }) {
            const result = await this.api().get(replaceQuery(`policy_rule/${id}/`, { provider }))
            commit('updateRule', result)
            return result
        },
        async getRules({ commit }, { provider }) {
            const result = await this.api().get(replaceQuery('policy_rule/', { provider }))
            commit('setRules', result)
            return result
        },
        async syncRules({ commit }, { provider }) {
            const result = await this.api().post(replaceQuery('policy_rule/sync/', { provider }))
            commit('setRules', result)
            return result
        },
        async trace(context, data) {
            return this.api().post('policy_rule/trace/', data)
        },
    },
    mutations: {
        setRelatedObjects(state, objects) {
            state.related = objects
        },
        setRules(state, rules) {
            state.rules = idMap(rules)
        },
        deleteRule(state, id) {
            Vue.delete(state.rules, parseInt(id, 10))
        },
        updateRule(state, rule) {
            Vue.set(state.rules, parseInt(rule.id, 10), rule)
        },
    },
    namespaced: true,
}
