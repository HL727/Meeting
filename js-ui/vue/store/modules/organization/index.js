import { buildTree } from '@/vue/helpers/tree'
import Vue from 'vue'

export default {
    state() {
        return {
            units: {},
            lastLoaded: null,
        }
    },

    getters: {
        units(state) {
            return state.units
        },
        all(state) {
            return Object.values(state.units).sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
        },
        tree(state) {
            return buildTree(Object.values(state.units).sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase())))
        },
    },
    actions: {
        async refreshUnits({ dispatch, state }) {

            if (!state.lastLoaded || state.lastLoaded < new Date().getTime() - 30 * 1000) {
                return await dispatch('getUnits')
            }
            return Object.values(state.units)
        },
        async getUnits({ commit }) {
            const response = await this.api().get('/organizationunit/')

            commit('setLastLoaded', new Date().getTime())
            commit('setOrganizations', response)
        },
        async getUnit(context, id) {
            return await this.api().get(`/organizationunit/${id}/`)
        },
        async addUnit({ commit }, unitData) {
            const response = await this.api().post('/organizationunit/', unitData)
            commit('updateUnit', response)
        },
        async updateUnit({ commit }, unitData) {
            const response = await this.api().patch(`/organizationunit/${unitData.id}/`, unitData)
            commit('updateUnit', response)
        },
        async deleteUnit({ commit }, id) {
            await this.api().delete(`/organizationunit/${id}/`)
            commit('deleteUnit', id)
        },
    },
    mutations: {
        setOrganizations(state, units) {
            const result = {}
            units.forEach(b => (result[b.id] = b))
            state.units = result
        },
        updateUnit(state, unit) {
            Vue.set(state.units, unit.id, unit)
        },
        deleteUnit(state, id) {
            Vue.delete(state.units, id)
        },
        setLastLoaded(state, ts) {
            state.lastLoaded = ts
        }
    },
    namespaced: true,
}
