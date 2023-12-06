<template>
    <v-form
        v-if="!loading"
        ref="form"
        v-model="formValid"
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
                <span v-if="approval"><translate>Godkänn system</translate></span>
                <span v-else-if="id"><translate>Redigera system</translate></span>
                <span v-else><translate>Lägg till system</translate></span>
            </v-card-title>
            <v-divider />
            <v-card-text>
                <v-alert
                    v-if="licenseError"
                    color="error"
                    icon="mdi-alert-circle"
                    text
                >
                    {{ licenseError }}
                </v-alert>

                <v-text-field
                    v-model="form.title"
                    :error-messages="errors.title ? errors.title : []"
                    :rules="rules.title"
                    :label="$gettext('Namn')"
                    :placeholder="$gettext('Hämtas automatiskt från system')"
                />

                <v-select
                    v-model="form.manufacturer"
                    :error-messages="errors.manufacturer ? errors.manufacturer : []"
                    :items="endpointManufacturerChoices"
                    item-text="title"
                    item-value="id"
                    :rules="rules.manufacturer"
                    :label="$gettext('Typ av system')"
                />
                <v-alert
                    v-if="id && form.title !== loadedData.title"
                    type="info"
                >
                    <translate>Notera att namn och uppringningsinställningar måste provisioneras för att de ska skrivas till systemet</translate>
                </v-alert>

                <v-text-field
                    v-model="form.username"
                    :error-messages="errors.username ? errors.username : []"
                    :rules="rules.username"
                    :counter="50"
                    :label="$gettext('Användarnamn')"
                />

                <v-row>
                    <v-col cols="6">
                        <v-checkbox
                            v-model="form.try_standard_passwords"
                            :label="$gettext('Logga in med standardlösenord')"
                        />
                    </v-col>
                    <v-col cols="6">
                        <v-text-field
                            v-if="!form.try_standard_passwords"
                            v-model="form.password"
                            type="password"
                            :error-messages="errors.password ? errors.password : []"
                            :rules="rules.password"
                            :label="$gettext('Skriv in lösenord manuellt') + ' (*)'"
                        />
                    </v-col>
                </v-row>

                <v-row>
                    <v-col cols="8">
                        <v-text-field
                            v-model="form.ip"
                            :error-messages="errors.ip ? errors.ip : []"
                            :rules="rules.ip"
                            :label="$gettext('IP-nummer')"
                        />
                    </v-col>
                    <v-col cols="4">
                        <v-text-field
                            v-model.number="form.api_port"
                            :error-messages="errors.api_port ? errors.api_port : []"
                            :rules="rules.api_port"
                            :label="$gettext('Port till webbgränssnitt')"
                            hide-details="auto"
                        />
                    </v-col>
                </v-row>

                <v-text-field
                    v-model="form.hostname"
                    :error-messages="errors.hostname ? errors.hostname : []"
                    :rules="rules.hostname"
                    :counter="100"
                    :label="$gettext('Fullständigt DNS värdnamn')"
                />

                <v-checkbox
                    v-model="form.track_ip_changes"
                    :label="$gettext('Uppdatera IP-uppgifter automatiskt när de skickas från systemet')"
                    :hint="$gettext('Kräver att inställningar för live-events provisioneras')"
                />

                <v-select
                    v-model="form.connection_type"
                    :label="$gettext('Typ av anslutning')"
                    :error-messages="errors.connection_type ? errors.connection_type : []"
                    :items="connection_types"
                    item-text="name"
                    item-value="id"
                />
                <EndpointProxyPicker
                    v-if="form.connection_type === 2"
                    v-model="form.proxy"
                    :label="$gettext('Proxy')"
                />

                <span
                    v-if="form.connection_type === 0"
                ><i v-translate>Stödjer endast firmwareuppgradering och konfigurationsändringar. Kräver att inställningar för passiv provisionering aktiveras i systemet</i></span>

                <v-text-field
                    v-model="form.mac_address"
                    :error-messages="errors.mac_address ? errors.mac_address : []"
                    :rules="rules.mac_address"
                    :counter="100"
                    :label="$gettext('MAC-adress')"
                />

                <v-text-field
                    v-model="form.serial_number"
                    :error-messages="errors.serial_number ? errors.serial_number : []"
                    :rules="rules.serial_number"
                    :counter="100"
                    :label="$gettext('Serienummer')"
                />

                <v-combobox
                    v-model="form.location"
                    :label="$gettext('Plats')"
                    :items="locations"
                />

                <OrganizationPicker
                    v-model="form.org_unit"
                    :label="$gettext('Organisationsenhet')"
                />

                <v-text-field
                    v-model.number="form.room_capacity"
                    :label="$gettext('Antal platser i rum')"
                />

                <v-checkbox
                    v-model="form.personal_system"
                    :label="$gettext('Personligt system')"
                />

                <v-text-field
                    v-if="form.personal_system || form.owner_email_address"
                    v-model="form.owner_email_address"
                    :label="$gettext('E-postadress till person')"
                />

                <div v-if="id">
                    <v-combobox
                        v-model="form.sip_aliases"
                        :label="$gettext('SIP/e-postalias')"
                        :hint="$gettext('Matcha alternativa adresser för autouppringning/ad-hoc samtal eller e-postinbjudningar')"
                        chips
                        multiple
                    />

                    <v-select
                        v-model="form.dial_protocol"
                        :error-messages="errors.dial_protocol ? errors.dial_protocol : []"
                        :rules="rules.dial_protocol"
                        :items="dial_protocols"
                        item-text="title"
                        item-value="key"
                        :label="$gettext('Protokoll för uppringning')"
                    />

                    <v-alert
                        v-if="changed"
                        type="info"
                    >
                        <translate>Notera att namn och uppringningsinställningar måste provisioneras för att de ska skrivas till systemet</translate>
                    </v-alert>
                    <v-text-field
                        v-model="form.sip"
                        :error-messages="errors.sip ? errors.sip : []"
                        :rules="rules.sip"
                        :counter="100"
                        :label="$gettext('SIP')"
                        :disabled="cloudRegistered"
                        :placeholder="$gettext('Hämtas automatiskt från system')"
                    />
                    <v-text-field
                        v-model="form.h323"
                        :error-messages="errors.h323 ? errors.h323 : []"
                        :rules="rules.h323"
                        :counter="49"
                        :label="$gettext('H323')"
                        :disabled="cloudRegistered"
                        :placeholder="$gettext('Hämtas automatiskt från system')"
                    />
                    <v-text-field
                        v-model="form.h323_e164"
                        :error-messages="errors.h323_e164 ? errors.h323_e164 : []"
                        :rules="rules.h323_e164"
                        :counter="30"
                        :label="$gettext('H323 E.164')"
                        :disabled="cloudRegistered"
                        :placeholder="$gettext('Hämtas automatiskt från system')"
                    />
                    <v-text-field
                        v-model="form.external_manager_service"
                        :error-messages="errors.external_manager_service ? errors.external_manager_service : []"
                        :label="$gettext('URL till extern provisionerings-service')"
                        :counter="255"
                        :hint="$gettext('För att kunna använda en provisioneringtjänst i passive läge. Ex.') + ' https://example.org/tms/public/external/management/systemmanagementservice.asmx'"
                    />
                    <v-checkbox
                        v-model="form.hide_from_addressbook"
                        :label="$gettext('Dölj i adressböcker')"
                    />
                </div>
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
                    :disabled="!formValid || !!licenseError"
                    :loading="formLoading"
                    color="primary"
                    type="submit"
                >
                    <span v-if="approval">{{ $gettext('Godkänn') }}</span>
                    <span v-else-if="id">{{ $gettext('Uppdatera') }}</span>
                    <span v-else>{{ buttonText }}</span>
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

import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'
import EndpointProxyPicker from '../endpointproxy/EndpointProxyPicker'
import { endpointManufacturerChoices } from '@/vue/store/modules/endpoint/consts'

export default {
    components: {EndpointProxyPicker, OrganizationPicker },
    mixins: [EndpointLicenseMixin],
    props: {
        id: { type: Number, default: null, required: false },
        initialData: { type: Object, required: false, default() { return {} } },
        buttonText: { type: String, default: $gettext('Lägg till') },
        approval: { type: Boolean, default: false },
    },
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            loading: false,
            error: '',
            formLoading: false,
            formValid: false,
            changed: false,
            loadedData: {},
            endpointManufacturerChoices,
            form: {
                title: '',
                hostname: '',
                sip: '',
                connection_type: 1,
                proxy: null,
                h323: '',
                h323_e164: '',
                mac_address: '',
                serial_number: '',
                manufacturer: 10,
                ip: '',
                api_port: 443,
                room_capacity: null,
                hide_from_addressbook: false,
                personal_system: false,
                owner_email_address: '',
                track_ip_changes: true,
                dial_protocol: '',
                location: '',
                username: 'admin',
                password: '',
                org_unit: null,
                try_standard_passwords: !this.id,
                sip_aliases: [],
                external_manager_service: '',
                ...(this.initialData || {}),
            },
            rules: {
                id: [v => !isNaN(parseInt(v)) || $gettext('Värdet måste vara ett tal')],
                manufacturer: [v => !!v || $gettext('Värdet måste fyllas i')],
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
            locations: [],
            errors: {},
        }
    },
    computed: {
        cloudRegistered() {
            if (!this.id) return false
            return this.loadedData.webex_registration || this.loadedData.pexip_registration
        },
    },
    watch: {
        'form.title': function() {
            this.errors.title = null
        },
        'form.hostname': function() {
            this.errors.hostname = null
            this.errors.connection_type = null
        },
        'form.sip': function() {
            this.errors.sip = null
            if (this.form.sip !== this.loadedData.sip) this.changed = true
        },
        'form.mac_address': function() {
            this.errors.mac_address = null
            if (this.form.mac_address !== this.loadedData.mac_address) this.changed = true
        },
        'form.h323': function() {
            this.errors.h323 = null
            if (this.form.h323 !== this.loadedData.h323) this.changed = true
        },
        'form.location': function() {
            this.errors.location = null
        },
        'form.h323_e164': function() {
            this.errors.h323_e164 = null
            if (this.form.h323_e164 !== this.loadedData.h323_e164) this.changed = true
        },
        'form.external_manager_service': function() {
            this.errors.external_manager_service = null
        },
        'form.manufacturer': function() {
            this.errors.manufacturer = null
        },
        'form.ip': function() {
            this.errors.ip = null
            this.errors.connection_type = null
        },
        'form.connection_type': function() {
            this.errors.connection_type = null
        },
        'form.api_port': function() {
            this.errors.api_port = null
        },
        'form.username': function() {
            this.errors.username = null
        },
        'form.password': function() {
            this.errors.password = null
        },
        'form.proxy': function(newValue) {
            if (newValue === undefined) this.form.proxy = null
        },
        'form.dial_protocol': function(newValue) {
            if (newValue === undefined) this.form.dial_protocol = ''
        },
    },
    mounted() {
        this.loading = true
        return Promise.all([
            this.loadObject(),
            this.$store.dispatch('endpoint/getFilters'),
            this.$store.dispatch('endpoint/getSettings'),
        ]).then(values => {
            this.form = { ...this.form, ...values[0] }
            this.loadedData = values[0]
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
        delaySubmit() {
            // make sure comboboxes are saved
            return new Promise(resolve => setTimeout(() => resolve(this.submit()), 100))
        },
        setSIPAliases(id) {
            return this.$store
                .dispatch('endpoint/setSIPAliases', { endpointId: id, aliases: this.aliases })
                .then(() => {
                    this.createdSnackbar = true
                })
        },
        serializeData() {
            return {
                ...this.form,
                password: this.form.try_standard_passwords ? '__try__' : this.form.password,
                room_capacity: this.form.room_capacity || null,
                api_port: this.form.api_port || undefined,
                sip_aliases: undefined,
            }
        },
        submit() {
            if (!this.$refs.form.validate()) return
            this.formLoading = true
            const { id } = this
            const form = this.serializeData()

            const action = !id
                ? this.$store.dispatch('endpoint/createEndpoint', form)
                : this.$store.dispatch('endpoint/updateEndpoint', {
                    id,
                    data: form,
                })
            return action
                .then(async endpoint => {
                    this.formLoading = false
                    this.errors = {}
                    if (id) {
                        await this.$store.dispatch('endpoint/setSIPAliases', {
                            endpointId: id,
                            aliases: this.form.sip_aliases,
                        })
                    }
                    this.$emit('complete', endpoint)
                })
                .catch(e => {
                    this.formLoading = false

                    if (e.errors) {
                        this.errors = e.errors
                        if (e.error) {
                            this.error = e.error
                        }
                    } else {
                        this.error = e
                    }
                })
        },
        loadObject() {
            return this.id
                ? this.$store.dispatch('endpoint/getEndpoint', this.id)
                : Promise.resolve(this.initialData || {})
        },
    },
}
</script>
