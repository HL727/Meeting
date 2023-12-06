<template>
    <v-form
        v-if="!loading"
        ref="form"
        v-model="formValid"
        :value="true"
        :disabled="!!licenseError"
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
                <translate>Lägg till flera system</translate>
            </v-card-title>
            <v-divider />
            <v-tabs v-model="tab">
                <v-tab :disabled="!!licenseError">
                    <translate>Manuellt</translate>
                </v-tab>
                <v-tab :disabled="!!licenseError">
                    <translate>Från excel</translate>
                </v-tab>
            </v-tabs>
            <v-divider />
            <div
                v-if="activeItems.length && willOveruse"
                class="px-4 pt-4"
            >
                <v-alert
                    type="warning"
                    class="mb-0"
                    icon="mdi-alert-outline"
                    text
                >
                    <translate
                        :translate-params="{count: activeItems.length, devicesLeft: licenseDevicesLeft}"
                    >
                        Du försöker registrera %{count} nya system men har bara %{devicesLeft} platser kvar i er licens.
                    </translate>
                </v-alert>
            </div>
            <v-card-text>
                <v-alert
                    v-if="licenseError"
                    color="error"
                    icon="mdi-alert-circle"
                    text
                >
                    {{ licenseError }}
                </v-alert>

                <div
                    v-if="tab === 0"
                    style="max-width: 40rem"
                >
                    <v-checkbox
                        v-model="form.track_ip_changes"
                        :label="$gettext('Uppdatera IP-uppgifter automatiskt när de skickas från systemet')"
                        :hint="$gettext('Kräver event-prenumeration')"
                    />

                    <v-row>
                        <v-col cols="6">
                            <v-select
                                v-model="form.connection_type"
                                :label="$gettext('Typ av anslutning')"
                                :items="connection_types"
                                hide-details
                                item-text="name"
                                item-value="id"
                            />
                        </v-col>
                        <v-col cols="6">
                            <v-select
                                v-if="form.connection_type === 2"
                                v-model="form.proxy"
                                :label="$gettext('Proxy')"
                                :items="proxies"
                                hide-details
                                item-text="name"
                                item-value="id"
                                clearable
                            />
                            <span
                                v-if="form.connection_type === 0"
                            ><i><translate>Stödjer endast firmwareuppgradering och konfigurationsändringar. Kräver att systemet
                                är inställd med provision-URL</translate></i></span>
                        </v-col>
                    </v-row>
                    <v-row>
                        <v-col cols="6">
                            <v-select
                                v-model="form.dial_protocol"
                                :error-messages="errors.dial_protocol ? errors.dial_protocol : []"
                                :rules="rules.dial_protocol"
                                :items="dial_protocols"
                                item-text="title"
                                item-value="key"
                                :label="$gettext('Protokoll för uppringning')"
                            />
                        </v-col>
                    </v-row>
                </div>

                <v-tabs-items v-model="tab">
                    <v-tab-item>
                        <div style="overflow-y: auto;">
                            <v-data-table
                                :class="{ scrollwrap_1600: $vuetify.breakpoint.mdAndUp }"
                                :headers="headers"
                                :items-per-page="10"
                                :items="items"
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
                                        :rules="item.valid && item.enabled ? rules.title : undefined"
                                        :placeholder="$gettext('Namn')"
                                    />
                                </template>
                                <template v-slot:item.username="{ item }">
                                    <v-text-field
                                        v-model="item.username"
                                        :error-messages="item.errors && item.errors.username"
                                        :rules="item.valid && item.enabled ? rules.username : undefined"
                                        :counter="50"
                                        :placeholder="$gettext('Användarnamn')"
                                    />
                                </template>
                                <template v-slot:item.password="{ item }">
                                    <div class="d-flex">
                                        <v-checkbox
                                            v-model="item.try_standard_passwords"
                                            :title="$gettext('Använd standardlösenord')"
                                        />
                                        <v-text-field
                                            v-if="!item.try_standard_passwords"
                                            v-model="item.password"
                                            type="password"
                                            :rules="item.valid && item.enabled ? rules.password : undefined"
                                            :placeholder="$gettext('Skriv in lösenord manuellt (*)')"
                                        />
                                    </div>
                                </template>
                                <template v-slot:item.ip="{ item }">
                                    <v-text-field
                                        v-model="item.ip"
                                        :error-messages="item.errors && item.errors.ip"
                                        :rules="item.valid && item.enabled ? rules.ip : undefined"
                                        validate-on-blur
                                        :placeholder="$gettext('IP-nummer')"
                                    />
                                </template>

                                <template v-slot:item.room_capacity="{ item }">
                                    <v-text-field
                                        v-model.number="item.room_capacity"
                                        :rules="item.valid && item.enabled ? rules.room_capacity : undefined"
                                        :placeholder="$gettext('Antal platser i rum')"
                                    />
                                </template>
                                <template v-slot:item.mac_address="{ item }">
                                    <v-text-field
                                        v-model="item.mac_address"
                                        :error-messages="item.errors && item.errors.mac_address"
                                        :rules="item.valid && item.enabled ? rules.mac_address : undefined"
                                        validate-on-blur
                                        :placeholder="$gettext('MAC-adress')"
                                    />
                                </template>
                                <template v-slot:item.location="{ item }">
                                    <v-combobox
                                        v-model="item.location"
                                        :placeholder="$gettext('Plats')"
                                        :items="locations"
                                    />
                                </template>
                                <template v-slot:item.organization_path="{ item }">
                                    <v-text-field
                                        v-model="item.organization_path"
                                        :label="$gettext('Organisationstillhörighet')"
                                    />
                                </template>
                                <template v-slot:item.sip="{ item }">
                                    <v-text-field
                                        v-model="item.sip"
                                        :error-messages="item.errors && item.errors.sip"
                                        :rules="item.valid && item.enabled ? rules.sip : undefined"
                                        :counter="100"
                                        :placeholder="$gettext('SIP')"
                                    />
                                </template>

                                <template v-slot:item.h323="{ item }">
                                    <v-text-field
                                        v-model="item.h323"
                                        :error-messages="item.errors && item.errors.h323"
                                        :rules="item.valid && item.enabled ? rules.h323 : undefined"
                                        :counter="100"
                                        :placeholder="$gettext('H323')"
                                    />
                                </template>
                                <template v-slot:item.hostname="{ item }">
                                    <v-text-field
                                        v-model="item.hostname"
                                        :error-messages="item.errors && item.errors.hostname"
                                        :rules="item.valid ? rules.hostname : undefined"
                                        :counter="200"
                                        :placeholder="$gettext('Hostname')"
                                    />
                                </template>

                                <template v-slot:item.h323_e164="{ item }">
                                    <v-text-field
                                        v-model="item.h323_e164"
                                        :error-messages="item.errors && item.errors.h323_e164"
                                        :rules="item.valid ? rules.h323_e164 : undefined"
                                        :counter="100"
                                        :placeholder="$gettext('H323 E.164')"
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
                            @cancel="closeDialog"
                        />
                    </v-tab-item>
                </v-tabs-items>
            </v-card-text>
            <v-alert
                v-if="error"
                type="error"
                class="ma-0"
                tile
            >
                {{ error }}
            </v-alert>
            <v-divider />
            <v-card-actions>
                <v-btn
                    v-if="tab === 0"
                    class="mr-4"
                    :disabled="!activeItems.length || !formValid || !!licenseError"
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

import EndpointLicenseMixin from '@/vue/views/epm/mixins/EndpointLicenseMixin'

import ExcelBulkImport from './ExcelBulkImport'
import { closeDialog } from '@/vue/helpers/dialog'

let tempId = 0

const emptyRow = data => ({
    _id: tempId++,
    title: '',
    ip: '',
    username: 'admin',
    valid: null,
    enabled: true,
    password: '',
    organization_path: null,
    try_standard_passwords: true,
    location: '',
    sip: '',
    h323: '',
    h323_e164: '',
    manufacturer: 10,
    room_capacity: null,
    hostname: '',
    ...(data || {}),
})

export default {
    components: { ExcelBulkImport },
    mixins: [EndpointLicenseMixin],
    props: {
        id: { type: Number, default: null, required: false },
        initialData: { type: Object, required: false, default() { return {} } },
    },
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            tab: 0,
            loading: false,
            error: '',
            formLoading: false,
            formValid: false,
            items: [...Array(3).keys()].map(() => emptyRow()),
            form: {
                connection_type: 1,
                proxy: null,
                track_ip_changes: true,
                dial_protocol: '',
                ...(this.initialData || {}),
            },
            rules: {
                id: [v => !isNaN(parseInt(v)) || $gettext('Värdet måste vara ett tal')],
                ip: [
                    v =>
                        !v || v.toString().match(/^\d+\.\d+\.\d+\.\d+$/) ? true : $gettext('Värdet måste vara ett IP'),
                ],
                mac_address: [
                    v =>
                        !v || v.toString().match(/^[A-Z0-9]{2}:[A-Z0-9]{2}:[A-Z0-9]{2}:[A-Z0-9]{2}:[A-Z0-9]{2}:[A-Z0-9]{2}$/)
                            ? true
                            : $gettext('Värdet måste vara en MAC-adress'),
                ],
                manufacturer: [v => !!v || $gettext('Värdet måste fyllas i')],
                room_capacity: [v => (!v || !isNaN(v) ? true : $gettext('Värdet måste vara ett tal'))],
                username: [v => v ? true : $gettext('Värdet måste fyllas i')],
            },
            connection_types: [
                { id: 1, name: $gettext('Direktanslutning') },
                { id: 2, name: $gettext('Genom Mividas Proxy-client') },
                { id: 0, name: $gettext('Passiv/bakom brandvägg.') },
            ],
            dial_protocols: [
                { key: '', title: $gettext('<Standardinställning>') },
                { key: 'SIP', title: $gettext('SIP') },
                { key: 'H323', title: $gettext('H323') },
            ],
            headers: [
                { text: '', value: 'status', sortable: false },
                { text: $gettext('Namn'), value: 'title' },
                { text: 'IP', value: 'ip' },
                { text: $gettext('Användarnamn'), value: 'username' },
                { text: $gettext('Lösenord'), value: 'password' },
                { text: $gettext('Stolar'), value: 'room_capacity' },
                { text: $gettext('MAC'), value: 'mac_address' },
                { text: $gettext('Organisationstillhörighet'), value: 'organization_path' },
                { text: $gettext('Hostname'), value: 'hostname' },
                { text: $gettext('Plats'), value: 'location' },
                { text: $gettext('SIP'), value: 'sip' },
                { text: $gettext('H323'), value: 'h323' },
                { text: $gettext('E.164'), value: 'h323_e164' },
            ],
            locations: [],
            errors: [],
        }
    },
    computed: {
        proxies() {
            return Object.values(this.$store.state.endpoint.proxies)
        },
        activeItems() {
            if (!this.items) return []
            return this.items.filter(item => item.enabled && (item.mac_address || item.ip))
        },
        willOveruse() {
            if (!this.licenseHasDetails || this.licenseStatus.licensed === -1) {
                return false
            }

            return this.activeItems.length > this.licenseDevicesLeft
        }
    },
    watch: {
        items: {
            handler() {
                this.updateValid()
            },
            deep: true,
        },
    },
    mounted() {
        this.loading = true
        return Promise.all([
            this.$store.dispatch('endpoint/getProxies'),
            this.$store.dispatch('endpoint/getFilters'),
            this.$store.dispatch('endpoint/getSettings'),
        ]).then(values => {
            if (this.form.connection_type === -10) this.form.connection_type = this.form.proxy ? 2 : 1
            this.locations = [...values[1].location]
            this.loading = false
            if (!this.id && values[2].default_proxy) {
                this.form.proxy = values[2].default_proxy
                this.form.connection_type = 2
            }
        })
    },
    methods: {
        closeDialog() {
            closeDialog(this.$el)
        },
        addRow() {
            this.items.unshift(emptyRow())
        },
        delaySubmit() {
            // make sure comboboxes are saved
            return new Promise(resolve => setTimeout(() => resolve(this.submit()), 100))
        },
        updateValid() {
            this.items.forEach((item, index) => {
                const valid = !!(item.ip || item.mac_address)

                if (!!item.valid !== valid) {
                    this.$set(this.items[index], 'valid', valid)
                }
                if (
                    this.errors.length > index &&
                    this.errors[index] &&
                    Object.keys(this.errors[index]).length
                ) {
                    this.$set(this.items[index], 'errors', this.errors[index])
                } else if (item.errors) {
                    this.$delete(this.items[index], 'errors')
                }
            })
            if (this.items[this.items.length - 1].title) {
                this.items.push(emptyRow())
            }
            this.$refs.form.validate()
        },
        selectAll(selected) {
            this.items.forEach(e => {
                this.$set(e, 'enabled', selected)
            })
        },
        submit() {
            if (!this.$refs.form.validate()) return
            this.formLoading = true
            const data = this.activeItems.map(item => ({
                ...this.form,
                ...item,
                password: item.try_standard_passwords ? '__try__' : item.password,
                room_capacity: item.room_capacity || null,
                location: !item.location ? '' : item.location
            }))

            return this.$store
                .dispatch('endpoint/createEndpointBulk', data)
                .then(endpoints => {
                    this.formLoading = false
                    this.errors = {}
                    this.items = [...Array(3).keys()].map(() => emptyRow())
                    this.$emit('complete', endpoints)
                })
                .catch(e => {
                    this.formLoading = false
                    if (e.errors) {
                        this.errors = e.errors
                    } else {
                        this.error = e
                    }
                })
        },
        removeItem(_id) {
            const index = this.items.findIndex(item => item._id == _id)
            this.items.splice(index, 1)
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
        cancel() {
            closeDialog(this.$vnode)
        },
    },
}
</script>

<style>
.scrollwrap_1600 .v-data-table__wrapper {
    width: 1600px;
}
</style>
