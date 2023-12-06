import { singleGet} from '@/vue/helpers/store'

export default {
    state() {
        return {
            cospaces: {},
        }
    },
    actions: {
        singleGet,
        async get({ dispatch }, id) {
            return dispatch('singleGet', `cospace-pexip/${id}/`)
        },
        async update(context, cospace) {
            return this.api().patch(`cospace-pexip/${cospace.id}/`, cospace)
        },
        async delete(context, id) {
            return this.api().delete(`cospace-pexip/${id}/`)
        },
        async create(context, cospace) {
            return this.api().post('cospace-pexip/', cospace)
        },
        async bulkCreate(context, cospaces) {
            return this.api().post('cospace-pexip/bulk_create/', cospaces)
        },
    },
    mutations: {},
    namespaced: true,
}
