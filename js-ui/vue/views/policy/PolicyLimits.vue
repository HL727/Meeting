<template>
    <Page icon="mdi-chart-multiline">
        <template v-slot:title>
            <h1><translate>Status för kunder med policy limits</translate></h1>
        </template>
        <template v-slot:actions>
            <v-list-item-icon class="ma-0 align-self-center">
                <v-chip
                    class="ma-2 ml-4"
                    outlined
                >
                    {{ $gettextInterpolate($gettext('%{count} kunder'), { count: limits.length }) }}
                </v-chip>
            </v-list-item-icon>
        </template>
        <template v-slot:content>
            <v-card
                color="grey darken-3"
                dark
                elevation="10"
            >
                <v-card-title>
                    <translate>Kunder</translate>
                    <v-chip class="ma-2 ml-5">
                        <translate :translate-params="{inactive: limitsTotal.inactive}">
                            %{inactive} ej aktiva
                        </translate>
                    </v-chip>
                    <v-chip class="ma-2 ml-5">
                        <translate :translate-params="{inactive: limitsTotal.ok - limitsTotal.inactive}">
                            %{inactive} kunder inom gräns
                        </translate>
                    </v-chip>
                    <v-chip
                        class="ma-2"
                        :color="limitsTotal.over ? 'red' : ''"
                        @click="onlyOver = !onlyOver"
                    >
                        <v-icon v-if="onlyOver">
                            mdi-check
                        </v-icon> <translate :translate-params="{over: limitsTotal.over}">
                            %{over} kunder över gräns
                        </translate>
                    </v-chip>
                    <v-progress-circular
                        class="ml-auto"
                        sm
                        :rotate="90"
                        :size="50"
                        :width="4"
                        :value="limitsTotal.over_percentage"
                        :color="limitsTotal.median_percentage >= 100 ? 'red' : 'orange'"
                    >
                        <span class="overline">{{ (limitsTotal.over_percentage).toFixed(0) }}%</span>
                    </v-progress-circular>
                </v-card-title>

                <v-skeleton-loader
                    v-if="!graphsLoaded"
                    height="250"
                    type="image"
                />
                <Plotly
                    v-if="loaded"
                    :data="limitGraphs.total.data"
                    :layout="limitGraphs.total.layout"
                    responsive
                    @afterplot="graphsLoaded = true"
                />
                <v-card-subtitle>
                    <translate>Uppdatering 5 sekunder</translate>
                </v-card-subtitle>
            </v-card>

            <v-divider class="my-6" />

            <v-row>
                <v-col
                    v-for="limit in policyLimits"
                    :key="limit.customer"
                    cols="4"
                >
                    <v-skeleton-loader
                        v-if="!graphsLoaded"
                        tile
                        type="card"
                    />
                    <CustomerUsageCard
                        v-else
                        :limit="limit"
                    />
                </v-col>
            </v-row>

            <template v-if="otherCustomers.length">
                <v-divider class="mt-8 mb-4" />
                <v-row>
                    <v-col
                        v-for="limit in otherCustomers"
                        :key="limit.customer"
                        cols="4"
                    >
                        <v-card>
                            <v-card-title>
                                {{ limit.name }} <v-chip class="ml-auto">
                                    {{ limit.usage.participant_value }}
                                </v-chip>
                            </v-card-title>
                        </v-card>
                    </v-col>
                </v-row>
            </template>
        </template>
    </Page>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import CustomerUsageCard from '../../components/policy/CustomerUsageCard'
import Page from '@/vue/views/layout/Page'
export default {
    name: 'PolicyTenantsLimit',
    components: {
        Page,
        CustomerUsageCard,
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            limitHistory: {},
            limitLayouts: {},
            timeout: null,
            loaded: false,
            graphsLoaded: false,
            displayInactive: false,
            onlyOver: false,
            limitGraphs: {
                total: {
                    data: [
                        {
                            x: [new Date(new Date() - 2 * 60 * 1000)],
                            y: [null],
                            name: $gettext('Inom gräns'),
                            type: 'scatter',
                            line: { color: '#98ff00' }
                        },
                        {
                            x: [new Date(new Date() - 2 * 60 * 1000)],
                            y: [null],
                            name: $gettext('Över gräns'),
                            type: 'scatter',
                            line: { color: '#ff9800' }
                        }
                    ],
                    layout: {
                        showlegend: false,
                        paper_bgcolor: 'rgba(0,0,0,0.05)',
                        plot_bgcolor: 'rgba(0, 0, 0, 0)',
                        displayModeBar: true,
                        height: 250,
                        font: {
                            color: 'white'
                        },
                        margin: {
                            t: 10,
                            b: 30,
                            l: 40,
                            r: 20,
                        },
                        yaxis: {
                            rangemode: 'tozero',
                            range: [0, 5],
                            fixedrange: true,
                            gridcolor: 'rgba(0, 0, 0, 0.15)',
                            zeroline: false,
                        }
                    }
                }
            }
        }
    },
    computed: {
        usage() {
            return this.$store.getters['policy/customerUsage']
        },
        customers() {
            return this.$store.state.site.customers
        },
        limits() {
            const limits = this.$store.getters['policy/limits']
                .filter(t => !!this.usage[t.customer])

            if (this.usage[null]) {
                limits.push({
                    customer: null,
                })
            }
            return limits.map(t => {
                const usage = Object.values(this.usage[t.customer]).sort((a, b) => b.participant_value - a.participant_value)[0]

                const percentage = (usage.participant_value / t.participant_limit) * 100
                const over_percentage = percentage > 100 ? (t.participant_limit / usage.participant_value) * 100 : null
                const over_hard_limit = (t.participant_hard_limit && usage.participant_value > t.participant_hard_limit)

                let color = percentage > 80 ? 'warning' : 'success'
                if (over_hard_limit) color = 'black'
                else if (percentage > 100) color = 'error'

                return {
                    ...t,
                    usage,
                    name: t.customer ? this.customers[t.customer]?.title : $gettext('Standardtenant'),
                    percentage,
                    over_hard_limit,
                    over_percentage: over_percentage,
                    color,

                }
            }).sort((a, b) => a.name.localeCompare(b.name))
        },
        activeLimits() {
            return this.limits.filter(l => !!l.usage)
        },
        displayLimits() {
            if (this.displayInactive && !this.onlyOver) {
                return this.limits
            }
            return this.limits.filter(l => l.usage.participant_value && (!this.onlyOver || l.percentage > 100))
        },
        policyLimits() {
            return this.displayLimits.filter(l => l.id)
        },
        otherCustomers() {
            return this.displayLimits.filter(l => !l.id)
        },
        // eslint-disable-next-line max-lines-per-function
        limitsTotal() {
            const result = {
                max: 0,
                current: 0,
                percentage: 0,
                median_percentage: 0,
                over_percentage: 0,
                ok: 0,
                over: 0,
                inactive: 0,
            }
            const percentages = []

            this.limits.forEach(t => {
                result.max += t.participant_limit
                result.current += t.usage.participant_value
                if (t.usage.participant_value > t.participant_limit) {
                    result.over += 1
                } else {
                    if (t.usage.participant_value == 0) {
                        result.inactive += 1
                    }
                    result.ok += 1
                }
                if (t.usage.participant_value > 0) {
                    percentages.push((result.current / result.max) * 100)
                }
            })

            result.over_percentage = Math.floor((result.over / (this.limits.length - result.inactive)) * 100)

            if (percentages.length) {
                result.median_percentage = Math.floor(percentages[Math.floor(percentages.length / 2)])
            }

            if (result.current) {
                result.percentage = (result.current / result.max) * 100
            }
            return result
        }
    },
    watch: {
        limitsTotal(newValue) {

            const median_percentage = Math.max(Math.min(newValue.median_percentage - 50, newValue.median_percentage * 3), 150)

            if (median_percentage != this.limitGraphs.total.layout.yaxis.range.max) {

                this.limitGraphs.total.layout.yaxis.range[1] = Math.max(this.limitGraphs.total.layout.yaxis.range[1], newValue.ok - newValue.inactive + 3, newValue.over + 3)
            }
        }
    },
    mounted() {
        return this.loadLimits().then(() => {
            this.loadUsage()
        })
    },
    destroyed() {
        clearTimeout(this.timeout)
    },
    methods: {
        updateHistory() {
            this.limitGraphs.total.data = this.limitGraphs.total.data.map((line, index) => {
                const value = index == 0 ? this.limitsTotal.ok - this.limitsTotal.inactive : this.limitsTotal.over
                return {
                    y: [...line.y.slice(0, 99), value],
                    x: [...line.x.slice(0, 99), new Date()],
                }
            })
        },
        startInterval() {
            this.timeout = setTimeout(() => {
                this.loadUsage()
            }, 5000)
        },
        loadUsage() {
            return this.$store.dispatch('policy/getCustomerUsage').then(() => {
                this.updateHistory()
                this.startInterval()
                this.loaded = true
            })
        },
        loadLimits() {
            return this.$store.dispatch('policy/getCustomerLimits')
        },
    }
}
</script>
