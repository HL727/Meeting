<template>
    <v-form @submit.prevent="delaySubmit">
        <div
            v-if="loading"
            class="mt-4"
            style="max-width: 40rem"
        >
            <v-progress-linear
                indeterminate
                color="primary"
            />
            <v-skeleton-loader
                min-height="800"
                type="list-item@8"
            />
        </div>
        <div
            v-else
            class="mt-4"
            style="max-width: 40rem"
        >
            <v-card class="mb-4">
                <v-card-title><translate>Bas</translate></v-card-title>
                <v-card-text>
                    <v-select
                        v-model="form.default_address_book"
                        :label="$gettext('Förvald adressbok')"
                        :items="addressBooks"
                        item-text="title"
                        item-value="id"
                    />
                    <v-select
                        v-if="$store.state.site.enableCore"
                        v-model="form.default_portal_address_book"
                        :label="$gettext('Adressbok för sökningar i bokningsportalen')"
                        :items="addressBooks"
                        item-text="title"
                        item-value="id"
                    />
                    <v-select
                        v-model="form.default_branding_profile"
                        :label="$gettext('Förvald brandingprofil')"
                        :items="brandingProfiles"
                        item-text="name"
                        item-value="id"
                    />

                    <v-text-field
                        v-model.number="form.http_feedback_slot"
                        :label="$gettext('HTTP Feedback Slot')"
                        :rules="rules.http_feedback_slot"
                    />

                    <v-row>
                        <v-col>
                            <v-text-field
                                v-model.number="form.night_first_hour"
                                :label="$gettext('Första timme för nattetid')"
                            />
                        </v-col>
                        <v-col>
                            <v-text-field
                                v-model.number="form.night_last_hour"
                                :label="$gettext('Sista timme för nattetid')"
                            />
                        </v-col>
                    </v-row>
                </v-card-text>
            </v-card>

            <v-card class="mb-4">
                <v-card-title><translate>Säkerhet och sekretess</translate></v-card-title>
                <v-card-text>
                    <v-combobox
                        multiple
                        chips
                        :label="$gettext('Standardlösenord')"
                        :hint="$gettext('Tabb-separerad')"
                        :value="maskedPasswords"
                        item-text="masked"
                        item-value="value"
                        @input="passwords = $event"
                    />

                    <v-checkbox
                        v-model="form.enable_user_debug_statistics"
                        :label="$gettext('Aktivera debugrapporter för användare utan administratörsrättigheter')"
                    />

                    <v-text-field
                        v-model="form.secret_key"
                        :label="$gettext('Adressnyckel för passiv provisionering')"
                        :hint="$gettext('Notera att nyckeln för ev. befintliga system måste ändras manuellt direkt i systemet')"
                    />

                    <v-text-field
                        v-model="form.proxy_password"
                        :label="$gettext('Lösenord för proxy-klienter')"
                        :hint="$gettext('Lämna tomt för att inte kräva lösenord')"
                    />

                    <v-textarea
                        v-model="form.ca_certificates"
                        :label="$gettext('Publika CA-certifikat')"
                        :hint="$gettext('Ett eller flera efter varandra, PEM-format.') + ' --- BEGIN CERTIFICATE --- [...] -----END CERTIFICATE----- [...]'"
                    />
                </v-card-text>
            </v-card>

            <v-card class="mb-4">
                <v-card-title><translate>Uppringningsinställningar</translate></v-card-title>
                <v-card-text>
                    <v-select
                        v-model="form.dial_protocol"
                        :items="dial_protocols"
                        item-text="title"
                        item-value="key"
                        :label="$gettext('Protokoll för uppringning')"
                    />

                    <EndpointProxyPicker
                        v-model="form.default_proxy"
                        :label="$gettext('Använd proxy som standard')"
                    />

                    <v-text-field
                        v-model="form.sip_proxy"
                        :label="$gettext('Standard SIP-proxy')"
                        :rules="rules.sip_proxy"
                    />

                    <v-text-field
                        v-model="form.sip_proxy_username"
                        :label="$gettext('Standard SIP-proxy användarnamn')"
                        :rules="rules.sip_proxy_username"
                    />

                    <v-text-field
                        v-model="form.sip_proxy_password"
                        :label="$gettext('Standard SIP-proxy lösenord')"
                        type="password"
                        :rules="rules.sip_proxy_password"
                    />

                    <v-text-field
                        v-model="form.h323_gatekeeper"
                        :label="$gettext('Standard H323 Gatekeeper')"
                        :rules="rules.h323_gatekeeper"
                    />
                </v-card-text>
            </v-card>

            <v-card class="mb-4">
                <v-card-title><translate>Bokade möten</translate></v-card-title>
                <v-card-text>
                    <v-text-field
                        v-model="form.booking_time_before"
                        :label="$gettext('Minuter i förväg att visa OBTP-möten')"
                    />
                    <v-combobox
                        v-model="domains"
                        multiple
                        chips
                        :label="$gettext('Tillåt e-postinbjudningar från dessa domäner')"
                        :hint="$gettext('Tabb-separerad')"
                    />
                    <v-checkbox
                        v-if="$store.state.site.enableObtp"
                        v-model="form.enable_obtp"
                        :label="$gettext('Aktivera OBTP för Rooms')"
                    />
                    <v-text-field
                        v-model="form.external_manager_service"
                        :error-messages="errors.external_manager_service ? errors.external_manager_service : []"
                        :counter="255"
                        :label="$gettext('URL till extern provisionerings-service')"
                        :hint="$gettext('För att kunna använda en provisioneringtjänst i passive läge. Ex.') + ' https://example.org/tms/public/external/management/systemmanagementservice.asmx'"
                    />
                </v-card-text>
            </v-card>

            <v-card class="mb-4">
                <v-card-title><translate>Nya system</translate></v-card-title>
                <v-card-text>
                    <v-combobox
                        v-model="ip_nets"
                        multiple
                        chips
                        :label="$gettext('Registrera nya system automatiskt från dessa ip-serier')"
                        :hint="$gettext('Tabb-separerad. Använd 0.0.0.0/0 för samtliga')"
                        item-value="ip_net"
                        item-text="ip_net"
                    />

                    <div v-if="passwords.length">
                        <v-checkbox
                            v-model="form.use_standard_password"
                            :label="$gettext('Godkänn automatiskt och försök skapa aktiv anslutning')"
                        />
                        <p><i v-translate>Notera att standardlösenord kommer skickas vidare</i></p>
                    </div>
                </v-card-text>
            </v-card>

            <ErrorMessage :error="error" />

            <v-btn
                color="primary"
                type="submit"
                :loading="saving"
                :disabled="saving"
            >
                <translate>Spara</translate>
            </v-btn>
        </div>

        <v-snackbar
            v-model="snackbar"
            :timeout="timeout"
        >
            <translate>Ändringarna är nu sparade</translate>
            <v-btn
                color="blue"
                text
                @click="snackbar = false"
            >
                <translate>Close</translate>
            </v-btn>
        </v-snackbar>
    </v-form>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import EndpointProxyPicker from '../../components/epm/endpointproxy/EndpointProxyPicker'
import { PLACEHOLDER_PASSWORD } from '@/vue/store/modules/endpoint/consts'
import ErrorMessage from '@/vue/components/base/ErrorMessage'



export default {
    name: 'CustomerSettings',
    components: {ErrorMessage, EndpointProxyPicker},
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            emitter: new GlobalEventBus(this),
            form: {
                default_address_book: null,
                default_portal_address_book: null,
                default_branding_profile: null,
                default_proxy: null,
                booking_time_before: null,
                use_standard_password: null,
                dial_protocol: 'SIP',
                http_feedback_slot: 4,
                sip_proxy: '',
                sip_proxy_username: '',
                sip_proxy_password: PLACEHOLDER_PASSWORD,
                h323_gatekeeper: '',
                enable_obtp: true,
                external_manager_service: '',
                enable_user_debug_statistics: false,
                secret_key: '',
                proxy_password: '',
                ca_certificates: '',
                night_first_hour: 23,
                night_last_hour: 4,
                id: null,
            },
            loading: true,
            saving: false,
            snackbar: false,
            error: null,
            errors: {},
            timeout: 2000,
            passwords: [],
            domains: [],
            rules: {
                http_feedback_slot: [(x) => (x && x.toString().match(/^[1-4]$/) ? true : $gettext('Ett tal mellan 1-4'))]
            },
            ip_nets: [],
            dial_protocols: [
                { key: 'SIP', title: $gettext('SIP') },
                { key: 'H323', title: $gettext('H323') },
                { key: 'H320', title: $gettext('H320') },
            ],
        }
    },
    computed: {
        brandingProfiles() {
            return Object.values(this.$store.state.endpoint_branding.profiles)
        },
        addressBooks() {
            return this.$store.getters['addressbook/addressBooks']
        },
        maskedPasswords() {
            const mask = p => {
                if (p.length < 2) return p
                return p.substr(0, 1) + '*'.repeat(p.length - 2) + p.substr(-1)
            }
            return (this.passwords || []).map(p => (p.masked ? p : { masked: mask(p), value: p }))
        },
    },
    mounted() {
        this.emitter.on('refresh', () => this.loadData())
        return this.loadData()
    },
    methods: {
        delaySubmit() {
            // make sure comboboxes are saved
            return new Promise(resolve => setTimeout(() => resolve(this.save()), 100))
        },
        serializeForm() {
            const passwords = this.passwords.map(p => (p.masked ? p.value : p))
            const ip_nets = this.ip_nets.map(n => (n.ip_net ? n.ip_net : n))
            const domains = this.domains.map(d => (d.domain ? d.domain : d))

            const result = { ...this.form, passwords, ip_nets, domains }
            if (this.sip_proxy_password == PLACEHOLDER_PASSWORD) result.sip_proxy_password = undefined
            if (this.form.enable_obtp) result.external_manager_service = ''
            return result
        },
        save() {

            this.saving = true
            this.error = null
            this.errors = {}

            this.$store.dispatch('endpoint/setSettings', this.serializeForm()).then(() => {
                this.saving = false
                this.snackbar = true
            }).catch(e => {
                this.saving = false
                this.error = e
                if (e.errors) this.errors = e.errors
            })
        },
        loadData() {
            this.loading = true

            return Promise.all([
                this.$store.dispatch('addressbook/getAddressBooks'),
                this.$store.dispatch('endpoint/getSettings'),
                this.$store.dispatch('endpoint/getDefaultPasswords'),
                this.$store.dispatch('endpoint/getAutoRegisterIpNets'),
                this.$store.dispatch('endpoint/getDomains'),
                this.$store.dispatch('endpoint_branding/loadProfiles'),
            ]).then(values => {
                this.form = JSON.parse(JSON.stringify(values[1]))
                if (this.addressBooks.length === 1) this.form.default_address_book = this.addressBooks[0].id
                if (values[1].has_sip_proxy_password) this.form.sip_proxy_password = PLACEHOLDER_PASSWORD

                this.passwords = values[2].map(p => p.password)
                this.ip_nets = values[3].map(n => n.ip_net)
                this.domains = values[4].map(d => d.domain)

                this.loading = false
                this.emitter.emit('loading', false)
            })
        }
    }
}
</script>

<style scoped></style>
