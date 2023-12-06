<template>
    <Page
        icon="mdi-view-dashboard-outline"
        :title="$gettext('Dashboard')"
        :actions="[{ type: 'refresh', click: () => loadData() }]"
        doc-url="core_dashboard"
    >
        <template v-slot:content>
            <div
                class="mb-6"
                style="position: relative;"
            >
                <v-progress-linear
                    :active="loading"
                    indeterminate
                    absolute
                    top
                />
            </div>

            <v-alert
                v-if="!loading && !settings.hasCoreProvider"
                class="mb-4"
                style="z-index: 5;"
                prominent
                text
                type="info"
            >
                <v-row align="center">
                    <v-col class="grow">
                        <translate>Det finns för närvarande ingen kopplad videobrygga.</translate>
                    </v-col>
                    <v-col class="shrink">
                        <v-btn
                            v-if="settings.perms.staff"
                            class="ml-2"
                            to="/setup/cluster/"
                        >
                            <translate>Lägg till videokluster</translate>
                        </v-btn>
                    </v-col>
                </v-row>
                <!-- TODO: option for pexip? -->
            </v-alert>

            <v-row v-if="settings.hasCoreProvider || settings.perms.staff">
                <v-col
                    cols="12"
                    md="8"
                    style="position:relative"
                >
                    <img
                        :src="illustration"
                        class="stats-illustration d-none d-sm-block ml-auto"
                        style="max-width:65%;position:absolute;top:-5.5rem;right:1rem;z-index:4;"
                    >

                    <p class="overline">
                        <translate>Pågående</translate>
                    </p>

                    <v-list
                        dense
                        :style="{ maxWidth: $vuetify.breakpoint.smAndUp ? '30%' : '' }"
                        class="mb-8"
                    >
                        <v-list-item to="/calls/">
                            <v-list-item-content>
                                <v-list-item-title><translate>Möten</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ stats.active_meetings_calls }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item to="/calls/">
                            <v-list-item-content>
                                <v-list-item-title><translate>Deltagare</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ stats.active_meetings_legs }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item to="/meeting/">
                            <v-list-item-content>
                                <v-list-item-title><translate>Kommande möten</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ stats.upcoming_meetings_count }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item :to="stats.stats_link || '/stats/'">
                            <v-list-item-content>
                                <v-list-item-title><translate>Samtal idag</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ stats.today_calls }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                        <v-divider />
                        <v-list-item :to="stats.stats_link || '/stats/'">
                            <v-list-item-content>
                                <v-list-item-title><translate>Timmar idag</translate></v-list-item-title>
                            </v-list-item-content>
                            <v-list-item-icon>
                                <v-chip small>
                                    {{ stats.today_hours }}
                                </v-chip>
                            </v-list-item-icon>
                        </v-list-item>
                    </v-list>

                    <p class="overline">
                        <translate>Översikt</translate>
                    </p>

                    <DashboardOverview :items="overview">
                        <template v-slot:item="{item}">
                            <div class="ml-auto">
                                <UserPicker
                                    v-if="item.key === 'users'"
                                    :input-attrs="{
                                        'prepend-inner-icon': 'mdi-magnify',
                                        placeholder: $gettext('Sök användare') + '...',
                                        solo: true,
                                        dense: true,
                                        style: 'width: 12rem'
                                    }"
                                    :hide-details="true"
                                    all
                                    navigate
                                    enable-search-all
                                    clearable
                                />
                                <CoSpacePicker
                                    v-if="item.key === 'cospaces'"
                                    :input-attrs="{
                                        'prepend-inner-icon': 'mdi-magnify',
                                        placeholder: $gettext('Sök mötesrum') + '...',
                                        solo: true,
                                        dense: true,
                                        style: 'width: 12rem'
                                    }"
                                    :hide-details="true"
                                    all
                                    navigate
                                    enable-search-all
                                    clearable
                                />
                                <CallPicker
                                    v-if="item.key === 'calls'"
                                    :input-attrs="{
                                        'prepend-inner-icon': 'mdi-magnify',
                                        placeholder: $gettext('Sök möten') + '...',
                                        solo: true,
                                        dense: true,
                                        style: 'width: 12rem'
                                    }"
                                    :hide-details="true"
                                    all
                                    navigate
                                    enable-search-all
                                    clearable
                                />
                                <MeetingPicker
                                    v-if="item.key === 'meetings'"
                                    :input-attrs="{
                                        'prepend-inner-icon': 'mdi-magnify',
                                        placeholder: $gettext('Sök bokningar') + '...',
                                        solo: true,
                                        dense: true,
                                        style: 'width: 12rem'
                                    }"
                                    :hide-details="true"
                                    all
                                    navigate
                                    enable-search-all
                                    clearable
                                />
                            </div>
                            <v-divider
                                vertical
                                class="mx-4"
                            />
                        </template>
                    </DashboardOverview>
                </v-col>
                <v-col
                    cols="12"
                    md="4"
                >
                    <v-expansion-panels
                        v-if="providerStatus.server && providerStatus.server.version"
                        v-model="productVersionPanel"
                        :flat="productVersionPanel !== 0"
                        class="mb-6"
                    >
                        <ServerStatus
                            :loading="loading"
                            :server="providerStatus.server"
                            title="Mividas Core"
                        />
                    </v-expansion-panels>

                    <p class="overline">
                        <translate>Kluster och bryggor</translate>
                    </p>

                    <v-skeleton-loader
                        v-if="providerStatus.acano === null"
                        type="list-item-avatar-two-line@1"
                        tile
                        loading
                    />

                    <v-expansion-panels
                        v-for="(cluster, i) in providerStatus.acanoClusters"
                        :key="'cluster' + i"
                        class="mb-6"
                    >
                        <AcanoStatus
                            v-for="(provider, index) in cluster"
                            :key="provider.id"
                            :provider="provider"
                            :counter="index + 1"
                            call_url="/calls/"
                        />
                    </v-expansion-panels>

                    <v-skeleton-loader
                        v-if="providerStatus.pexip === null"
                        type="list-item-avatar-two-line@1"
                        tile
                        loading
                    />

                    <v-expansion-panels class="mb-6">
                        <PexipStatusPanel
                            v-for="(provider, id, index) in providerStatus.pexip"
                            :key="provider.id"
                            :provider="provider"
                            :counter="index + 1"
                            call_url="/calls/"
                        />
                    </v-expansion-panels>

                    <v-skeleton-loader
                        v-if="providerStatus.vcs === null"
                        type="list-item-avatar-two-line@2"
                        tile
                        loading
                    />
                    <v-expansion-panels>
                        <VCSEStatus
                            v-for="(server, id, index) in providerStatus.vcs"
                            :key="server.id"
                            :provider="server"
                            :counter="index + 1"
                        />
                    </v-expansion-panels>
                </v-col>
            </v-row>
            <ErrorMessage :error="error" />
        </template>
    </Page>
</template>

<script>
import axios from 'axios'
import { $gettext, $ngettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

import CoSpacePicker from '@/vue/components/cospace/CoSpacePicker'
import UserPicker from '@/vue/components/user/UserPicker'
import CallPicker from '@/vue/components/call/CallPicker'
import MeetingPicker from '@/vue/components/meeting/MeetingPicker'
import AcanoStatus from '@/vue/components/AcanoStatus'
import VCSEStatus from '@/vue/components/VCSEStatus'
import PexipStatusPanel from '@/vue/components/provider/PexipStatusPanel'
import DashboardOverview from '@/vue/components/dashboard/DashboardOverview'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'
import ServerStatus from '@/vue/components/ServerStatus'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

const statsOverviewTypes = {
    users: {
        title: $gettext('Användare'),
        icon: 'mdi-account-multiple',
        key: 'users',
        to: { name: 'user_list' }
    },
    cospaces: {
        title: $ngettext('Mötesrum', 'Mötesrum', 2),
        icon: 'mdi-door-closed',
        key: 'cospaces',
        to: { name: 'cospaces_list' }
    },
    calls: {
        title: $gettext('Pågående möten'),
        icon: 'mdi-google-classroom',
        key: 'calls',
        to: { name: 'calls_list' }
    },
    meetings: {
        title: $gettext('Bokade möten'),
        icon: 'mdi-calendar',
        key: 'meetings',
        to: { name: 'meetings_list' }
    },
}

export default {
    name: 'CoreDashboard',
    components: { ErrorMessage, ServerStatus, Page, PexipStatusPanel, DashboardOverview, VCSEStatus, AcanoStatus, UserPicker, CoSpacePicker, CallPicker, MeetingPicker },
    mixins: [PageSearchMixin],
    data() {
        return {
            stats: {},
            providerStatus: {
                acano: null,
                acanoClusters: null,
                pexip: null,
                vcs: null,
                server: null,
            },
            productVersionPanel: null,
            illustration: require('@/assets/images/illustrations/core.svg'),
            statsOverviewTypes,
            error: null,
        }
    },
    computed: {
        overview() {
            const totals = {
                users: this.loading ? '-' : this.stats.user_count,
                cospaces:  this.loading ? '-' : this.stats.cospace_count,
                calls: this.loading ? '-' : this.stats.active_meetings_calls,
                meetings: this.loading ? '-' : this.stats.upcoming_meetings_count
            }

            return Object.entries(this.statsOverviewTypes).map(s => {
                return {
                    ...s[1],
                    totals: [{
                        label: $gettext('Totalt'),
                        value: totals[s[0]]
                    }]
                }
            })
        },
        customerId() {
            return this.$store.state.site.customerId
        },
        settings() {
            return this.$store.getters['settings']
        },
    },
    mounted() {
        return this.loadData()
    },
    methods: {
        loadData() {
            this.setLoading(true)

            return Promise.all([
                this.$store.api().get('provider/status/?type=acano')
                    .then(r => {
                        this.providerStatus.acano = Object.values(r)
                        const clusters = {}
                        this.providerStatus.acano.forEach(a => {
                            if (!clusters[a.cluster_id]) clusters[a.cluster_id] = []
                            clusters[a.cluster_id].push(a)
                        })
                        Object.keys(clusters).forEach(clusterId => {
                            clusters[clusterId].sort((a, b) => {
                                if (a.is_service_node == b.is_service_node) {
                                    return a.title.localeCompare(b.title)
                                }
                                return a.is_service_node - b.is_service_node
                            })
                        })
                        this.providerStatus.acanoClusters = clusters
                    }),
                this.$store.api().get('provider/status/?type=pexip')
                    .then(r => this.providerStatus.pexip = r),
                this.$store.api().get('provider/status/?type=vcs')
                    .then(r => this.providerStatus.vcs = r),
                this.$store.api().get('provider/status/?type=server')
                    .then(r => this.providerStatus.server = r),
                axios.get('/?get_counters=1').then(r => (this.stats = typeof r.data === 'object' ? r.data : {})),
            ]).then(() => {
                this.setLoading(false)
            }).catch(e => {
                this.error = e
                this.setLoading(false)
            })
        }
    },
}
</script>

<style scoped></style>
