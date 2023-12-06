export default {
    state() {
        return {}
    },
    actions: {
        async getData(context, { module, params }) {
            return await this.api().get(`debug/${module}/`, { params: { ...params } })
        },
    },
    mutations: {},
    namespaced: true,
}
