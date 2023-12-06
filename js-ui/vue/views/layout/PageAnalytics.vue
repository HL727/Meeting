<template>
    <Page
        :title="title"
        :icon="icon"
        search-width=""
        :actions="[{ type: 'refresh', click: () => refilter(), disabled: noEndpointServer }]"
    >
        <template v-slot:search>
            <div class="d-flex align-center">
                <v-datetime-picker
                    v-model="form.ts_start"
                    :input-attrs="{
                        outlined: true,
                        dense: true,
                        hideDetails: true,
                        disabled: noEndpointServer,
                        class: 'mr-4',
                        style: 'max-width:12rem;'
                    }"
                    :label="$gettext('Fr.o.m.')"
                />
                <v-datetime-picker
                    v-model="form.ts_stop"
                    :input-attrs="{
                        outlined: true,
                        dense: true,
                        hideDetails: true,
                        disabled: noEndpointServer,
                        class: 'mr-4',
                        style: 'max-width:12rem;'
                    }"
                    :label="$gettext('T.o.m.')"
                />
                <v-btn
                    color="primary"
                    :disabled="noEndpointServer"
                    :loading="loading"
                    @click="refilter()"
                >
                    <v-icon>mdi-refresh</v-icon>
                </v-btn>
            </div>
        </template>
        <template v-slot:filter>
            <VBtnFilterServer
                v-if="showServers && choices.server && choices.server.length > 1"
                v-model="form.server"
                :disabled="noEndpointServer"
                :loading="loading"
                :servers="choices.server"
                button-class="mr-4"
                @filter="refilter"
            />

            <v-checkbox
                v-if="$refs.form && $refs.form.allowDebug"
                v-model="form.debug"
                class="mr-4"
                :label="$gettext('Debug')"
                prepend-icon="mdi-bug"
            />

            <VBtnFilter
                :disabled="loading || noEndpointServer"
                :filters="filters"
                hide-close
                :style="filterButtonStyle"
                @click="filterDialog = true"
            />
        </template>
        <template v-slot:content>
            <slot />

            <v-alert
                v-if="!loading && showServers && (!choices.server || choices.server.length === 0)"
                type="error"
            >
                <translate>Hittar ingen server för att generera statistik</translate>
            </v-alert>
            <v-alert
                v-else-if="noEndpointServer"
                type="info"
                outlined
            >
                <translate>Hittade ingen statistikdata</translate>
            </v-alert>
            <ErrorMessage
                v-else-if="error"
                :error="error"
            />
            <v-card
                v-else-if="!stats.loaded"
                class="mt-2"
                :loading="loading"
            >
                <v-card-text>
                    <translate>Gör din filtrering för att generera en rapport</translate>
                    <v-btn
                        color="primary"
                        :disabled="loading"
                        small
                        class="ml-4"
                        @click="refilter()"
                    >
                        <translate>Generera nu</translate>
                    </v-btn>
                </v-card-text>
            </v-card>
            <slot
                v-else
                name="content"
                :stats="stats"
                :graphs="graphs"
                :loading="loading"
            />

            <v-dialog
                v-model="filterDialog"
                scrollable
                eager
                max-width="320"
            >
                <v-card>
                    <v-card-title><translate>Filtrera</translate></v-card-title>
                    <v-divider />
                    <v-card-text>
                        <HeadCountStatsForm
                            v-if="rooms && displayHeadCount"
                            ref="form"
                            v-model="form"
                            :ts-start="form.ts_start"
                            :ts-stop="form.ts_stop"
                            hide-actions
                            :enable-tenants="enableTenants"
                            @loading="loading = $event"
                            @choices="choices = $event"
                            @error="error = $event"
                            @statsLoaded="statsData = $event"
                        />
                        <EPMStatsForm
                            v-else-if="rooms"
                            ref="form"
                            v-model="form"
                            :ts-start="form.ts_start"
                            :ts-stop="form.ts_stop"
                            :display-head-count="displayHeadCount"
                            :enable-tenants="enableTenants"
                            :initial-data="{server: 'person'}"
                            hide-actions
                            :force-debug="form.debug"
                            @loading="loading = $event"
                            @choices="setChoices($event)"
                            @error="error = $event"
                            @statsLoaded="setStats($event)"
                        />
                        <StatsForm
                            v-else
                            ref="form"
                            v-model="form"
                            :ts-start="form.ts_start"
                            :ts-stop="form.ts_stop"
                            :enable-tenants="enableTenants"
                            :force-debug="form.debug"
                            hide-actions
                            @loading="loading = $event"
                            @choices="choices = $event"
                            @error="error = $event"
                            @statsLoaded="setStats($event)"
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-actions>
                        <v-btn
                            type="submit"
                            color="primary"
                            @click="applyFilters"
                        >
                            <translate>Tillämpa</translate>
                        </v-btn>
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
    </Page>
</template>

<script>
import { $gettext, $ngettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

import VDatetimePicker from '@/vue/components/datetime/DateTimePicker'
import EPMStatsForm from '@/vue/components/epm/statistics/EPMStatsForm'
import HeadCountStatsForm from '@/vue/components/epm/statistics/HeadCountStatsForm'
import StatsForm from '@/vue/components/statistics/StatsForm'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'
import VBtnFilterServer from '@/vue/components/filtering/VBtnFilterServer'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

export default {
    name: 'PageAnalytics',
    components: {
        ErrorMessage,
        Page,
        StatsForm,
        EPMStatsForm,
        HeadCountStatsForm,
        VDatetimePicker,
        VBtnFilter,
        VBtnFilterServer,
    },
    mixins: [PageSearchMixin],
    props: {
        icon: { type: String, default: '' },
        title: { type: String, default: '' },
        rooms: { type: Boolean, default: false },
        showServers: { type: Boolean, default: false },
        displayHeadCount: { type: Boolean, default: false },

        requireEndpointServer: { type: Boolean, default: false },
        enableTenants: { type: Boolean, default: false },
    },
    // eslint-disable-next-line max-lines-per-function
    data() {
        const filterLabels = {
            cospace: $ngettext('Mötesrum', 'Mötesrum', 1),
            member: $gettext('Deltagare'),
            organization: $gettext('OU'),
            debug: $gettext('Debug'),
            endpoints: $ngettext('System', 'System', 2),
            protocol: $gettext('Protokoll'),
            only_gateway: $gettext('Bara gateway'),

            only_hours: $gettext('Timmar'),
            only_days: $gettext('Dagar'),
            as_percent: $gettext('Visa som procent'),
            ignore_empty: $gettext('Hoppa över tomma rum'),
            fill_gaps: $gettext('Fyll i saknad data')
        }

        return {
            times: {},
            dataTab: 0,
            debugTab: 0,
            choices: {},
            data: {},
            form: {
                ts_start: null,
                ts_stop: null,
                server: 'person',
                debug: false,
            },
            loading: true,
            settingsLoaded: false,
            search: { debug: '', stats: '' },
            graphsLoaded: false,
            statsData: {},
            filterValues: {},
            filterDialog: false,
            error: null,
            noEndpointServer: false,
            filterLabels
        }
    },
    computed: {
        filters() {
            const labels = { ...this.filterLabels }

            if (this.enableTenants) {
                labels.tenant = $gettext('Tenant')
            }

            const activeFilters = []

            Object.entries(labels).forEach(f => {
                const filterValue = this.getFilterValue(f[0])

                if (filterValue) {
                    activeFilters.push({
                        title: f[1],
                        value: filterValue
                    })
                }
            })

            return activeFilters
        },
        organizations() {
            return this.$store.getters['organization/units']
        },
        filterButtonStyle() {
            return this.$vuetify.breakpoint.mdAndUp ?
                { maxWidth: '25rem' } : null
        },
        summary() {
            const result = {}
            Object.entries(this.stats.summary).forEach(x => {
                result[x[0]] = x[1].pop ? x[1] : Object.entries(x[1]).map(y => ({ title: y[0], ...y[1] }))
            })
            return result
        },
        stats() {
            return this.statsData || {}
        },
        graphs() {
            return this.statsData.graphs || {}
        },
        extras() {
            if (!this.stats.has_data) return []

            return [
                {
                    label: $gettext('Timmar'),
                    value: parseInt(this.summary.cospace_total[0], 10)
                },
                {
                    label: $gettext('Unika samtal'),
                    value: parseInt(this.summary.cospace_total[3], 10)
                }
            ]
        }
    },
    watch: {
        loading(newValue) {
            if (!newValue || this.stats.loaded) this.settingsLoaded = true
            if (newValue) this.graphsLoaded = false
            this.setLoading(newValue)
        },
    },
    mounted() {
        this.$store.dispatch('organization/refreshUnits')
        this.filterValues = { ...this.form }
    },
    methods: {
        getFilterValue(filterKey) {
            if (!this.filterValues[filterKey]) {
                return null
            }

            let filterValue = this.filterValues[filterKey]

            if (filterKey === 'organization' && filterValue in this.organizations) {
                filterValue = this.organizations[filterValue].name
            }

            if (filterKey === 'fill_gaps' && this.filterValues.ignore_empty && filterValue) {
                return
            }
            if (filterKey === 'ignore_empty' && !filterValue) {
                return
            }
            if (filterKey === 'endpoints') {
                if (filterValue.length === 0) {
                    return
                }
                filterValue = filterValue.length + ' ' + this.$ngettext('vald', 'valda', filterValue.length)
            }

            return filterValue
        },
        setStats(data) {
            this.statsData = data
            this.$emit('statsData', data)
        },
        setChoices(data) {
            this.choices = data

            if (this.displayHeadCount) {
                this.form.server = 'person'
            }

            if (this.requireEndpointServer) {
                const endpointServer = this.choices.server.find(s => s.type === 2)

                if (!endpointServer) {
                    this.noEndpointServer = true
                    return
                }

                this.form.server = endpointServer.id
            }
        },
        refilter(newValues) {
            if (newValues) Object.assign(this.form, newValues)
            this.dataTab = 0
            this.search = {}
            this.filterValues = { ...this.form }
            this.$refs.form.submit()
        },
        applyFilters() {
            this.filterDialog = false
            this.refilter()
        },
        applyServer() {
            this.serverDialog = false
            this.refilter({
                server: this.filterServer,
                head_count: false
            })
        }
    },
}
</script>
