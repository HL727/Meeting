import { idMap } from '@/vue/helpers/store'
import Vue from 'vue'

export default {
    state() {
        return {
            calls: {},
            participants: {},
        }
    },
    getters: {
        callParticipants(state) {
            const callParticipant = {}
            Object.values(state.participants).forEach(part => {
                if (
                    !part.remote ||
                    part.remote.indexOf('app:conf:chat:id') !== -1 ||
                    part.remote.indexOf('app:conf:applicationsharing:id') !== -1 ||
                    part.remote.indexOf('app:conf:focus:id') !== -1) {
                    return
                }
                if (!callParticipant[part.call]) callParticipant[part.call] = []
                callParticipant[part.call].push(part)
            })
            return callParticipant
        },
    },
    actions: {
        async dial(context, { callId, data }) {
            // TODO 500 error
            return await this.api().post('call_legs/', {
                ...data,
                call_id: callId
            })
        },
        async muteAudioForAllParticipants(context, { callId, value }) {
            return await this.api().post(`calls/${callId}/set_all_mute/`, { value: value })
        },
        async muteVideoForAllParticipants(context, { callId, value }) {
            return await this.api().post(`calls/${callId}/set_all_video_mute/`, { value: value })
        },
        async getCallStatus({ dispatch }, { callId, ...params }) {
            return dispatch('getCallData', { callId, compact: true, ...params })
        },
        async getCallData({ commit }, { callId, compact=false, ...params }) {
            try {
                const response = await this.api().get(`calls/${callId}/${compact ? 'status/' : ''}`, { params })
                commit('updateCall', { ...response, _extended: !compact })
                if (response.legs) {
                    commit('clearCallParticipants', callId)
                    commit(
                        'updateParticipants',
                        response.legs.map(part => ({ ...part, call: callId }))
                    )
                }
                return response
            } catch (e) {
                commit('deleteCall', callId)
                commit('clearCallParticipants', callId)
                throw e
            }
        },
        async hangup({ commit }, { callId, ...params }) {
            const response = await this.api().delete(`calls/${callId}/`, { params })
            commit('deleteCall', response)
            return response
        },
        async getCalls({ commit }, params) {
            const response = await this.api().get('calls/', { params })
            commit('updateCalls', response.results)
            return response
        },
        async getCallParticipants({ commit }, { callId, ...params }) {
            const response = await this.api().get(`calls/${callId}/legs/`, { params })
            commit('clearCallParticipants', callId)
            commit(
                'updateParticipants',
                response.map(part => ({ ...part, call: callId }))
            )
            return response
        },
        async getParticipants({ commit }, params) {
            const response = await this.api().get('call_legs/', { params })
            commit('updateParticipants', response.results)
            return response
        },
        async getParticipant({ commit }, legId) {
            const response = await this.api().get(`call_legs/${legId}/`, { full: 1 })
            commit('updateParticipants', [response.results])
            return response
        },
        async hangupParticipant({ commit }, { id, ...params }) {
            const response = await this.api().delete(`call_legs/${id}/`, { params })
            commit('deleteParticipant', id)
            return response
        },
        async muteAudioParticipant({ commit }, { id, value, ...params }) {
            const response = await this.api().post(`call_legs/${id}/set_mute/`, { value }, { params })

            commit('updateParticipant', response)
            return response
        },
        async muteVideoParticipant({ commit }, { id, value, ...params }) {
            const response = await this.api().post(`call_legs/${id}/set_video_mute/`, { value }, { params })
            commit('updateParticipant', response)
            return response
        },
        async makeParticipantModerator({ commit }, { id, value, ...params }) {
            const response = await this.api().post(`call_legs/${id}/set_moderator/`, { value }, { params })

            commit('updateParticipant', response)
            return response
        },
    },
    mutations: {
        updateCalls(state, calls) {
            state.calls = { ...state.calls, ...idMap(calls) }
        },
        deleteCall(state, callId) {
            Vue.delete(state.calls, callId)
        },
        updateCall(state, call) {
            const existing = state.calls[call.id]

            if (!call._extended && existing) {
                Vue.set(state.calls, call.id, { ...existing, ...call, _extended:  existing._extended || call._extended })
            } else {
                Vue.set(state.calls, call.id, call)
            }
        },
        clearCallParticipants(state, callId) {
            Object.values(state.participants).forEach(p => {
                if (p.call === callId) {
                    Vue.delete(state.participants, p.id)
                }
            })
        },
        updateParticipants(state, participants) {
            participants.forEach(part => {
                Vue.set(state.participants, part.id, part)
            })
        },
        updateParticipant(state, participant) {
            const existing = state.participants[participant.id]
            if (existing && existing.call) {
                participant.call = existing.call
            }
            Vue.set(state.participants, participant.id, participant)
        },
        deleteParticipant(state, id) {
            Vue.delete(state.participants, id)
        },
    },
    namespaced: true,
}
