<template>
    <v-dialog
        v-model="dialog"
        :close-on-content-click="false"
        :nudge-right="40"
        transition="scale-transition"
        offset-y
        scrollable

        :fullscreen="$vuetify.breakpoint.xsOnly"
        width="400px"
    >
        <template v-slot:activator="{ on }">
            <!-- TODO separate input events with TreePicker events -->
            <v-text-field
                v-model="search"
                :label="label"
                v-bind="inputAttrs"
                clearable
                :hide-details="hideDetails"
                :append-outer-icon="appendOuterIcon"
                :readonly="single"
                v-on="{...$listeners, ...on}"
            />

            <input
                v-if="inputName"
                type="hidden"
                :name="inputName"
                :value="internalValue || ''"
            >
            <input
                v-if="textPathInputName"
                type="hidden"
                :name="textPathInputName"
                :value="search || ''"
            >
        </template>

        <v-card>
            <v-card-title>{{ title || label }}</v-card-title>
            <v-divider />
            <v-card-text class="pa-0">
                <component
                    :is="treeComponent"
                    ref="tree"
                    :value="internalValue"
                    :items="items"
                    :hide-details="hideDetails"
                    :item-text="itemText"
                    :item-key="itemKey"
                    :single="single"
                    :hide-add-new="hideAddNew"
                    @input="internalValue = $event"
                    @click:clear="$emit('input', null)"
                    v-on="$listeners"
                    @textPath="update($event)"
                    @loadedItems="initialValue"
                >
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
                </component>
            </v-card-text>
            <v-divider v-if="items.length" />
            <v-card-actions>
                <v-spacer />
                <v-btn
                    v-close-dialog
                    text
                    color="red"
                >
                    <translate>Stäng</translate>
                    <v-icon
                        right
                        dark
                    >
                        mdi-close
                    </v-icon>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import TreeView from '@/vue/components/tree/TreeView'
import { textPath } from '@/vue/helpers/tree'

export default {
    name: 'TreeViewPicker',
    components: { TreeView },
    inheritAttrs: false,
    props: {
        title: { type: String, default: '' },
        label: { type: String, default: $gettext('Välj') },
        value: { type: [String, Number], default: null },
        treeComponent: { type: Object, default: () => TreeView },
        items: { type: Array, default: () => [] },
        itemText: { type: String, default: 'title' },
        itemKey: { type: String, default: 'id' },
        single: { type: Boolean, default: true },
        inputName: { type: String, default: '' },
        inputAttrs: {
            type: Object,
            default() {
                return this.$attrs
            },
        },
        hideDetails: { type: Boolean, default: false },
        hideAddNew: { type: Boolean, default: false },
        textPathInputName: { type: String, default: '' },
        appendOuterIcon: { type: String, default: '' },
        emptyResultHint: { type: String, default: '' },
    },
    data() {
        return {
            search: '',
            dialog: null,
            internalValue: this.value,
        }
    },
    watch: {
        items() {
            this.initialValue()
        },
        value() {
            if (this.search && this.search === this.valueText(this.internalValue)) {
                this.search = ''
            }
            this.internalValue = this.value
            this.initialValue()
        },
        internalValue() {
            this.$emit('input', this.internalValue)
        },
    },
    mounted() {
        this.initialValue()
    },
    methods: {
        initialValue(items = null) {
            if (!this.search && (items || this.items || []).length && this.value) {
                this.search = this.valueText(this.value, items)
            }
        },
        update(newValue) {
            this.dialog = this.single ? false : this.dialog
            this.search = newValue
            this.$emit('textPath', newValue)
            this.$emit('update:text-path', newValue)
        },
        valueText(value, items = null) {
            return textPath(value, items || this.items, this.itemText, this.itemKey)
        },
    },
}
</script>

<style scoped>
>>> div.v-treeview-node__label {
    cursor: pointer;
}

</style>
