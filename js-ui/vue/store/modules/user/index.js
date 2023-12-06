import { singleGet } from '@/vue/helpers/store'
import { replaceQuery } from '@/vue/helpers/url'

export default {
    actions: {
        singleGet,
        async search({ dispatch }, params) {
            return dispatch('singleGet', replaceQuery('user/', { ...params, q: params.search }))
        },
        async get(context, id) {
            return await this.api().get(`user/${id}/`)
        },
        async sync(context, providerId) {
            return await this.api().post(`provider/${providerId}/sync_ldap/`)
        },
        async sendInvite(context, { userId, subject }) {
            return await this.api().post(`user/${userId}/invite/`, { subject })
        },
        async setOrganizationUnit(context, { userIds, unitPath, unitId }) {
            const data = {
                ids: userIds,
                organization_path: unitPath,
                organization_unit: unitId,
            }
            return await this.api().patch('user/set-organization-unit/', data)
        },
    },
    mutations: {},
    namespaced: true,
}
