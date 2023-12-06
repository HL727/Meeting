<template>
    <div>
        <PageSearchFilter search-width="">
            <template slot="search">
                <div class="d-flex align-center">
                    <v-datetime-picker
                        v-model="tsFilter.ts_start"
                        :input-attrs="{
                            outlined: true,
                            dense: true,
                            hideDetails: true,
                            class: 'mr-4',
                            style: 'max-width:12rem;'
                        }"
                        :label="$gettext('Fr.o.m.')"
                    />
                    <v-datetime-picker
                        v-model="tsFilter.ts_stop"
                        :input-attrs="{
                            outlined: true,
                            dense: true,
                            hideDetails: true,
                            class: 'mr-4',
                            style: 'max-width:12rem;'
                        }"
                        :label="$gettext('T.o.m.')"
                    />
                    <v-btn
                        color="primary"
                        :loading="loading"
                        @click="load"
                    >
                        <v-icon>mdi-refresh</v-icon>
                    </v-btn>
                </div>
            </template>
        </PageSearchFilter>

        <v-divider class="mb-4" />

        <v-alert
            v-if="error"
            type="error"
            class="mb-0"
        >
            {{ error }}
        </v-alert>

        <v-row>
            <v-col
                :cols="12"
                md="4"
                class="order-md-2"
            >
                <!-- eslint-disable -->
                <EPMStatsForm
                    :ts-start="tsFilter.ts_start"
                    :ts-stop="tsFilter.ts_stop"
                    :initial-data="{ endpoints: id.toString() }"
                    only-epm
                    autoload
                    ref="form"
                    @statsLoaded="statsLoaded"
                    @error="error = $event"
                    v-show="false"
                    />
                <!-- eslint-enable -->

                <HeadCountStatsForm
                    v-show="endpoint.has_head_count"
                    ref="peopleForm"
                    :ts-start="tsFilter.ts_start"
                    :ts-stop="tsFilter.ts_stop"
                    autoload
                    disable-query-change
                    hide-actions
                    :initial-data="{ endpoints: id.toString() }"
                    @statsLoaded="headCountStatsLoaded"
                    @error="error = $event"
                />

                <v-btn
                    v-show="endpoint.has_head_count"
                    color="primary"
                    :loading="loading"
                    @click="load"
                >
                    <translate>Filtrera</translate>
                </v-btn>
            </v-col>
            <v-col
                :cols="12"
                md="8"
            >
                <v-alert
                    v-if="!loading && (stats.loaded || stats.errors) && !stats.has_data"
                    type="warning"
                >
                    <translate>Kunde inte hitta någon registrerad samtalsstatistik.</translate>
                </v-alert>

                <v-card
                    v-if="stats.has_data"
                    class="mb-4"
                >
                    <v-card-text>
                        <div class="d-md-flex align-center">
                            <div>
                                <div
                                    class="d-flex"
                                    style="flex-wrap: wrap;"
                                >
                                    <div
                                        v-for="extra in extras"
                                        :key="extra.label"
                                        class="mr-10"
                                    >
                                        <v-list-item-subtitle class="mb-1">
                                            {{ extra.label }}
                                        </v-list-item-subtitle>
                                        <v-list-item-title>{{ extra.value }}</v-list-item-title>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>

                <div
                    v-if="graphs.graph || loading"
                    :loading="loading"
                    class="mb-4"
                >
                    <h3><translate>Timmar per dag</translate></h3>
                    <v-skeleton-loader
                        v-if="!graphsLoaded"
                        tile
                        type="card"
                    />
                    <Plotly
                        v-if="!loading && graphs.graph"
                        :data="graphs.graph.data"
                        :layout="graphs.graph.layout"
                        responsive
                        @afterplot="graphsLoaded = true"
                    />
                    <v-divider class="mb-4" />
                </div>

                <HeadCountGraphs
                    v-if="endpoint.has_head_count"
                    :graphs="headCountStatsData.graphs"
                    :loading="loading"
                    :graps-loading="loading"
                />
            </v-col>
        </v-row>

        <v-dialog
            v-model="filterDialog"
            eager
            scrollable
            max-width="320"
        >
            <v-card>
                <v-card-title><translate>Filtrera</translate></v-card-title>
                <v-divider />
                <v-card-text />
                <v-divider />
                <v-card-actions>
                    <v-btn
                        type="submit"
                        color="primary"
                        @click="load"
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
    </div>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'
import { globalOn, globalEmit } from '@/vue/helpers/events'

import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import EndpointsMixin from '../../mixins/EndpointsMixin'
import HeadCountStatsForm from '@/vue/components/epm/statistics/HeadCountStatsForm'
import EPMStatsForm from '@/vue/components/epm/statistics/EPMStatsForm'
import HeadCountGraphs from '@/vue/components/statistics/HeadCountGraphs'

import VDatetimePicker from '@/vue/components/datetime/DateTimePicker'

export default {
    name: 'EndpointStats',
    components: {
        PageSearchFilter,
        VDatetimePicker,
        HeadCountGraphs,
        EPMStatsForm,
        HeadCountStatsForm,
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    mixins: [SingleEndpointMixin, EndpointsMixin],
    data() {
        const defaultTimeFilter = {
            ts_start: new Date(new Date() - 30 * 24 * 60 * 60 * 1000),
            ts_stop: new Date(new Date() - 1 * 60 * 60 * 1000),
        }

        return {
            loading: true,
            loadTimeout: null,
            graphsLoaded: false,
            tsFilter: defaultTimeFilter,
            error: '',
            statsData: {},
            headCountStatsData: {},
            filterDialog: false
        }
    },
    computed: {
        summary() {
            const result = {}
            Object.entries(this.stats.summary).forEach(x => {
                result[x[0]] = x[0].match(/_total$/) ? x[1] : Object.entries(x[1]).map(y => ({ title: y[0], ...y[1] }))
            })
            return result
        },
        stats() {
            return this.statsData || {}
        },
        graphs() {
            return this.statsData.graphs || {}
        },
        filterButtonStyle() {
            return this.$vuetify.breakpoint.mdAndUp ?
                { maxWidth: '25rem' } : null
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
                },
            ]
        }
    },
    watch: {
        loading(newValue) {
            if (!newValue || this.stats.loaded) this.settingsLoaded = true
            if (newValue) this.graphsLoaded = false

            globalEmit(this, 'loading', newValue)
        },
    },
    mounted() {
        globalOn(this, 'refresh', () => { this.load() })
    },
    methods: {
        headCountStatsLoaded(statsData) {
            this.headCountStatsData = statsData || {}
        },
        statsLoaded(statsData) {
            this.statsData = statsData
            this.loading = false
        },
        load() {
            if (!this.$refs.form) return

            this.error = ''
            this.loading = true
            this.filterDialog = false

            return Promise.all([this.$refs.form.submit(), this.$refs.peopleForm.submit()]).then(f => {
                this.loading = false
                return f
            }).catch(e => {
                this.loading = false
                this.error = e
            })
        },
    },
}
</script>
