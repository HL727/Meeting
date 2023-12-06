<template>
    <div>
        <slot name="header" />
        <slot
            v-if="!hideActions"
            name="action"
        />

        <v-card-text
            v-if="countedItemsWithDuplicates.length > 0"
            class="py-0"
        >
            <div class="d-flex align-center mb-4">
                <v-text-field
                    v-if="!hideSearch"
                    v-model="searchInput"
                    v-bind="searchAttr"
                    hide-details
                    :placeholder="label + '...'"
                    prepend-inner-icon="mdi-magnify"
                    clearable
                    :class="showReload ? 'mr-4' : ''"
                />
                <v-btn
                    v-if="showReload"
                    color="primary"
                    class="mr-md-4"
                >
                    <v-icon>mdi-refresh</v-icon>
                </v-btn>
            </div>
        </v-card-text>
        <v-treeview
            v-if="countedItemsWithDuplicates.length > 0"
            ref="tree"
            :value="single ? [] : internalValue"
            :active="!single || !internalValue ? [] : internalValue"
            :search="searchReal"
            :item-key="itemKey"
            :item-text="itemText"
            :items="countedItemsWithDuplicates"
            :selectable="!single && !hideSelect"
            :open.sync="open"
            :activatable="single"
            :dense="dense"
            :open-all="openAll"
            :hoverable="hoverable"
            @input="internalValue = $event"
            @update:active="activate"
        >
            <template v-slot:append="{ item }">
                <span class="grey--text">{{ item.totalCount ? `(${item.totalCount})` : '' }}</span>
            </template>
            <template v-slot:label="{ item }">
                <template v-if="item.isParentDuplicate">
                    <v-icon small>
                        mdi-dots-horizontal
                    </v-icon>
                    <i
                        v-if="item.isParentDuplicate"
                        class="grey--text text--lighten-1"
                    >
                        {{ item[itemText] }}
                    </i>
                </template>
                <template v-else>
                    {{ item[itemText] }}
                </template>
            </template>
            <template
                v-for="(_, name) in $scopedSlots"
                :slot="name"
                slot-scope="slotData"
            >
                <slot
                    :name="name"
                    v-bind="slotData"
                />
            </template>
        </v-treeview>
        <v-card-text
            v-if="countItems && hiddenNodes && !hideToggleEmpty"
            class="py-0"
        >
            <v-switch
                v-model="forceShowEmpty"
                :label="`Visa ${hiddenNodes} tomma grupper`"
            />
        </v-card-text>
    </div>
</template>

<script>
import {countItems, duplicateParentsAsSubNodes, textPath} from '@/vue/helpers/tree'
import { $gettext } from '@/vue/helpers/translate'

const splitSearch = s => {
    return (
        (s || '')
            .replace(/ *[/>] *[A-z ]{0,2}$/, '')
            .split(/ *[/>] */)
            .pop() || ''
    )
}

export default {
    props: {
        value: {
            type: [Number, Array],
            default() {
                return this.single ? null : []
            },
        },
        duplicateParentsAsNodes: { type: [Boolean, String], required: false, default: false },
        label: { type: String, default() { return $gettext('Sök grupp') }},
        single: { type: Boolean, default: false },
        search: { type: String, default: '' },
        hideSearch: { type: Boolean, default: false },
        items: { type: Array, required: true, default: () => [] },
        countItems: { type: Array, required: false, default: null },
        countItemsKey: { type: String, required: false, default: null },
        showEmpty: { type: Boolean, default: false },
        hideToggleEmpty: { type: Boolean, default: false },
        hideActions: { type: Boolean, default: false },
        hideSelect: { type: Boolean, default: false },
        emptyText: { type: String, default: $gettext('<Utan tillhörighet>')},
        itemText: { type: String, default: 'title' },
        itemKey: { type: String, default: 'id' },
        searchAttr: { type: Object, default: () => ({}) },
        dense: { type: Boolean, default: false },
        openAll: { type: Boolean, default: false },
        hoverable: { type: Boolean, default: false },
        showReload: { type: Boolean, default: false },
        separator: { type: String, default: ' / ' },
    },
    data() {
        let internalValue = this.value || []
        if (!Array.isArray(internalValue)) internalValue = [internalValue]

        return {
            searchReal: '',
            searchInput: this.search,
            internalValue: internalValue,
            open: [],
            forceShowEmpty: false,
        }
    },
    computed: {
        countedItemsWithDuplicates() {
            if (!this.duplicateParentsAsNodes) return this.countedItems

            const title = typeof this.duplicateParentsAsNodes == 'string' ? this.duplicateParentsAsNodes : this.$gettext('(direkt i grupp)')
            const getItemTitle = () => ({[this.itemText]: title })

            return duplicateParentsAsSubNodes(this.countedItems, getItemTitle, this.itemKey, true)
        },
        countedItems() {
            if (!this.countItems) {
                return this.items
            }

            // Add null-relation if empty relations exist. Remove otherwise
            const empty = { id: null, [this.itemText]: this.emptyText, children: [], isEmpty: true }

            const counted = countItems(
                [empty, ...this.items],
                this.countItems,
                this.countItemsKey,
                !(this.showEmpty || this.forceShowEmpty)
            )

            if (counted.length === 0 && this.items.length < 5) return this.items

            return counted.filter(i => !(i.isEmpty && !i.totalCount))
        },
        textPath() {
            return textPath(this.internalValue, this.items, this.itemText, this.itemKey, this.separator)
        },
        hiddenNodes() {
            if (!this.countItems) return 0
            const counted = this.countedItems.reduce(
                (acc, item) => acc + (item.isEmpty ? 0 : item.totalNodes),
                0
            )
            const all = this.items.reduce((acc, item) => acc + item.totalNodes, 0)
            return all - counted
        },
    },
    watch: {
        value(newValue) {
            if (!newValue) this.internalValue = []
            else this.internalValue = newValue && newValue.pop ? newValue : [newValue]
        },
        search(newValue) {
            this.searchInput = newValue
            this.searchReal = splitSearch(newValue)
        },
        searchInput(newValue) {
            this.searchReal = splitSearch(newValue)
        },
        internalValue(newValue) {
            if (this.single) {
                this.$emit('input', newValue.length ? newValue[0] : null)
            } else {
                this.$emit('input', newValue || [])
                this.$emit('textPath', newValue.map(v => textPath(v, this.items, this.itemText)).join(', '))
            }
        },
        items() {
            this.openDefault()
        },
    },
    mounted() {
        this.openDefault()
    },
    methods: {
        activate(newValue) {
            if (!this.single) return
            this.internalValue = newValue
            this.$emit('textPath', this.textPath)
        },
        openDefault() {
            if (!this.open.length && (this.items || []).length === 1) {
                this.open = [this.items[0][this.itemKey]]
            }
        },
        openAllNodes() {
            this.$refs.tree?.updateAll(true)
        }
    },
}
</script>
