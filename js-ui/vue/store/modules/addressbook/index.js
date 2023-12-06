import { buildTree } from '@/vue/helpers/tree'
import { idMap } from '@/vue/helpers/store'
import Vue from 'vue'
import { baseURL } from '@/consts'

export default {
    state() {
        return {
            books: {},
            groups: {},
            items: {},
            sources: {},
            providers: {},
        }
    },

    getters: {
        addressBooks(state) {
            return Object.values(state.books)
        },
        groupTrees(state) {
            const result = {}
            for (let k in state.groups) {
                result[k] = buildTree(Object.values(state.groups[k]))
            }
            return result
        },
    },
    actions: {
        async getAddressBooks({ commit }) {
            const response = await this.api().get('/addressbook/')

            commit('setAddressBooks', response)
        },
        async getProviders({ commit }) {
            const response = await this.api().get('/addressbook/providers/')

            commit('setProviders', response)
            return response
        },
        async createAddressBook({ dispatch }, data) {
            const response = await this.api().post('/addressbook/', data)
            await dispatch('handleAddressBookResponse', response)
            return response
        },

        async getAddressBook({ dispatch }, addressBookId) {
            const response = await this.api().get(`/addressbook/${addressBookId}/`)
            await dispatch('handleAddressBookResponse', response)
            return response
        },
        async updateAddressBook({ dispatch }, { id, data }) {
            const response = await this.api().patch(`/addressbook/${id}/`, data)
            await dispatch('handleAddressBookResponse', response)
            return response
        },
        async getAddressBookItems({ commit }, addressBookId) {
            const response = await this.api().get(`/addressbook/${addressBookId}/items/`)

            commit('setAddressBookItems', { addressBookId, items: response })
        },
        async getAddressBookEditableItems({ commit }, addressBookId) {
            const response = await this.api().get(`/addressbook/${addressBookId}/editable_items/`)

            commit('setAddressBookItems', { addressBookId, items: response })
        },
        async deleteAddressBook({ commit }, addressBookId) {
            await this.api().delete(`/addressbook/${addressBookId}/`)

            commit('deleteAddressBook', addressBookId)
        },
        async checkLinkedAddressbook(context, addressBookId) {
            return await this.api().get(`/addressbook/${addressBookId}/source_links/`)
        },
        handleAddressBookResponse({ commit }, response) {
            const addressBookId = response.id

            commit('updateAddressBook', response)
            commit('setGroups', { addressBookId, groups: response.groups })
            commit('setSources', { addressBookId, sources: response.sources })
        },
        async addSource({ dispatch }, { addressBookId, form }) {
            const response = await this.api().post(`/addressbook/${addressBookId}/source/`, form)
            await dispatch('handleAddressBookResponse', response)
        },
        async deleteSource({ dispatch }, { addressBookId, sourceId }) {
            const response = await this.api().post(`/addressbook/${addressBookId}/remove_source/`, {
                id: sourceId,
            })

            await dispatch('handleAddressBookResponse', response)
        },
        async copyAddressBook({ dispatch }, { addressBookId, form }) {
            const response = await this.api().post(`/addressbook/${addressBookId}/copy/`, form)
            await dispatch('handleAddressBookResponse', response)
            return response
        },
        async getGroup(context, id) {
            return this.api().get(`/addressbook_group/${id}/`)
        },
        async addGroup({ commit }, form) {
            const response = await this.api().post('/addressbook_group/', form)
            commit('updateGroup', response)
            return response
        },
        export(context, id) {
            const url = `${baseURL}addressbook/${id}/export/`
            try {
                if (window.open(url)) return true
            } catch (e) {
                location.href = url
            }
        },
        async updateGroup({ commit }, form) {
            const response = await this.api().patch(`/addressbook_group/${form.id}/`, form)
            commit('updateGroup', response)
            return response
        },
        async deleteGroup({ commit }, { addressBookId, id }) {
            const response = await this.api().delete(`/addressbook_group/${id}/`)
            commit('deleteGroup', { addressBookId, id })
            return response
        },
        async getItem(context, id) {
            return this.api().get(`/addressbook_item/${id}/`)
        },
        async addItem({ commit }, form) {
            const response = await this.api().post('/addressbook_item/', form)
            commit('updateAddressBookItem', response)
            return response
        },
        async addItemsBulk({ commit }, bulkData) {
            const response = await this.api().post('/addressbook_item/bulk_create/', bulkData)
            if (response.items) {
                response.items.forEach(item => item.id && commit('updateAddressBookItem', item))
            }
            return response
        },
        async updateItem({ commit }, itemData) {
            const response = await this.api().patch(`/addressbook_item/${itemData.id}/`, itemData)
            commit('updateAddressBookItem', response)
            return response
        },
        async deleteItem({ commit }, { addressBookId, id }) {
            const response = await this.api().delete(`/addressbook_item/${id}/`)
            commit('deleteAddressBookItem', { addressBookId, id })
            return response
        },
    },
    mutations: {
        setAddressBooks(state, books) {
            const newValues = idMap(books)
            Object.values(books).forEach(book => {
                if (book._fullyLoaded) {
                    newValues[book.id] = { ...newValues[book.id], ...book }
                }
            })
            state.books = newValues
        },
        updateAddressBook(state, book) {
            state.books = { ...state.books, [book.id]: { ...book, _fullyLoaded: true } }
        },
        deleteAddressBook(state, id) {
            delete state.books[id]
        },
        updateGroup(state, group) {
            const addressBookId = group.address_book
            if (!addressBookId) return

            Vue.set(state.groups[addressBookId], group.id, group)
        },
        deleteGroup(state, { addressBookId, id }) {
            Vue.delete(state.groups[addressBookId], id)
        },
        setGroups(state, { addressBookId, groups }) {
            state.groups = { ...state.groups, [addressBookId]: idMap(groups) }
        },
        setAddressBookItems(state, { addressBookId, items }) {
            state.items = { ...state.items, [addressBookId]: idMap(items) }
        },
        updateAddressBookItem(state, item) {
            if (!item.address_book || !state.items[item.address_book]) {
                return
            }
            Vue.set(state.items[item.address_book], item.id, item)
        },
        deleteAddressBookItem(state, { addressBookId, id }) {
            Vue.delete(state.items[addressBookId], id)
        },
        setSources(state, { addressBookId, sources }) {
            state.sources = { ...state.sources, [addressBookId]: idMap(sources) }
        },
        setProviders(state, providers) {
            state.providers = providers
        },
    },
    namespaced: true,
}
