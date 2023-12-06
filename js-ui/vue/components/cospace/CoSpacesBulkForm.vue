
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
                <translate>Lägg till flera mötesrum</translate>
            </v-card-title>
            <v-divider />
            <v-tabs v-model="tab">
                <v-tab><translate>Manuellt</translate></v-tab>
                <v-tab><translate>Från excel</translate></v-tab>
                <v-tab v-if="createdItems && createdItems.length">
                    <translate>Skapade rum</translate>
                </v-tab>
            </v-tabs>
            <v-divider />
            <v-card-text>
                <div
                    v-if="tab === 0"
                    style="max-width: 40rem"
                >
                    <v-checkbox
                        class="mt-2"
                        :label="$gettext('Skicka e-post')"
                        model="form.send_email"
                    />

                    <v-select
                        v-model="form.call_id_generation_method"
                        :label="$gettext('Skapa automatiskt numeriskt adress för ej ifyllda poster')"
                        :items="[
                            { value: 'random', text: $gettext('Slumpa numeriskt ID') },
                            { value: 'increase', text: $gettext('Nästa numeriska ID i nummerföljd') },
                        ]"
                    />

                    <v-divider />
                </div>
                <v-tabs-items v-model="tab">
                    <v-tab-item>
                        <div v-if="createdItems.length > 0">
                            <h4 class="my-5">
                                <translate :translate-params="{length: createdItems.length}">
                                    Totalt har %{length} mötesrum skapats.
                                </translate>
                                <a
                                    v-translate
                                    @click="tab = 2"
                                >Visa skapade mötesrum</a>
                            </h4>
                        </div>

                        <v-data-table
                            :headers="headers"
                            :items-per-page="10"
                            :items="items"
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
                            <template v-slot:item.name="{ item }">
                                <v-text-field
                                    v-model="item.name"
                                    :error-messages="item.errors && item.errors.name"
                                    :placeholder="$gettext('Namn')"
                                    validate-on-blur
                                    :rules="item.valid && item.enabled ? rules.notEmpty : undefined"
                                    @keyup="item.errors.name = null"
                                />
                            </template>
                            <template v-slot:item.uri="{ item }">
                                <v-text-field
                                    v-model="item.uri"
                                    :error-messages="item.errors && item.errors.uri"
                                    :placeholder="$gettext('URI')"
                                    validate-on-blur
                                    @keyup="item.errors.uri = null"
                                />
                            </template>
                            <template v-slot:item.call_id="{ item }">
                                <v-text-field
                                    v-model="item.call_id"
                                    :error-messages="item.errors && item.errors.call_id"
                                    :placeholder="$gettext('Call ID')"
                                    validate-on-blur
                                    :rules="item.valid && item.enabled ? rules.number : undefined"
                                    @keyup="item.errors.call_id = null"
                                />
                            </template>
                            <template v-slot:item.passcode="{ item }">
                                <v-text-field
                                    v-model="item.passcode"
                                    :error-messages="item.errors && item.errors.passcode"
                                    :placeholder="$gettext('PIN-kod')"
                                    validate-on-blur
                                    append-outer-icon="mdi-refresh"
                                    @keyup="item.errors.passcode = null"
                                    @click:append-outer="item.passcode = parseInt(Math.random() * 10000)"
                                />
                            </template>
                            <template v-slot:item.organization_path="{ item }">
                                <v-text-field
                                    v-model="item.organization_path"
                                    :error-messages="item.errors && item.errors.organization_path"
                                    :placeholder="$gettext('Organisationsenhet')"
                                />
                            </template>
                            <template v-slot:item.owner_jid="{ item }">
                                <v-text-field
                                    v-model="item.owner_jid"
                                    :error-messages="item.errors && item.errors.owner_jid"
                                    :placeholder="$gettext('Ägare')"
                                    :rules="item.valid && item.enabled ? [v => item.owner_jid_error != v ? true : 'Ange en annan ägare'] : undefined"
                                    @keyup="item.errors.owner_jid = null"
                                />
                            </template>
                            <template v-slot:item.owner_email="{ item }">
                                <v-text-field
                                    v-model="item.owner_email"
                                    :error-messages="item.errors && item.errors.owner_email"
                                    :placeholder="$gettext('E-postadress')"
                                    @keyup="item.errors.owner_email = null"
                                />
                            </template>
                        </v-data-table>
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
                        <v-simple-table>
                            <template v-slot:default>
                                <thead>
                                    <tr>
                                        <th
                                            v-translate
                                            class="text-left"
                                        >
                                            Name
                                        </th>
                                        <th
                                            v-translate
                                            class="text-left"
                                        >
                                            URI
                                        </th>
                                        <th
                                            v-translate
                                            class="text-left"
                                        >
                                            Call ID
                                        </th>
                                        <th
                                            v-translate
                                            class="text-left"
                                        >
                                            Ägare
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr
                                        v-for="item in createdItems"
                                        :key="item.id"
                                    >
                                        <td>
                                            <router-link :to="{name: 'cospaces_details', params: { id: item.id } }">
                                                {{
                                                    item.name
                                                }}
                                            </router-link>
                                        </td>
                                        <td>{{ item.uri }}</td>
                                        <td>{{ item.call_id }}</td>
                                        <td>{{ item.owner_jid || item.owner_email }}</td>
                                    </tr>
                                </tbody>
                            </template>
                        </v-simple-table>

                        <v-card-actions>
                            <v-btn v-close-dialog>
                                <translate>Stäng</translate>
                            </v-btn>
                        </v-card-actions>
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

import ExcelBulkImport from '../epm/endpoint/ExcelBulkImport'
import { closeDialog } from '../../helpers/dialog'

let tempId = 0

const emptyRow = data => ({
    _id: tempId++,
    id: 0,
    name: '',
    uri: '',
    call_id: '',
    passcode: '',

    organization_path: '',
    owner_jid: '',
    owner_email: '',

    valid: null,
    enabled: true,

    complete: false,
    update: false,

    errors: {},

    ...(data || {}),
})

export default {
    name: 'CoSpacesBulkForm',
    components: { ExcelBulkImport },
    data() {
        return {
            loading: false,
            formLoading: false,
            formValid: false,
            tab: 0,
            form: {
                random_call_id: true,
                start_call_id: null,
                send_email: false,
                call_id_generation_method: 'random',
            },
            items: [...Array(3).keys()].map(() => emptyRow()),
            createdItems: [],
            headers: [
                { text: '', value: 'status', sortable: false },
                { text: $gettext('Namn'), value: 'name' },
                { text: $gettext('URI'), value: 'uri' },
                { text: $gettext('Call ID'), value: 'call_id' },
                { text: $gettext('PIN-kod'), value: 'passcode' },
                { text: $gettext('Ägare'), value: 'owner_jid' },
                { text: $gettext('E-postadress'), value: 'owner_email' },
                { text: $gettext('Organisationsenhet'), value: 'organization_path' },
            ],
            rules: {
                notEmpty: [v => v ? true : 'Värdet måste fyllas i'],
                number: [v => !v || parseInt(v, 10) ? true : 'Värdet måste vara ett heltal'],
            },
            error: null,
            errorSnackbar: false,
            errors: {},
            createdCoSpacesDialog: false
        }
    },
    computed: {
        activeItems() {
            if (!this.items) return []
            return this.items.filter(item => {
                return item.enabled && item.name
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
                const valid = !!item.name

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
        serializeData() {
            return {
                ...this.form,
                cospaces: this.activeItems.map(item => ({
                    ...item,
                    call_id: item.call_id || undefined,
                }))
            }
        },
        submit() {
            if (!this.$refs.form.validate()) {
                this.error = $gettext('Kontrollera formuläret')
                return
            }
            this.formLoading = true
            this.items = [ ...this.items.filter(item => item.valid && item.enabled) ]

            const data = this.serializeData()
            this.errors = {}
            this.error = null

            return this.$store.dispatch('cospace/bulkCreate', data)
                .then(response => {
                    this.formLoading = false

                    const createdItems = []

                    response.cospaces.forEach(cospace => {
                        if (cospace.status === 'ok') {
                            createdItems.push(cospace)
                        }
                    })

                    this.createdItems = [...createdItems]

                    this.items = this.checkErrors(response.cospaces)

                    if (this.items.length === 0) {
                        this.items = [emptyRow()]
                        this.$emit('complete', this.createdItems)
                        this.tab = 2
                    }
                })
                .catch(e => {
                    this.formLoading = false
                    this.handleErrors(e)
                })
        },
        handleErrors(response) {
            if (response.errors && response.errors.cospaces) {
                this.items = this.checkErrors(response.errors.cospaces)
            }

            if (response.errors) {
                this.errors = response.errors
            }
            if (response.error) {
                this.error = response.error
                this.errorSnackbar = true
            }
        },
        checkErrors(items) {
            const result = []
            items.forEach((cospace, index) => {
                if (cospace.status == 'ok') {
                    return
                }
                const newItem = {
                    ...this.items[index],
                    ...(cospace.errors ? cospace : { errors: cospace }),
                    update: true,
                    complete: false
                }

                if (cospace.errors && cospace.errors.owner_jid) {
                    newItem['owner_jid_error'] = cospace.owner_jid
                }

                result.push(newItem)
                this.errors = { ...this.errors, ...cospace.errors}
            })
            return result
        },
        cancel() {
            closeDialog(this.$vnode)
        },
    }
}
</script>
