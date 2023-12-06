<template>
    <v-form
        v-if="!loading"
        ref="form"
        v-model="formValid"
        @submit.prevent="delaySubmit"
    >
        <v-card>
            <v-progress-linear
                :active="loading"
                indeterminate
                absolute
                top
            />
            <v-card-title>
                <translate>Skapa flera inlägg</translate>
            </v-card-title>
            <v-divider />
            <v-tabs v-model="tab">
                <v-tab><translate>Manuellt</translate></v-tab>
                <v-tab><translate>Från excel</translate></v-tab>
                <v-tab v-if="createdItems && createdItems.length">
                    <translate>Skapade inlägg</translate>
                </v-tab>
            </v-tabs>
            <v-divider />
            <v-card-text>
                <div
                    v-if="tab === 0"
                    style="max-width: 40rem"
                >
                    <GroupPicker
                        v-model="form.group"
                        :items="groups"
                        :label="$gettext('Skapa under grupp')"
                        :error-messages="errors && errors.group"
                    />
                </div>

                <v-tabs-items v-model="tab">
                    <v-tab-item>
                        <div style="overflow-y: auto;">
                            <v-data-table
                                :class="{ scrollwrap_1600: $vuetify.breakpoint.mdAndUp }"
                                :items-per-page="10"
                                :items="items"
                                :headers="headers"
                                item-key="_id"
                            >
                                <template v-slot:header.status>
                                    <v-checkbox @change="selectAll" />
                                </template>
                                <template v-slot:item.status="{ item }">
                                    <div class="d-flex align-center">
                                        <v-checkbox
                                            :input-value="item.valid && item.enabled"
                                            :disabled="!item.valid"
                                            @change="(item.errors = {}) && (item.enabled = $event)"
                                        />
                                    </div>
                                </template>

                                <template v-slot:item.title="{ item }">
                                    <v-text-field
                                        v-model="item.title"
                                        :error-messages="item.errors && item.errors.title"
                                        :rules="item.valid && item.enabled ? rules.notEmpty : undefined"
                                        :placeholder="$gettext('Namn')"
                                    />
                                </template>
                                <template v-slot:item.description="{ item }">
                                    <v-text-field
                                        v-model="item.description"
                                        :error-messages="item.errors && item.errors.description"
                                        :placeholder="$gettext('Beskrivning')"
                                    />
                                </template>

                                <template v-slot:item.group_path="{ item }">
                                    <v-text-field
                                        v-model="item.group_path"
                                        hint="Separara med /"
                                    />
                                </template>

                                <template v-slot:item.sip="{ item }">
                                    <v-text-field
                                        v-model="item.sip"
                                        :error-messages="item.errors && item.errors.sip"
                                        :counter="100"
                                        :placeholder="$gettext('SIP')"
                                    />
                                </template>
                                <template v-slot:item.h323="{ item }">
                                    <v-text-field
                                        v-model="item.h323"
                                        :error-messages="item.errors && item.errors.h323"
                                        :counter="100"
                                        :placeholder="$gettext('H323')"
                                    />
                                </template>
                                <template v-slot:item.h323_e164="{ item }">
                                    <v-text-field
                                        v-model="item.h323_e164"
                                        :error-messages="item.errors && item.errors.h323_e164"
                                        :counter="100"
                                        :placeholder="$gettext('H323 E.164')"
                                    />
                                </template>

                                <template v-slot:item.tel="{ item }">
                                    <v-text-field
                                        v-model="item.tel"
                                        :error-messages="item.errors && item.errors.tel"
                                        :placeholder="$gettext('Telefonnummer')"
                                    />
                                </template>
                            </v-data-table>
                        </div>
                    </v-tab-item>
                    <v-tab-item>
                        <ExcelBulkImport
                            :columns="headers"
                            :hide-close="true"
                            @input="useExcel"
                            @cancel="tab = 0"
                        />
                    </v-tab-item>
                    <v-tab-item v-if="createdItems && createdItems.length">
                        <h4 class="my-5">
                            <translate :translate-params="{length: createdItems.length}">
                                Totalt har %{length} inlägg skapats.
                            </translate>
                        </h4>

                        <v-simple-table>
                            <template v-slot:default>
                                <thead>
                                    <tr>
                                        <th
                                            v-translate
                                            class="text-left"
                                        >
                                            Namn
                                        </th>
                                        <th
                                            v-translate
                                            class="text-left"
                                        >
                                            SIP
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr
                                        v-for="item in createdItems"
                                        :key="item.id"
                                    >
                                        <td>
                                            {{ item.title }}
                                        </td>
                                        <td>
                                            {{ item.sip }}
                                        </td>
                                    </tr>
                                </tbody>
                            </template>
                        </v-simple-table>
                    </v-tab-item>
                </v-tabs-items>

                <v-snackbar
                    v-model="errorSnackbar"
                    :timeout="2500"
                    color="error"
                >
                    {{ error }}
                    <v-btn
                        dark
                        text
                        @click="errorSnackbar = null"
                    >
                        <translate>Stäng</translate>
                    </v-btn>
                </v-snackbar>
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-btn
                    v-if="tab === 0"
                    class="mr-4"
                    :disabled="!activeItems.length || !formValid"
                    :loading="formLoading"
                    color="primary"
                    type="submit"
                >
                    <translate>Lägg till</translate>
                </v-btn>
                <v-spacer />
                <v-btn
                    v-close-dialog
                    text
                    color="red"
                >
                    <translate>Avbryt</translate>
                    <v-icon
                        right
                        dark
                    >
                        mdi-close
                    </v-icon>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-form>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import { closeDialog } from '@/vue/helpers/dialog'
import ExcelBulkImport from '../endpoint/ExcelBulkImport'
import GroupPicker from './GroupPicker'

let tempId = 0

const emptyRow = data => ({
    _id: tempId++,
    title: '',
    description: '',

    group_path: '',
    sip: '',
    h323: '',
    h323_e164: '',
    tel: '',

    valid: null,
    enabled: true,

    ...(data || {}),
})

export default {
    name: 'ItemBulkForm',
    components: { GroupPicker, ExcelBulkImport },
    props: {
        groups: {
            type: Array,
            required: true,
            default: () => [],
        },
        addressBookId: {
            type: Number,
            default: null,
        },
        initialGroup: {
            type: Number,
            default: null,
            required: false,
        },
    },
    data() {
        return {
            loading: false,
            formLoading: false,
            formValid: false,
            tab: 0,
            form: {
                group: this.initialGroup || (this.groups ? this.groups[0]?.id : null),
            },
            items: [...Array(3).keys()].map(() => emptyRow()),
            createdItems: [],
            headers: [
                { text: '', value: 'status', sortable: false },
                { text: $gettext('Namn *'), value: 'title' },
                { text: $gettext('Beskrivning'), value: 'description' },

                { text: $gettext('SIP *'), value: 'sip' },
                { text: $gettext('H323'), value: 'h323' },
                { text: $gettext('H323 E164-alias'), value: 'h323_e164' },
                { text: $gettext('Telefonnummer'), value: 'tel' },
                { text: $gettext('Grupp'), value: 'group_path' },
            ],
            rules: {
                notEmpty: [v => v ? true : 'Värdet måste fyllas i'],
            },
            error: null,
            errorSnackbar: false,
            errors: {},
        }
    },
    computed: {
        activeItems() {
            if (!this.items) return []
            return this.items.filter(item => {
                return item.valid && item.enabled
            })
        },
    },
    watch: {
        items: {
            handler() {
                this.updateValid()
            },
            deep: true,
        },
    },
    methods: {
        addRow() {
            this.items.unshift(emptyRow())
        },
        removeItem(_id) {
            const index = this.items.findIndex(item => item._id == _id)
            this.items.splice(index, 1)
        },
        delaySubmit() {
            // make sure comboboxes are saved
            return new Promise(resolve => setTimeout(() => resolve(this.submit()), 100))
        },
        updateValid() {
            this.items.forEach((item, index) => {
                const valid = !!(item.title && (item.sip || item.h323 || item.h323_e164))

                if (!!item.valid !== valid) {
                    this.$set(this.items[index], 'valid', valid)
                }
            })
            if (this.items.length && this.items[this.items.length - 1].valid) {
                this.items.push(emptyRow())
            }
            this.$refs.form.validate()
        },
        useExcel(items) {
            this.tab = 0
            this.items = items.map(item => emptyRow(item))
            this.updateValid()
            this.selectAll(true)
            this.$nextTick(() => {
                this.$refs.form.validate()
            })
        },
        selectAll(selected) {
            this.items.forEach(e => {
                this.$set(e, 'enabled', selected)
            })
        },
        submit() {
            if (!this.$refs.form.validate()) return
            this.formLoading = true
            this.items = [ ...this.items.filter(item => item.valid && item.enabled) ]

            const data = {
                ...this.form,
                items: this.activeItems.map(item => ({
                    ...item,
                })),
            }

            this.errors = {}
            this.error = null
            this.createdItems = []
            this.$store.dispatch('addressbook/addItemsBulk', data)
                .then(response => {
                    this.formLoading = false

                    this.createdItems = response.items.filter(item => item.id)

                    this.$store.dispatch('addressbook/getAddressBook', this.addressBookId)

                    this.$emit('complete', this.createdItems)
                    this.items = [emptyRow()]
                    this.tab = 2
                })
                .catch(e => {
                    this.formLoading = false

                    if (e.errors && e.errors.items) {
                        this.items = this.checkErrors(e.errors.items)
                    }

                    if (e.errors) {
                        this.errors = e.errors
                    } else {
                        this.error = e.error || e.toString()
                        this.errorSnackbar = true
                    }
                })
        },
        checkErrors(items) {
            const result = []
            items.forEach((item, index) => {
                if (item.status === 'ok') {
                    return
                }
                result.push({
                    ...this.items[index],
                    errors: { ...item, ...item.errors },
                })
                this.errors = { ...this.errors, ...item.errors }
            })
            return result
        },
        cancel() {
            closeDialog(this.$vnode)
        },
    }
}
</script>

