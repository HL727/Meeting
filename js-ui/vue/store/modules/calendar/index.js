import { idMap } from '@/vue/helpers/store'

export default {
    state() {
        return {
            calendars: {},
        }
    },
    actions: {
        async getCalendars({ commit }, params) {
            const response = await this.api().get('ews_calendar/', { params })
            commit('setCalendars', response)
            return response
        },
    },
    mutations: {
        setCalendars(state, calendars) {
            state.calendars = idMap(calendars)
        },
    },
    namespaced: true,
}
