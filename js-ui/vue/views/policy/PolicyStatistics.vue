<template>
    <Page
        :title="$gettext('Överförbrukning')"
        icon="mdi-chart-line-stacked"
        search-width=""
        :actions="[{ type: 'refresh', click: () => refilter() }]"
    >
        <template v-slot:search>
            <div class="d-flex align-center">
                <v-datetime-picker
                    v-model="form.ts_start"
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
                    v-model="form.ts_stop"
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
                    @click="refilter"
                >
                    <v-icon>mdi-refresh</v-icon>
                </v-btn>
            </div>
        </template>
        <template
            v-if="choices.server && choices.server.length > 1"
            v-slot:filter
        >
            <VBtnFilterServer
                v-model="form.server"
                :loading="loading"
                :servers="choices.server"
                @filter="refilter"
            />
        </template>
        <template v-slot:content>
            <ErrorMessage :error="error" />

            <v-alert
                v-if="settingsLoaded && !loading && !hasData"
                type="info"
                class="mt-2"
            >
                <translate>Kunde inte hitta någon överförbrukning för perioden</translate>
            </v-alert>

            <template v-if="settingsLoaded && policyGraphs">
                <template v-if="policyGraphs.soft_limit">
                    <v-divider class="mb-4" />
                    <h3><translate>Överanvändning, varaktighet h/dag, soft limit</translate></h3>
                    <v-skeleton-loader
                        v-if="loading || !graphsLoaded"
                        tile
                        type="image"
                        class="mt-4"
                    />
                    <Plotly
                        v-if="!loading && policyGraphs.soft_limit"
                        :data="policyGraphs.soft_limit.data"
                        :layout="policyGraphs.soft_limit.layout"
                        responsive
                        @afterplot="graphsLoaded = true"
                    />
                </template>
                <template v-if="policyGraphs.soft_limit_30">
                    <v-divider class="mb-4" />
                    <h3><translate>Överanvändning, varaktighet h/dag, soft limit</translate> + 30%</h3>
                    <v-skeleton-loader
                        v-if="loading || !graphsLoaded"
                        tile
                        type="image"
                        class="mt-4"
                    />
                    <Plotly
                        v-if="!loading && policyGraphs.soft_limit_30"
                        :data="policyGraphs.soft_limit_30.data"
                        :layout="policyGraphs.soft_limit_30.layout"
                        responsive
                        @afterplot="graphsLoaded = true"
                    />
                </template>
                <template v-if="policyGraphs.hard_limit">
                    <v-divider class="mb-4" />
                    <h3><translate>Överanvändning, varaktighet h/dag, hard limit</translate></h3>
                    <v-skeleton-loader
                        v-if="loading || !graphsLoaded"
                        tile
                        type="image"
                        class="mt-4"
                    />
                    <Plotly
                        v-if="!loading && policyGraphs.hard_limit"
                        :data="policyGraphs.hard_limit.data"
                        :layout="policyGraphs.hard_limit.layout"
                        responsive
                        @afterplot="graphsLoaded = true"
                    />
                </template>


                <template v-if="policyGraphs.count">
                    <v-divider class="mb-4" />
                    <h3><translate>Överanvändning, antal deltagare</translate></h3>
                    <v-card
                        v-for="(graph, customerId) in policyGraphs.count.graphs"
                        :key="'count' + customerId.toString()"
                        :loading="loading"
                        class="my-4"
                    >
                        <v-card-text>
                            <p class="overline mb-0">
                                {{ customers[customerId] && customers[customerId].title }}
                            </p>
                            <v-skeleton-loader
                                v-if="loading || !graphsLoaded"
                                tile
                                type="image"
                                class="mt-4"
                            />
                            <Plotly
                                v-if="!loading && policyGraphs.count"
                                :data="graph.data"
                                :layout="policyGraphs.count.layout"
                                responsive
                                @afterplot="graphsLoaded = true"
                            />
                        </v-card-text>
                    </v-card>
                </template>
            </template>
        </template>
    </Page>
</template>

<script>
import { format } from 'date-fns'
import Page from '@/vue/views/layout/Page'
import VDatetimePicker from '@/vue/components/datetime/DateTimePicker'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import VBtnFilterServer from '@/vue/components/filtering/VBtnFilterServer'
import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'

export default {
    name: 'PolicyServer',
    components: {
        Page,
        ErrorMessage,
        VBtnFilterServer,
        VDatetimePicker,
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    mixins: [PageSearchMixin],
    data() {
        return {
            times: {},
            choices: {
                server: null,
                tenant: null,
            },
            form: {
                ts_start: new Date(new Date() - 7 * 60 * 60 * 24 * 1000),
                ts_stop: new Date(),
                server: null,
            },
            loading: false,
            settingsLoaded: false,
            search: { debug: '', stats: '' },
            graphsLoaded: false,
            policyGraphs: null,
            error: null,
        }
    },
    computed: {
        customers() {
            return this.$store.state.site.customers || {}
        },
        hasData() {
            return this.policyGraphs && Object.values(this.policyGraphs).some(x => !!x)
        }
    },
    watch: {
        loading(newValue) {
            if (newValue) this.graphsLoaded = false
            this.setLoading(newValue)
        },
    },
    mounted() {
        this.$store.dispatch('stats/getStatsSettings', { multitenant: 1 }).then(d => {
            this.error = null

            this.choices = { ...this.choices, ...d.choices }
            this.settingsLoaded = true
            if (this.choices.server && this.choices.server.length) {
                if (!this.form.server || this.choices.server.length === 1) {
                    this.form.server = this.choices.server[0].id
                }
            }
            this.load()
        }).catch(e => this.error = e)
    },
    methods: {
        applyServer() {
            this.serverDialog = false
            this.refilter({
                server: this.filterServer,
                head_count: false
            })
        },
        refilter(newValues) {
            if (newValues) Object.assign(this.form, newValues)
            this.load()
        },
        load() {
            const dateString = d => (d && d.getYear ? format(d, 'yyyy-MM-dd HH:mm') : d || '')

            this.loading = true
            return this.$store
                .api()
                .get('policy/report/', {
                    params: {
                        as_graph: true,
                        ts_start: dateString(this.form.ts_start),
                        ts_stop: dateString(this.form.ts_stop),
                        server: this.form.server || undefined,
                    },
                })
                .then(values => {
                    this.policyGraphs = values
                    this.loading = false
                })
        },
    },
}
</script>

<style scoped></style>
