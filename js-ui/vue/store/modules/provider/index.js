import { idMap } from '@/vue/helpers/store'

export default {
    state() {
        return {
            clusters: {},
            providers: {},
            ewsCredentials: {},
            msGraphCredentials: {},
        }
    },
    actions: {
        async getClusters({ commit }, params) {
            const response = await this.api().get('cluster/', { params })
            commit('setClusters', response)
            return response
        },
        async getProviders({ commit }, params) {
            const response = await this.api().get('provider/', { params })
            commit('setProviders', response)
            return response
        },
        async getExchangeCredentials({ commit }, params) {
            const response = await this.api().get('ews_credentials/', { params })
            commit('setExchangeCredentials', response)
            return response
        },
        async syncExchangeCredentials(context, id) {
            return await this.api().post(`ews_credentials/${id}/sync/`)
        },
        async syncMSGraphCredentials(context, id) {
            return await this.api().post(`msgraph_credentials/${id}/sync/`)
        },
        async getMSGraphCredentials({ commit }, params) {
            const response = await this.api().get('msgraph_credentials/', { params })
            commit('setMSGraphCredentials', response)
            return response
        },
    },
    mutations: {
        setClusters(state, clusters) {
            state.clusters = idMap(clusters)
        },
        setProviders(state, providers) {
            state.providers = idMap(providers)
        },
        setExchangeCredentials(state, credentials) {
            state.ewsCredentials = idMap(credentials)
        },
        setMSGraphCredentials(state, credentials) {
            state.msGraphCredentials = idMap(credentials)
        }
    },
    namespaced: true,
}
