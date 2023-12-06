<template>
    <v-form
        v-if="!loading"
        ref="form"
        v-model="formValid"
        @submit.prevent="delaySubmit"
    >
        <v-card>
            <v-progress-circular
                v-if="loading"
                indeterminate
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
                    <v-select
                        v-model="form.service_type"
                        :label="$gettext('Typ av rum')"
                        hide-details
                        :items="[{value: 'conference', text: $ngettext('Mötesrum', 'Mötesrum', 1)}, {value: 'lecture', text: $gettext('Webinar')}]"
                    />

                    <v-checkbox
                        v-model="form.send_email"
                        :label="$gettext('Skicka e-post')"
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
                            <template v-slot:item.description="{ item }">
                                <v-text-field
                                    v-model="item.description"
                                    :error-messages="item.errors && item.errors.description"
                                    :placeholder="$gettext('Beskrivning')"
                                    validate-on-blur
                                    @keyup="item.errors.description = null"
                                />
                            </template>
                            <template v-slot:item.pin="{ item }">
                                <v-text-field
                                    v-model="item.pin"
                                    :error-messages="item.errors && item.errors.pin"
                                    :placeholder="$gettext('Pin')"
                                    validate-on-blur
                                    append-outer-icon="mdi-refresh"
                                    @keyup="item.errors.pin = null"
                                    @click:append-outer="item.pin = parseInt(Math.random() * 10000)"
                                />
                            </template>
                            <template v-slot:item.host_view="{ item }">
                                <v-select
                                    v-model="item.host_view"
                                    :items="pexipHostLayoutChoices"
                                    item-text="title"
                                    item-value="id"
                                    :label="$gettext('Moderatorlayout')"
                                />
                            </template>
                            <template v-slot:item.allow_guests="{ item }">
                                <v-checkbox
                                    v-model="item.allow_guests"
                                    :disabled="!item.valid"
                                />
                            </template>
                            <template v-slot:item.guest_pin="{ item }">
                                <v-text-field
                                    v-model="item.guest_pin"
                                    :error-messages="item.errors && item.errors.guest_pin"
                                    :placeholder="$gettext('Gäst Pin')"
                                    validate-on-blur
                                    append-outer-icon="mdi-refresh"
                                    @keyup="item.errors.guest_pin = null"
                                    @click:append-outer="item.guest_pin = parseInt(Math.random() * 10000)"
                                />
                            </template>
                            <template v-slot:item.guest_view="{ item }">
                                <v-select
                                    v-model="item.guest_view"
                                    :items="pexipGuestLayoutChoices"
                                    item-text="title"
                                    item-value="id"
                                    :label="$gettext('Gästlayout')"
                                />
                            </template>

                            <template v-slot:item.call_id="{ item }">
                                <v-text-field
                                    v-model.number="item.call_id"
                                    :error-messages="item.errors && item.errors.call_id"
                                    :rules="item.valid && item.enabled ? rules.number : undefined"
                                    :placeholder="$gettext('12345')"
                                    :hint="$gettext('Lämna tomt för att generera automatiskt')"
                                    @keyup="item.errors.call_id = null"
                                />
                            </template>
                            <template v-slot:item.other_aliases="{ item }">
                                <v-text-field
                                    v-model="item.other_aliases"
                                    :error-messages="item.errors && item.errors.other_aliases"
                                    placeholder="vmr1@abc.org, vmr12@abc.com ...."
                                    :hint="$gettext('Separera med komma eller mellanslag')"
                                />
                            </template>
                            <template v-slot:item.primary_owner_email_address="{ item }">
                                <v-text-field
                                    v-model="item.primary_owner_email_address"
                                    type="email"
                                    :error-messages="item.errors && item.errors.primary_owner_email_address"
                                    :placeholder="$gettext('E-postadress')"
                                />
                            </template>
                            <template v-slot:item.organization_path="{ item }">
                                <v-text-field
                                    v-model="item.organization_path"
                                    :error-messages="item.errors && item.errors.organization_path"
                                    :placeholder="$gettext('Organisationsenhet')"
                                />
                            </template>
                        </v-data-table>
                    </v-tab-item>
                    <v-tab-item>
                        <ExcelBulkImport
                            :hide-close="true"
                            :columns="headers"
                            @input="useExcel"
                            @cancel="tab = 0"
                        />
                    </v-tab-item>
                    <v-tab-item v-if="createdItems && createdItems.length">
                        <h4 class="my-5">
                            <translate :translate-params="{length: createdItems.length}">
                                Totalt har %{length} mötesrum skapats.
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
                                            Alias
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr
                                        v-for="item in createdItems"
                                        :key="item.id"
                                    >
                                        <td>
                                            <router-link :to="{ name: 'pexip_cospaces_details', params: { id: item.id } }">
                                                {{ item.name }}
                                            </router-link>
                                        </td>
                                        <td>
                                            <v-chip
                                                v-for="alias in item.aliases"
                                                :key="'alias' + alias.id"
                                            >
                                                {{ alias.alias }}
                                            </v-chip>
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

import ExcelBulkImport from '../epm/endpoint/ExcelBulkImport'
import { pexipGuestLayoutChoices, pexipHostLayoutChoices } from '@/vue/store/modules/cospace/consts'
import { closeDialog } from '../../helpers/dialog'

let tempId = 0

const emptyRow = data => ({
    _id: tempId++,

    id: 0,
    name: '',
    description: '',
    pin: '',
    allow_guests: false,
    guest_pin: '',
    call_id: '',
    other_aliases: '',
    organization_path: '',
    host_view: '',

    valid: null,
    enabled: true,

    complete: false,
    update: false,

    errors: {},

    ...(data || {}),
})

export default {
    name: 'PexipCoSpacesBulkForm',
    components: { ExcelBulkImport },
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            loading: false,
            formLoading: false,
            formValid: false,
            tab: 0,
            form: {
                random_call_id: true,
                start_call_id: null,
                call_id_generation_method: 'random',
                service_type: 'conference',
                send_email: false,
            },
            items: [...Array(3).keys()].map(() => emptyRow()),
            createdItems: [],
            headers: [
                { text: '', value: 'status', sortable: false },
                { text: $gettext('Namn'), value: 'name' },
                { text: $gettext('Beskrivning'), value: 'description' },
                { text: $gettext('Pin'), value: 'pin' },
                { text: $gettext('Layout moderatorer'), value: 'host_view' },
                { text: $gettext('Tillåt gäster'), value: 'allow_guests' },
                { text: $gettext('Gäst pin'), value: 'guest_pin' },
                { text: $gettext('Layout gäster'), value: 'guest_view' },
                { text: $gettext('Primärt nummeralias'), value: 'call_id' },
                { text: $gettext('Övriga alias'), value: 'other_aliases' },
                { text: $gettext('E-postadress'), value: 'primary_owner_email_address' },
                { text: $gettext('Organisationsenhet'), value: 'organization_path' },
            ],
            rules: {
                notEmpty: [v => v ? true : 'Värdet måste fyllas i'],
                number: [v => !v || parseInt(v, 10) ? true : 'Värdet måste vara ett heltal'],
            },
            pexipHostLayoutChoices,
            pexipGuestLayoutChoices,
            error: null,
            errorSnackbar: false,
            errors: {},
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
                conferences: this.activeItems.map(item => ({
                    ...item,
                    call_id: item.call_id || undefined,
                    service_type: item.service_type || this.form.service_type,
                    other_aliases: undefined,
                    aliases: (item.other_aliases || '').split(/[, \t\n]+/).filter(a => !!a).map(a => ({ alias: a })),
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
            return this.$store.dispatch('cospace/pexip/bulkCreate', data)
                .then(response => {
                    this.formLoading = false

                    const createdItems = []

                    response.conferences.forEach(cospace => {
                        if (cospace.status === 'ok') {
                            createdItems.push(cospace)
                        }
                    })
                    this.createdItems = [...createdItems]

                    const errors = this.checkErrors(response.conferences)
                    this.items = errors

                    if (this.items.length === 0) {
                        this.$emit('complete', this.createdItems)
                        this.items = [emptyRow()]
                        this.tab = 2
                    }
                })
                .catch(e => {
                    this.formLoading = false
                    this.handleErrors(e)
                })
        },
        handleErrors(response) {
            if (response.errors && response.errors.conferences) {
                this.items = this.checkErrors(response.errors.conferences)
            }

            if (response.errors) {
                this.errors = response.errors
            } else {
                this.error = response.error || response.toString()
                this.errorSnackbar = true
            }
        },
        checkErrors(items) {
            const result = []
            items.forEach((cospace, index) => {
                if (cospace.status === 'ok') {
                    return
                }
                const errors = 'errors' in cospace ? { ...cospace.errors } : { ...cospace }
                if (errors.aliases) errors.other_aliases = errors.aliases

                result.push({
                    ...this.items[index],
                    errors,
                })
                this.errors = { ...this.errors, ...cospace.errors }
            })
            return result
        },
        cancel() {
            closeDialog(this.$vnode)
        },
    }
}
</script>
