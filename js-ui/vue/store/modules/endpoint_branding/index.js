import Vue from 'vue'
import { idMap } from '@/vue/helpers/store'

export default {
    state() {
        return {
            profiles: {},
            types: {},
        }
    },
    actions: {
        async loadProfiles({ commit }) {
            const response = await this.api().get('endpointbranding/')
            commit('setProfiles', response)
            return response
        },
        async loadFileTypes({ commit }) {
            const response = await this.api().get('endpointbranding/types/')
            commit('setTypes', response)
            return response
        },
        async getProfile({ commit }, id) {
            const response = await this.api().get(`endpointbranding/${id}/`)
            commit('updateProfile', response)
            return response
        },
        async createProfile({ commit }, profile) {
            const response = await this.api().post('endpointbranding/', profile)
            commit('updateProfile', response)
            return response
        },
        async updateProfile({ commit }, { id, ...profile }) {
            const response = await this.api().patch(`endpointbranding/${id}/`, profile)
            commit('updateProfile', response)
            return response
        },
        async removeProfile({ dispatch }, id) {
            const response = await this.api().delete(`endpointbranding/${id}/`)
            dispatch('loadProfiles')
            return response
        },
    },
    mutations: {
        setProfiles(state, profiles) {
            state.profiles = idMap(profiles)
        },
        updateProfile(state, profile) {
            Vue.set(state.profiles, profile.id, profile)
        },
        setTypes(state, types) {
            state.types = idMap(types)
        },
    },
    namespaced: true,
}
