<template>
    <v-combobox
        v-model="selected"
        :search-input.sync="textValue"
        :loading="loading"
        return-object
        auto-select-first
        v-bind="{ noFilter: true, label: label, ...inputAttrs }"
        :hide-details="hideDetails"
        :items="items"
        :item-text="itemText"
        :item-value="itemValue"
        :no-data-text="noDataText"
        @keydown.native.enter="onenter"
        v-on="inputListeners"
        @click:clear="$emit('input', undefined)"
    >
        <template v-slot:item="{ item }">
            <v-list-item-content>
                <v-list-item-title>{{ item._title }}</v-list-item-title>
                <v-list-item-subtitle v-if="item._subTitle">
                    {{ item._subTitle }}
                </v-list-item-subtitle>
            </v-list-item-content>
        </template>

        <template v-slot:append>
            <input
                v-if="inputName"
                ref="input"
                type="hidden"
                :name="inputName"
                :value="inputValue"
            >
        </template>
    </v-combobox>
</template>

<script>
import { $gettext, $gettextInterpolate } from '@/vue/helpers/translate'

import { itemListSearchPrefix } from '@/consts'
import {idMap} from '../../helpers/store'
import axios from 'axios'

export default {
    props: {
        itemText: { type: String, default: 'name' },
        itemSubtitle: { type: String, default: '' },
        itemValue: { type: String, default: 'id' },
        itemSearch: { type: String, default: '' },
        inputAttrs: {
            type: Object,
            default() {
                return {}
            },
        },
        inputName: { type: String, default: '' },
        label: { type: String, default: '' },
        searchUrl: { type: String, required: true },
        enableSearchAll: { type: Boolean },
        autoSubmit: { type: Boolean },
        localItems: { type: Array, default: null },
        noDataText: { type: String, default: $gettext('Hittade inga objekt') },
        hideDetails: { type: Boolean, default: false },
        value: { type: [Object, String, Number, null], default: null },
        search: {
            type: String,
            default: '',
        },
        searchQuery: {
            type: String,
            default: '',
        },
        all: {
            type: Boolean,
            default: false,
        },
        returnObject: {
            type: Boolean,
            default: false,
        },
        extraParams: {
            type: Object,
            default() {
                return {}
            },
        },
    },
    data() {
        let value = this.value === null ? null : this.value

        const valueText =
            this.value && typeof this.value == 'object'
                ? this.value[this.itemText] || ''
                : (value || '').toString() || ''


        let search = (this.search || '').replace(itemListSearchPrefix, '') || valueText.toString()
        if (this.localItems) {
            const localMap = idMap(this.localItems, this.itemValue)
            if (localMap[value]) {
                search = localMap[valueText][this.itemValue]
                value = localMap[value]
            }
        }

        return {
            selected: value || search, // selected should always be object, passed into combobox
            textValue: search,
            loading: false,
            pagination: {},
            debounceTimeout: null,
            requestCancelToken: null,
        }
    },
    computed: {
        items() {
            const items = (this.localItems || this.pagination.results || []).map(i => {
                const result = typeof i == 'string' ? { _title: i } : i

                result._title = i.overrideTitle || i[this.itemText]
                if (!result._title) result._title = i[this.itemSubtitle] || '--empty--'
                else if (this.itemSubtitle) result._subTitle = i[this.itemSubtitle]

                return result
            })

            if (this.enableSearchAll) {
                const title = this.pagination.count ?
                    $gettextInterpolate($gettext('Visa %{ count } resultat'), { count: this.pagination.count || 0 })
                    : $gettext('Visa alla resultat')

                const displayAllItem = {
                    _title: title,
                    [this.itemText]: this.textValue,
                }
                items.unshift(displayAllItem)
            }

            return items
        },
        inputValue() {
            if (!this.selected) return ''
            if (typeof this.selected == 'string') {
                return this.value || this.selected
            }
            return this.selected[this.itemValue]
        },
        inputListeners() {
            const result = { ...this.$listeners }
            ;['search', 'input', 'input:search', 'search-all', 'click:clear'].forEach(k => {
                delete result[k]
            })
            return result
        },
    },
    watch: {
        value(newValue) {
            this.selected = newValue == 'object' ? newValue[this.itemValue] : idMap(this.items, this.itemValue)[newValue] || newValue
        },
        textValue(newValue) {
            if (typeof newValue === 'string') {
                this.$emit('update:search', newValue)
                this.$emit('input:search', newValue)
            }
            if (!newValue) {
                return (this.pagination = {})
            }
            if (newValue) {
                this.debounce()
            }
        },
        selected(newValue) {
            if (!newValue || typeof newValue == 'string' || newValue[this.itemValue] === undefined) {
                if (newValue && typeof newValue == 'object') {
                    // selected display all item
                    this.$emit('search-all', this.textValue || '')
                }
                return
            }
            this.$emit('input', this.returnObject ? newValue : newValue[this.itemValue])
            if (this.itemSearch && newValue[this.itemSearch]) {
                this.$nextTick(() => {
                    this.$nextTick(() => {
                        this.textValue = newValue[this.itemSearch]
                    })
                })
            }
            if (this.autoSubmit && this.inputName) {
                this.$nextTick(() => {
                    try {
                        this.$refs.input.form.submit()
                    } catch (e) {
                        /* */
                    }
                })
            }
        },
    },
    methods: {
        onenter() {
            if (this.selected === this.textValue) this.$emit('search-all', this.textValue || '')
        },
        debounce() {
            if (this.debounceTimeout) return
            this.debounceTimeout = setTimeout(() => {
                this.load()
                this.debounceTimeout = null
            }, 300)
        },
        load() {
            if (!this.searchUrl) return

            if (this.requestCancelToken) {
                this.requestCancelToken.cancel('cancelled by new search')
            }
            this.requestCancelToken = axios.CancelToken.source()
            this.loading = true

            const { textValue, all, limit } = this
            const search = this.searchQuery ? { [this.searchQuery]: textValue } : { search: textValue }
            return this.$store.api().get(this.searchUrl, {
                params: {
                    ...this.extraParams,
                    ...search,
                    limit,
                    all: all ? 1 : undefined,
                },
                cancelToken: this.requestCancelToken.token,
            }).then(response => {
                this.pagination = response
                this.loading = false
            }).catch(e => {
                this.loading = false
                if (axios.isCancel(e)) {
                    return
                }
                throw e
            })
        },
    },
}
</script>

<style scoped></style>
