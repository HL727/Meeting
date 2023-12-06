<template>
    <Page
        :title="cospace.name"
        icon="mdi-door-open"
        :actions="[
            {
                icon: 'mdi-email-outline',
                click: () => ($router.push({name: 'cospaces_invite', params: {id: cospace.id}})),
                hidden: !cospace.id && !loading
            },
            { icon: 'mdi-phone-outgoing', click: () => (dialDialog = true ) },
            { icon: 'mdi-pencil', click: () => (editDialog = true) },
            { type: 'api', url: apiUrl },
            {
                type: 'delete',
                text: $gettext('Är du säker på att du vill ta bort mötesrummet') + ' ' + cospace.name + '?'
            },
            { type: 'refresh', click: () => loadData() },
        ]"
    >
        <template v-slot:content>
            <v-alert
                v-if="error"
                type="error"
                class="my-4"
            >
                {{ error }}
            </v-alert>

            <v-row>
                <v-col
                    cols="12"
                    md="7"
                >
                    <v-skeleton-loader
                        v-if="loading"
                        :loading="loading"
                        type="list-item, list-item, list-item"
                        class="mt-4"
                    />
                    <v-simple-table v-else>
                        <tbody>
                            <tr>
                                <th v-translate>
                                    Typ av rum
                                </th>
                                <td>{{ cospace.service_type }}</td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    PIN-kod
                                </th>
                                <td>{{ cospace.pin || $gettext('Nej') }}</td>
                            </tr>
                            <tr v-if="cospace.allow_guests">
                                <th v-translate>
                                    Gäst-PIN
                                </th>
                                <td>{{ cospace.guest_pin }}</td>
                            </tr>
                            <tr v-else>
                                <th v-translate>
                                    Tillåt gäster
                                </th>
                                <td><v-icon>mdi-close</v-icon></td>
                            </tr>

                            <tr>
                                <th v-translate>
                                    Beskrivning
                                </th>
                                <td>{{ cospace.description }}</td>
                            </tr>

                            <tr>
                                <th v-translate>
                                    Web-länk
                                </th>
                                <td>
                                    <ClipboardInput
                                        :value="cospace.web_url"
                                        open-external
                                    />
                                </td>
                            </tr>

                            <tr>
                                <th v-translate>
                                    E-postadress
                                </th>
                                <td>
                                    <ClipboardInput
                                        v-if="cospace.primary_owner_email_address"
                                        :value="cospace.primary_owner_email_address"
                                        open-external
                                        :external-value="'mailto:' + cospace.primary_owner_email_address"
                                    />
                                </td>
                            </tr>

                            <tr v-if="customers.length > 1">
                                <th v-translate>
                                    Kund
                                </th>
                                <td>
                                    <TenantPicker
                                        tenant-field="pexip_tenant_id"
                                        :value="cospace.tenant"
                                        :provider-id="providerId"
                                        @input="setTenant($event)"
                                    />
                                </td>
                            </tr>

                            <tr v-if="enableOrganization">
                                <th v-translate>
                                    Organisationsenhet
                                </th>
                                <td>
                                    <OrganizationPicker
                                        v-model="cospace.organization_unit"
                                        @input="setOrganizationUnit($event)"
                                    />
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>

                    <h3 class="overline my-4">
                        <translate>Senaste samtal</translate>
                    </h3>

                    <v-skeleton-loader
                        v-if="loading"
                        :loading="loading"
                        type="image"
                        height="100"
                    />
                    <v-simple-table v-else-if="latestCalls.length">
                        <thead>
                            <tr>
                                <th v-translate>
                                    Start
                                </th>
                                <th v-translate>
                                    Stop
                                </th>
                                <th v-translate>
                                    Längd (timmar)
                                </th>
                                <th
                                    v-translate
                                    :colspan="settings.perms.staff ? 2 : 1"
                                >
                                    Deltagare
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="call in latestCalls"
                                :key="'call' + call.id"
                            >
                                <td>{{ call.ts_start || $gettext('Okänt') }}</td>
                                <td>{{ call.ts_stop || $gettext('Okänt') }}</td>
                                <td>{{ call.duration }}</td>
                                <td>{{ call.leg_count || call.ts_stop ? call.leg_count : '' }}</td>
                                <td
                                    v-if="settings.perms.staff"
                                    class="text-right"
                                >
                                    <v-btn
                                        color="lime darken-2"
                                        :dark="!!call.debugUrl"
                                        x-small
                                        :to="call.debugUrl"
                                        :disabled="!call.debugUrl"
                                    >
                                        <v-icon left>
                                            mdi-bug
                                        </v-icon>
                                        debug
                                    </v-btn>
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                    <v-alert
                        v-else
                        type="info"
                        outlined
                    >
                        <translate>Har inga senaste samtal</translate>
                    </v-alert>
                </v-col>
                <v-col
                    cols="12"
                    md="5"
                >
                    <v-alert
                        v-if="!loading && !!cospace.ongoing_calls.length"
                        color="error"
                        text
                        icon="mdi-phone-in-talk"
                        prominent
                        class="my-4"
                    >
                        <p class="mb-2">
                            <strong><translate>Pågående samtal</translate></strong>
                        </p>
                        <ul class="mb-0">
                            <li
                                v-for="call in cospace.ongoing_calls"
                                :key="'call' + call.id"
                            >
                                <router-link
                                    :to="{
                                        name: 'call_details_pexip',
                                        params: { id: call.id },
                                        query: {
                                            cospace: cospace.name,
                                        },
                                    }"
                                >
                                    {{ call.name || '-- No name --' }}
                                </router-link>
                            </li>
                        </ul>
                    </v-alert>

                    <h3 class="overline my-4">
                        <translate>Alias</translate>
                    </h3>
                    <v-skeleton-loader
                        v-if="loading"
                        :loading="loading"
                        type="image"
                        height="100"
                    />
                    <v-card v-else-if="cospace.aliases && cospace.aliases.length">
                        <v-card-text>
                            <div
                                v-for="alias in cospace.aliases"
                                :key="'alias' + alias.id"
                            >
                                <ClipboardInput
                                    :label="alias.description || ''"
                                    :value="alias.alias"
                                    :open-external="alias.alias.indexOf('@') != -1"
                                    :external-value="'sip:' + alias.alias"
                                />
                            </div>
                        </v-card-text>
                    </v-card>
                    <v-alert
                        v-else
                        type="info"
                        outlined
                    >
                        <translate>Har just nu inga alias kopplade</translate>
                    </v-alert>

                    <h3 class="overline my-4">
                        <translate>Medlemmar</translate>
                    </h3>
                    <v-skeleton-loader
                        v-if="loading"
                        :loading="loading"
                        type="image"
                        height="100"
                    />
                    <v-card v-else-if="cospace.members && cospace.members.length">
                        <v-list-item
                            v-for="user in cospace.members"
                            :key="'user' + user.id"
                            :two-line="!!cospace.call_id"
                            :to="{ name: 'pexip_user_details', params: { id: user.id } }"
                        >
                            <v-icon class="align-self-center mr-4">
                                mdi-account
                            </v-icon>
                            <v-list-item-content>
                                <v-list-item-title>
                                    {{ user.name || user.email }}
                                </v-list-item-title>
                                <v-list-item-subtitle v-if="user.name && user.email">
                                    {{ user.email }}
                                </v-list-item-subtitle>
                            </v-list-item-content>
                        </v-list-item>
                    </v-card>
                    <v-alert
                        v-else
                        type="info"
                        outlined
                    >
                        <translate>Mötesrummet har just nu inga medlemmar</translate>
                    </v-alert>
                </v-col>
            </v-row>

            <v-dialog
                v-model="editDialog"
                scrollable
                max-width="620"
            >
                <PexipCoSpacesForm
                    v-if="editDialog"
                    :id="cospace.id"
                    @created="loadData"
                    @cancel="editDialog = false"
                />
            </v-dialog>

            <v-dialog
                v-model="dialDialog"
                scrollable
                :max-width="500"
            >
                <DialParticipantForm
                    show-cancel
                    :call-from-choices="aliasUris"
                    @complete="loadData"
                />
            </v-dialog>
        </template>
    </Page>
</template>

<script>
import moment from 'moment'
import { GlobalEventBus } from '@/vue/helpers/events'
import Page from '@/vue/views/layout/Page'
import PexipCoSpacesForm from '@/vue/components/cospace/PexipCoSpacesForm'
import TenantPicker from '../../components/tenant/TenantPicker'
import ClipboardInput from '@/vue/components/ClipboardInput'
import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'
import DialParticipantForm from '@/vue/components/call/DialParticipantForm'

export default {
    name: 'PexipCoSpaceDetails',
    components: { DialParticipantForm, Page, ClipboardInput, TenantPicker, PexipCoSpacesForm, OrganizationPicker },
    mixins: [PageSearchMixin],
    props: {
        id: {
            type: Number,
            required: true,
        }
    },
    data() {
        return {
            emitter: new GlobalEventBus(this),
            editDialog: false,
            dialDialog: false,
            cospaceData: {},
            error: '',
            refreshTimeout: null
        }
    },
    computed: {
        enableOrganization() {
            return this.$store.state.site.enableOrganization
        },
        settings() {
            return this.$store.state.site || {}
        },
        apiUrl() {
            return `configuration/v1/conference/${this.cospace.id}/`
        },
        cospace() {
            if (this.cospaceData && this.cospaceData.aliases) {
                return this.cospaceData
            }
            return {
                aliases: [],
                ongoing_calls: [],
            }
        },
        aliases() {
            if (!this.cospace || !this.cospace.aliases || ! this.cospace.aliases.length) return []
            return this.cospace.aliases
        },
        aliasUris() {
            return this.aliases.map(a => a.alias)
        },
        latestCalls() {
            const calls = this.cospace.latest_calls || []
            return calls.map(c => {
                return {
                    ...c,
                    ts_start: c.ts_start ? moment(c.ts_start).format('YYYY-MM-DD HH:mm:ss') : null,
                    ts_stop: c.ts_stop ? moment(c.ts_stop).format('YYYY-MM-DD HH:mm:ss') : null,
                    duration: (c.duration / 60 / 60).toFixed(2),
                    debugUrl: (c.guid || c.id) ? `/stats/debug/call/${c.guid || c.id}` : null
                }
            })
        },
        customers() {
            return Object.values(this.$store.state.site.customers)
        },
        providerId() {
            return this.$store.state.site.providerId
        },
    },
    mounted() {
        this.emitter.on('delete', () => this.deleteCoSpace())
        this.loadData()
    },
    destroyed() {
        clearTimeout(this.refreshTimeout)
    },
    methods: {
        deleteCoSpace() {
            return this.$store.dispatch('cospace/pexip/delete', this.id).then(() => {
                this.$router.push({name: 'cospaces_list'})
            })
        },
        setLoadDataTimeout() {
            clearTimeout(this.refreshTimeout)
            this.refreshTimeout = setTimeout(() => {
                this.loadData(true)
            }, 5000)
        },
        loadData(silent) {
            if (!silent) {
                this.setLoading(true)
                this.editDialog = false
            }

            this.$store.dispatch('cospace/pexip/get', this.id).then((cospace) => {
                this.setLoading(false)
                this.setLoadDataTimeout()
                this.cospaceData = {
                    ...cospace,
                    loaded: true,
                }
            }).catch(e => {
                this.setLoading(false)
                this.error = e.toString()
            })
        },
        setTenant(customer) {
            return this.$store.dispatch('cospace/pexip/update', {id: this.id, tenant: customer.pexip_tenant_id})
        },
        setOrganizationUnit(organizationUnit) {
            return this.$store.dispatch('cospace/pexip/update', {id: this.id, organization_unit: organizationUnit})
        }
    }
}
</script>
