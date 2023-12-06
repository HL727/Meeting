import * as QS from 'query-string'
import { singleGet } from '@/vue/helpers/store'
import { replaceQuery } from '@/vue/helpers/url'

export default {
    actions: {
        singleGet,
        async create(context, form) {
            return this.api().post('cospace-acano/', form)
        },
        async update(context, { id, ...form }) {
            return this.api().patch(`cospace-acano/${id}/`, form)
        },
        get({ dispatch }, id) {
            return dispatch('singleGet', `cospace-acano/${id}/`)
        },
        async search({ dispatch }, params) {
            return dispatch('singleGet', replaceQuery('cospace/', { ...params, q: params?.search }))
        },
        async sendInvite(context, { cospaceId, subject }) {
            return this.api().post(`cospace/${cospaceId}/invite/`, { subject })
        },
        async bulkCreate(context, bulkData) {
            return this.api().post('cospace-acano/bulk_create/', bulkData)

        },
        async remove(context, cospaces) {
            return this.api().delete('cospace/', {
                params: { cospaces },
            })
        },
        async setOrganizationUnit(context, { cospaceIds, unitPath, unitId }) {
            return await this.api().patch(
                'cospace/set-organization-unit/',
                QS.stringify({
                    ids: cospaceIds,
                    organization_path: unitPath,
                    organization_unit: unitId,
                }),
                {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                }
            )
        },
        async setCustomer(context, { cospaceIds, tenantId }) {
            return this.api().patch(
                'cospace/set-tenant/',
                QS.stringify({ ids: cospaceIds, tenant: tenantId }),
                {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                }
            )
        },
    },
    mutations: {},
    namespaced: true,
}
