import Vue from 'vue'
import { idMap } from '@/vue/helpers/store'

export default {
    state() {
        return {
            endpointStatus: {},
        }
    },
    actions: {
        async getStats(context, { url = '/call_statistics/', ...params }) {
            return this.api().get(url, { params: params })
        },
        async getHeadCountStats(context, params) {
            return this.api().get('room_statistics/head_count/', { params: params })
        },
        async getStatsDebug(context, { url = '/call_statistics/debug/', ...params }) {
            return this.api().get(url, { params: params })
        },
        async getStatsSettings(context, params) {
            return this.api().get('call_statistics/settings/', { params: { ...params } })
        },
        async getEPMStatsSettings(context, params) {
            return this.api().get('room_statistics/settings/', { params: { ...params } })
        },
        async getEndpointStatuses({ commit }, params) {
            const response = await this.api().get('room_statistics/endpoint_status/', { params: { ...params } })
            commit('setEndpointStatuses', response)
            return response
        },
    },
    mutations: {
        setGraphs(state, d) {
            state.graphs = Object.freeze({ ...d })
        },
        setData(state, d) {
            state.data = Object.freeze({ ...d, graphs: undefined })
        },
        updateLimits(state, limits) {
            Vue.set(state, 'limits', limits)
        },
        setEndpointStatuses(state, statuses) {
            state.endpointStatus = idMap(statuses, 'endpoint')
        },
    },
    namespaced: true,
}
