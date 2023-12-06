<template>
    <Page
        icon="mdi-account-group"
        :title="$gettext('Personräknare')"
        :actions="[{ type: 'refresh', click: () => loadData() }]"
        :loading="loading.endpoints"
    >
        <template v-slot:content>
            <v-card
                v-if="!hadEndpoints && !loading.endpoints && !endpoints.length && !filters.length"
                class="mt-2"
            >
                <v-card-text>
                    <translate>Hittade inga registrerade system med personräknare.</translate>
                    <v-btn
                        color="primary"
                        :to="{name:'epm_list'}"
                        small
                        class="ml-4"
                    >
                        <translate>Gå till system</translate>
                    </v-btn>
                </v-card-text>
            </v-card>
            <template v-else>
                <v-card class="mt-4 mb-4">
                    <v-progress-linear
                        :active="loading.endpoints || loading.graphs"
                        indeterminate
                        absolute
                        top
                    />
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
                                        class="extra-circle mr-5 my-2"
                                    >
                                        <v-icon
                                            class="extra-circle__icon"
                                            small
                                        >
                                            {{ extra.icon }}
                                        </v-icon>
                                        <div class="text-h6 extra-circle__title">
                                            {{ extra.value }}
                                        </div>
                                        <small>{{ extra.label }}</small>
                                    </div>
                                </div>
                            </div>
                            <v-divider class="my-4 d-md-none" />
                            <div
                                class="d-flex ml-auto align-center"
                                :class="{'flex-wrap': $vuetify.breakpoint.xsOnly}"
                            >
                                <Plotly
                                    v-if="!loading.endpoints"
                                    :data="graphData.data"
                                    :layout="graphData.layout"
                                    :display-mode-bar="false"
                                    @afterplot="loading.graphs = false"
                                />
                                <div
                                    v-if="loading.endpoints || loading.graphs"
                                    class="d-flex align-center"
                                >
                                    <v-avatar
                                        size="96"
                                        class="mr-4"
                                        color="grey lighten-3"
                                    />
                                    <v-skeleton-loader
                                        tile
                                        width="450"
                                        height="90"
                                        type="image"
                                    />
                                </div>
                                <template v-else>
                                    <v-simple-table
                                        dense
                                        class="ml-8"
                                        style="min-width:15rem;"
                                    >
                                        <template v-slot:default>
                                            <tbody>
                                                <tr
                                                    v-for="legend in legends.slice(0, 3)"
                                                    :key="legend.label"
                                                >
                                                    <td class="px-0">
                                                        <v-avatar
                                                            v-if="legend.percentage"
                                                            size="10"
                                                            :color="legend.color"
                                                        />
                                                    </td>
                                                    <td class="pr-0">
                                                        <strong>{{ legend.value }}</strong>
                                                        <span
                                                            v-if="legend.percentage"
                                                            class="d-inline-block ml-1"
                                                        >({{ legend.percentage }})</span>
                                                    </td>
                                                    <td class="pr-0">
                                                        {{ legend.label }}
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </template>
                                    </v-simple-table>
                                    <v-simple-table
                                        dense
                                        class="ml-8"
                                        style="min-width:15rem;"
                                    >
                                        <template v-slot:default>
                                            <tbody>
                                                <tr
                                                    v-for="legend in legends.slice(-3)"
                                                    :key="legend.label"
                                                >
                                                    <td class="px-0">
                                                        <v-avatar
                                                            v-if="legend.percentage"
                                                            size="10"
                                                            :color="legend.color"
                                                        />
                                                    </td>
                                                    <td class="pr-0">
                                                        <strong>{{ legend.value }}</strong>
                                                        <span
                                                            v-if="legend.percentage"
                                                            class="d-inline-block ml-1"
                                                        >({{ legend.percentage }})</span>
                                                    </td>
                                                    <td class="pr-0">
                                                        {{ legend.label }}
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </template>
                                    </v-simple-table>
                                </template>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>
                <EndpointPeopleCountGrid
                    ref="grid"
                    :show-empty="false"
                    @endpoints="endpoints = $event"
                    @filters="filters = $event"
                    @refreshed="loading.endpoints = false"
                />
            </template>
        </template>
    </Page>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

import EndpointPeopleCountGrid from '@/vue/components/epm/endpoint/EndpointPeopleCountGrid'
import GraphsLayout from '@/vue/views/epm/mixins/GraphsLayout'

export default {
    components: {
        Page,
        EndpointPeopleCountGrid,
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    mixins: [GraphsLayout],
    data() {
        return {
            loading: {
                endpoints: true,
                graphs: true
            },
            filters: [],
            endpoints: [],
            hadEndpoints: false
        }
    },
    computed: {
        endpointStatus() {
            return this.$store.state.stats.endpointStatus
        },
        legendsEndpointStats() {
            const stats = {
                free: 0,
                occupied: 0,
                meeting: 0,
                meeting_participants: 0,
                ghost: 0,
                offline: 0,
                err: 0,
            }
            this.endpoints.forEach(e => {
                stats[e.status.type.key] += 1
            })

            return stats
        },
        legends() {
            const stats = this.legendsEndpointStats
            const getLegend = (value, color) => ({
                value, color,
                percentage: (((value / this.endpoints.length) * 100 || 0)).toFixed(1) + '%',
            })

            stats.offline_err = stats.offline + stats.err
            stats.all_meeting = stats.meeting_participants + stats.meeting

            return [
                {
                    label: $gettext('Lediga'),
                    ...getLegend(stats.free, 'green'),
                },
                {
                    label: $gettext('Bokat möte'),
                    ...getLegend(stats.all_meeting, 'red'),
                },
                {
                    label: $gettext('Möte'),
                    ...getLegend(stats.occupied, 'blue'),
                },
                {
                    label: $gettext('Spökmöte'),
                    ...getLegend(stats.ghost, '#d4d4d4'),
                },
                {
                    label: $gettext('Offline'),
                    ...getLegend(stats.offline, '#aaa'),
                },
                {
                    label: $gettext('Varning'),
                    ...getLegend(stats.err, '#888'),
                },
            ]
        },
        extras() {
            const stats = {
                totalRooms: this.endpoints.length,
                totalSeats: 0,
                usedSeats: 0,
            }
            this.endpoints.forEach(e => {
                stats.totalSeats += e.room_capacity

                if (e.id in this.endpointStatus) {
                    const status = this.endpointStatus[e.id]
                    stats.usedSeats += Math.max(0, status.head_count || 0)
                }
            })

            return [
                {
                    icon: 'mdi-door',
                    label: this.$ngettext('Rum', 'Rum', 2),
                    value: stats.totalRooms
                },
                {
                    icon: 'mdi-seat',
                    label: $gettext('Stolar'),
                    value: stats.totalSeats
                },
                {
                    icon: 'mdi-account',
                    label: $gettext('Personer'),
                    value: stats.usedSeats
                },
            ]
        },
        graphData() {
            const graph = this.simplePieChartDefaults()
            graph.data[0].values = this.legends.map(l => l.value)
            graph.data[0].marker.colors = this.legends.map(l => l.color)
            graph.data[0].hole = 0.01
            graph.layout.width = 80
            graph.layout.height = 80

            return graph
        }
    },
    watch: {
        endpoints(newValue) {
            if (newValue && !this.hadEndpoints) {
                this.hadEndpoints = true
            }
        }
    },
    methods: {
        loadData() {
            this.loading.endpoints = true
            if (this.$refs.grid) this.$refs.grid.reloadEndpoints()
        }
    },
}
</script>

<style lang="scss">
.extra-circle {
    border: 2px solid #eee;
    width: 80px;
    height: 80px;
    border-radius: 160px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    position: relative;
}
.extra-circle__icon {
    position: absolute!important;
    top: -3px;
    right: -3px;
    background: #aaa;
    color: #fff!important;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 2rem;
}
.extra-circle__title {
    display: flex;
    align-items: center;
    line-height: 1!important;
}
</style>
