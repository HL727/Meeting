<template>
    <Page
        icon="mdi-view-dashboard-outline"
        :title="$gettext('Dashboard')"
        :actions="[{ type: 'refresh', click: () => loadData() }]"
    >
        <template v-slot:content>
            <div
                class="mb-6"
                style="position:relative;"
            >
                <v-progress-linear
                    :active="loading"
                    indeterminate
                    absolute
                    top
                />
            </div>

            <v-row>
                <v-col
                    cols="12"
                    md="8"
                    style="position:relative;"
                >
                    <img
                        :src="illustration"
                        class="stats-illustration d-none d-sm-block ml-auto"
                        style="max-width:60%;position:absolute;top:-3rem;right:1rem;z-index:4;"
                    >

                    <p class="overline">
                        <translate>System</translate>
                    </p>

                    <v-list
                        dense
                        :style="{ maxWidth: $vuetify.breakpoint.smAndUp ? '30%' : '' }"
                        class="mb-8"
                    >
                        <v-list-item :to="{ name: 'epm_list' }">
                            <v-list-item-content>
                                <v-list-item-title><translate>Hanterade system</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ endpointStats.total }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item :to="{ name: 'epm_task_list' }">
                            <v-list-item-content>
                                <v-list-item-title><translate>Åtgärder i kö</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ taskStats.pending }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item :to="{ name: 'epm_incoming' }">
                            <v-list-item-content>
                                <v-list-item-title><translate>Ej godkända system</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ endpointStats.incoming }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item :to="{ name: 'epm_list', query: { status_code: 20 } }">
                            <v-list-item-content>
                                <v-list-item-title><translate>System i samtal</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ endpointStats.inCall }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item :to="{ name: 'epm_list', query: { online: 1 } }">
                            <v-list-item-content>
                                <v-list-item-title><translate>System online</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ endpointStats.online }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item :to="{ name: 'epm_list', query: { status__has_warnings: 'true' } }">
                            <v-list-item-content>
                                <v-list-item-title><translate>System med varningar</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ endpointStats.warnings }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                    </v-list>

                    <p class="overline">
                        <translate>Översikt</translate>
                    </p>

                    <DashboardOverview :items="overview">
                        <template v-slot:item>
                            <v-spacer />
                        </template>
                    </DashboardOverview>
                </v-col>
                <v-col
                    cols="12"
                    md="4"
                >
                    <v-expansion-panels
                        v-if="providers.server"
                        v-model="productVersionPanel"
                        class="mb-6"
                    >
                        <ServerStatus
                            :loading="loading"
                            :server="providers.server"
                            :license-status="licenseStatusLabel"
                            :license-icon="licenseStatusIcon"
                            :license-color="licenseStatusColor"
                            :warnings="licenseWarnings"
                            title="Mividas Rooms"
                        >
                            <template v-slot:extraRows>
                                <tr v-if="licenseHasDetails">
                                    <th class="text-left">
                                        {{ $ngettext('System', 'System', 2) }}
                                    </th>
                                    <td
                                        v-if="licenseStatus.licensed === -1"
                                        key="unlimited"
                                        class="text-right"
                                    >
                                        <translate :translate-params="{active: licenseStatus.active}">
                                            %{active} licensierade system
                                        </translate>
                                    </td>
                                    <td
                                        v-else
                                        key="limited"
                                        class="text-right"
                                    >
                                        <translate :translate-params="{active: licenseStatus.active, licensed: licenseStatus.licensed}">
                                            %{active} av %{licensed} licensierade system
                                        </translate>
                                        <v-progress-linear
                                            class="mt-2"
                                            :color="licenseOveruse ? 'error': 'success'"
                                            :value="licenseProgress"
                                        />
                                    </td>
                                </tr>
                            </template>
                        </ServerStatus>
                    </v-expansion-panels>

                    <p class="overline">
                        <translate>Provisionering</translate>
                    </p>

                    <ProvisionSettingsWidget />

                    <v-card
                        v-if="proxies.length && proxiesSummary.new"
                        class="mb-6"
                        :loading="loading"
                    >
                        <v-card-title class="mb-2">
                            <v-icon large>
                                mdi-weather-cloudy-arrow-right
                            </v-icon>
                            <translate>Proxyklienter</translate>
                        </v-card-title>

                        <v-navigation-drawer
                            class="grey lighten-4"
                            width="100%"
                            floating
                            permanent
                        >
                            <v-list>
                                <v-list-item
                                    v-if="proxiesSummary.new > 0"
                                    link
                                    :to="{ name: 'epm_proxies' }"
                                >
                                    <v-list-item-icon>
                                        <v-icon color="orange">
                                            mdi-new-box
                                        </v-icon>
                                    </v-list-item-icon>
                                    <v-list-item-content>
                                        <v-list-item-title><translate>Väntar på godkännande</translate></v-list-item-title>
                                    </v-list-item-content>
                                    <v-chip
                                        :pill="true"
                                        :input-value="true"
                                    >
                                        {{ proxiesSummary.new }}
                                    </v-chip>
                                </v-list-item>
                                <v-list-item
                                    link
                                    :to="{ name: 'epm_proxies' }"
                                >
                                    <v-list-item-icon>
                                        <v-icon color="primary">
                                            mdi-arrow-right
                                        </v-icon>
                                    </v-list-item-icon>
                                    <v-list-item-content>
                                        <v-list-item-title><translate>Totalt antal proxyklienter</translate></v-list-item-title>
                                    </v-list-item-content>
                                    <v-chip
                                        :pill="true"
                                        :input-value="true"
                                    >
                                        {{ proxiesSummary.total }}
                                    </v-chip>
                                </v-list-item>
                            </v-list>
                        </v-navigation-drawer>
                    </v-card>

                    <v-skeleton-loader
                        v-if="loading"
                        type="list-item-avatar-two-line@2"
                        tile
                        loading
                    />

                    <v-expansion-panels
                        v-if="activeProxies.length"
                        class="mb-4"
                    >
                        <EndpointProxyStatusPanel
                            v-for="(proxy, index) in activeProxies"
                            :key="'proxy' + proxy.id"
                            :proxy="proxy"
                            :counter="index + 1"
                            :max="activeProxies.length"
                        />
                    </v-expansion-panels>

                    <v-expansion-panels v-if="!loading">
                        <VCSEStatus
                            v-for="(server, id, index) in providers.vcs"
                            :key="server.id"
                            :provider="server"
                            :counter="index + 1"
                        />
                    </v-expansion-panels>
                </v-col>
            </v-row>

            <ClipboardSnackbar ref="copySnackbar" />

            <ErrorMessage :error="error" />
        </template>
    </Page>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

import VCSEStatus from '@/vue/components/VCSEStatus'
import ClipboardSnackbar from '@/vue/components/ClipboardSnackbar'
import EndpointProxyStatusPanel from '@/vue/components/endpointproxy/EndpointProxyStatusPanel'
import DashboardOverview from '@/vue/components/dashboard/DashboardOverview'

import EndpointsMixin from '@/vue/views/epm/mixins/EndpointsMixin'
import EndpointLicenseMixin from '@/vue/views/epm/mixins/EndpointLicenseMixin'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'
import ServerStatus from '@/vue/components/ServerStatus'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import ProvisionSettingsWidget from '@/vue/components/epm/ProvisionSettingsWidget'

const statsOverviewTypes = {
    system: {
        title: $gettext('System'),
        icon: 'mdi-google-lens',
        to: { name: 'epm_list' }
    },
    addressBooks: {
        title: $gettext('Adressböcker'),
        icon: 'mdi-notebook-multiple',
        to: { name: 'addressbook_list' }
    },
    firmware: {
        title: $gettext('Firmware'),
        icon: 'mdi-download-network',
        to: { name: 'epm_firmware' }
    },
    meetings: {
        title: $gettext('Bokade möten'),
        icon: 'mdi-calendar',
        to: { name: 'epm_bookings' }
    },
    macros: {
        title: $gettext('Paneler och macron'),
        icon: 'mdi-apps-box',
        to: { name: 'control_list' }
    },
}

export default {
    name: 'EPMDashboard',
    components: { ProvisionSettingsWidget, ErrorMessage, ServerStatus, Page, EndpointProxyStatusPanel, DashboardOverview, VCSEStatus, ClipboardSnackbar },
    mixins: [PageSearchMixin, EndpointLicenseMixin, EndpointsMixin],
    data() {
        return {
            providers: { vcs: {}, server: null },
            provisionAddressType: { type: Number, default: 0 },
            copySnackbar: false,
            illustration: require('@/assets/images/illustrations/rooms-dashboard.svg'),
            productVersionPanel: null,
            statsOverviewTypes,
            error: null,
        }
    },
    computed: {
        licenseWarnings() {
            const warnings = []

            if (this.licenseStatus.status === 'limit') {
                warnings.push({
                    message: $gettext('Överanvändning av era systemlicenser. Inga fler system kan läggas till.'),
                    type: 'error',
                    icon: 'mdi-alert-circle'
                })
            }
            else if (this.licenseStatus.status === 'warning') {
                warnings.push({
                    message: $gettext('Överanvändning av era systemlicenser.'),
                })
            }
            return warnings
        },
        licenseStatusLabel() {
            if (this.licenseStatus.status !== 'ok') {
                return $gettext('Överanvändning')
            }

            return ''
        },
        licenseStatusIcon() {
            if (this.licenseStatus.status === 'limit') {
                return 'mdi-alert-circle'
            }
            else if (this.licenseStatus.status === 'warning') {
                return 'mdi-alert-outline'
            }

            return ''
        },
        licenseStatusColor() {
            if (this.licenseStatus.status === 'limit') {
                return 'error'
            }
            else if (this.licenseStatus.status === 'warning') {
                return 'warning'
            }

            return ''
        },
        overview() {
            const result = { ...this.statsOverviewTypes }

            result.macros.totals = [{
                label: $gettext('Rumskontroller'),
                value: Object.keys(this.$store.state.roomcontrol.controls).length
            },{
                label: $gettext('Samlingar'),
                value: Object.keys(this.$store.state.roomcontrol.templates).length
            }]

            const totals = {
                system: this.endpointStats.total,
                addressBooks: this.$store.getters['addressbook/addressBooks'].length,
                firmware:  Object.keys(this.$store.state.endpoint.firmwares || {}).length,
                meetings: this.$store.getters['endpoint/bookings'].length,
            }

            return Object.entries(result).map(s => {
                if (!(s[0] in totals)) return s[1]

                return {
                    ...s[1],
                    totals: [{
                        label: $gettext('Totalt'),
                        value: totals[s[0]]
                    }]
                }
            })
        },
        proxies() {
            return Object.values(this.$store.state.endpoint.proxies)
        },
        activeProxies() {
            return this.proxies.filter(proxy => !!proxy.ts_activated)
        },
        proxiesSummary() {
            return {
                total: this.proxies.length,
                online: this.proxies.filter(proxy => proxy.is_online).length,
                new: this.proxies.filter(proxy => 'ts_activated' in proxy && !proxy.ts_activated).length,
            }
        },

        settings() {
            return this.$store.state.endpoint.settings
        },
        customerId() {
            return this.$store.state.site.customerId
        },
        incoming() {
            return Object.values(this.$store.state.endpoint.incoming)
        },
        endpointStats() {
            const result = {
                inCall: 0,
                total: this.endpoints.length,
                incoming: this.incoming.length,
                online: 0,
                warnings: 0,
            }

            this.endpoints.forEach(e => {
                if (e.status_code > 0) result.online++
                if (e.status_code === 20) result.inCall++
                if (e.status.has_warnings) result.warnings++
            })
            return result
        },
        taskStats() {
            const tasks = Object.values(this.$store.state.endpoint.tasks)
            const result = {
                count: tasks.length,
                pending: 0,
            }
            tasks.forEach(t => {
                if (t.status === 0) result.pending++
            })
            return result
        },
        provisionUrl() {
            return `https://${window.location.host}/tms/`
        },
    },
    mounted() {
        this.loadData()
    },
    methods: {
        loadData() {
            this.setLoading(true)

            return Promise.all([
                this.$store.dispatch('addressbook/getAddressBooks'),
                this.$store.dispatch('endpoint/getAllBookings').then(b => (this.bookings = b)),
                this.$store.dispatch('endpoint/getTasks'),
                this.$store.dispatch('endpoint/getIncoming'),
                this.$store.dispatch('endpoint/getSettings'),
                this.$store.api().get('provider/status/?type=vcs')
                    .then(r => this.providers.vcs = r),
                this.$store.api().get('provider/status/?type=server')
                    .then(r => this.providers.server = r),
                this.$store.dispatch('endpoint/getProxies').catch(() => null),
                this.$store.dispatch('roomcontrol/getControls'),
                this.$store.dispatch('roomcontrol/getTemplates'),
                this.$store.dispatch('endpoint/getFirmwares')
            ])
                .catch(e => {
                    this.error = e
                    this.setLoading(false)
                })
                .then(() => {
                    this.setLoading(false)
                })
        }
    },
}
</script>

