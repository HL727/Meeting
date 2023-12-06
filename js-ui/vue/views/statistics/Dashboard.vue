<template>
    <Page icon="mdi-view-dashboard-outline">
        <template v-slot:title>
            <h1><translate>Dashboard</translate></h1>
        </template>
        <template v-slot:actions>
            <v-list-item-icon class="ma-0 align-self-center">
                <v-btn
                    color="primary"
                    fab
                    small
                    outlined
                    :title="$gettext('Ladda om')"
                    :loading="loading.calls || loading.rooms"
                    @click="getStats"
                >
                    <v-icon>mdi-reload</v-icon>
                </v-btn>
            </v-list-item-icon>
        </template>
        <template v-slot:content>
            <div
                class="mb-6"
                style="position: relative;"
            >
                <v-progress-linear
                    :active="loading.calls || loading.rooms"
                    indeterminate
                    absolute
                    top
                />
            </div>
            <v-row>
                <v-col
                    cols="12"
                    md="6"
                >
                    <div class="mb-6">
                        <h2
                            v-translate
                            class="font-weight-regular mr-6"
                        >
                            Videosamtal senaste 24h
                        </h2>
                        <router-link :to="{name:'analytics_calls'}">
                            <translate>Visa avancerat</translate>
                        </router-link>
                    </div>
                    <v-card style="margin-bottom:2rem;">
                        <v-card-text>
                            <DashboardStatsHeader
                                :loading="loading.calls"
                                :legends="callsSummary.legends"
                                :extras="callsSummary.extras"
                                :pie-chart="callsPieChartTotal"
                                :image="images.illustrationCalls"
                                :error="errors.calls"
                                :no-data="!callsStatsData.graphs.seconds_per_hour && !loading.calls"
                            />
                        </v-card-text>
                        <v-divider />
                        <v-card
                            v-if="!errors.calls && (callsStatsData.graphs.seconds_per_hour || loading.calls)"
                            flat
                            :loading="loading.calls || loading.graphs"
                        >
                            <div class="d-flex align-center">
                                <v-card-title class="py-5">
                                    <translate>Minuter per klockslag</translate>
                                </v-card-title>
                                <v-progress-circular
                                    v-if="loading.calls || loading.graphs"
                                    indeterminate
                                    color="grey lighten-2"
                                    class="ml-auto mr-10"
                                />
                                <v-list
                                    v-else
                                    class="d-flex ml-auto pa-0"
                                >
                                    <v-list-item
                                        v-for="peak in callsSummary.peaks"
                                        :key="peak.label"
                                        two-line
                                    >
                                        <div>
                                            <v-list-item-subtitle class="mb-1">
                                                {{ peak.label }}
                                            </v-list-item-subtitle>
                                            <v-list-item-title>{{ peak.value }}</v-list-item-title>
                                        </div>
                                    </v-list-item>
                                </v-list>
                            </div>
                            <v-divider />
                            <v-card-text class="pa-0">
                                <Plotly
                                    v-if="!loading.calls"
                                    :data="callsGraphPerHour.data"
                                    :layout="callsGraphPerHour.layout"
                                    :display-mode-bar="false"
                                    @afterplot="loading.graphs = false"
                                />
                                <v-skeleton-loader
                                    v-if="loading.calls || loading.graphs"
                                    tile
                                    height="217"
                                    type="image"
                                />
                            </v-card-text>
                            <v-divider />
                        </v-card>
                    </v-card>
                </v-col>
                <v-col
                    cols="12"
                    md="6"
                >
                    <div class="mb-6">
                        <h2
                            v-translate
                            class="font-weight-regular mr-6"
                        >
                            Rumsanvändning
                        </h2>
                        <router-link :to="{name:'analytics_rooms'}">
                            <translate>Visa avancerat</translate>
                        </router-link>
                    </div>
                    <v-card>
                        <v-card-text>
                            <DashboardStatsHeader
                                :loading="loading.rooms"
                                :legends="roomsSummary.legends"
                                :extras="roomsSummary.extras"
                                :image="images.illustrationRooms"
                                :error="errors.rooms"
                                :hide-pie-chart="true"
                                :no-data="!roomsSummary.peaks.perHour.value"
                            />
                        </v-card-text>
                        <v-divider />

                        <v-card
                            v-if="!errors.rooms && (loading.rooms || roomsSummary.peaks.perHour.value)"
                            flat
                            :loading="loading.rooms || loading.graphs"
                        >
                            <div class="d-flex align-center py-3">
                                <v-card-title class="py-2">
                                    <translate>Personer per klockslag</translate>
                                </v-card-title>
                                <div>
                                    <v-list-item class="pl-0">
                                        <v-list-item-subtitle><translate>(senaste 7 dagarna)</translate></v-list-item-subtitle>
                                    </v-list-item>
                                </div>

                                <v-progress-circular
                                    v-if="loading.rooms || loading.graphs"
                                    indeterminate
                                    color="grey lighten-2"
                                    class="ml-auto mr-10"
                                />
                            </div>
                            <v-divider />
                            <v-card-text class="pa-0">
                                <Plotly
                                    v-if="!loading.rooms"
                                    :data="roomsPersonPerHourChart.data"
                                    :layout="roomsPersonPerHourChart.layout"
                                    :display-mode-bar="false"
                                    @afterplot="loading.graphs = false"
                                />
                                <v-skeleton-loader
                                    v-if="loading.rooms || loading.graphs"
                                    height="140"
                                    tile
                                    type="image"
                                />
                            </v-card-text>
                        </v-card>
                        <v-divider />
                        <v-card
                            v-if="!errors.rooms && (loading.rooms || roomsSummary.peaks.perHour.value)"
                            flat
                            :loading="loading.rooms || loading.graphs"
                        >
                            <div class="d-flex align-end py-3">
                                <v-card-title class="py-2">
                                    <translate>Personer per veckodag</translate>
                                </v-card-title>
                                <div>
                                    <v-list-item class="pl-0">
                                        <v-list-item-subtitle><translate>(senaste 7 dagarna)</translate></v-list-item-subtitle>
                                    </v-list-item>
                                </div>

                                <v-progress-circular
                                    v-if="loading.rooms || loading.graphs"
                                    indeterminate
                                    color="grey lighten-2"
                                    class="ml-auto mr-10"
                                />
                            </div>
                            <v-divider />
                            <v-card-text class="pa-0">
                                <Plotly
                                    v-if="!loading.rooms"
                                    :data="roomsPersonPerDayChart.data"
                                    :layout="roomsPersonPerDayChart.layout"
                                    :display-mode-bar="false"
                                    @afterplot="loading.graphs = false"
                                />
                                <v-skeleton-loader
                                    v-if="loading.rooms || loading.graphs"
                                    tile
                                    height="140"
                                    type="image"
                                />
                            </v-card-text>
                        </v-card>
                    </v-card>
                </v-col>
            </v-row>
        </template>
    </Page>
</template>

<script>
import { translate } from 'vue-gettext'
const $gettext = translate.gettext
import Page from '@/vue/views/layout/Page'
import DashboardStatsHeader from '../../components/statistics/DashboardStatsHeader'
import GraphsLayout from '@/vue/views/epm/mixins/GraphsLayout'
import { formatDate, localtimeSub, localtime } from '@/vue/helpers/datetime'

const getChartMax = (values) => {
    let max = -1
    let label = ''
    values.y.forEach((val, i) => {
        if (val > max) {
            max = val
            label = values.x[i]
        }
    })
    return {value: max < 0 ? 0 : max, label}
}

export default {
    name: 'StatisticsDashboard',
    components: {
        Page,
        DashboardStatsHeader,
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    mixins: [GraphsLayout],
    data() {
        return {
            callsStatsData: {
                graphs: {},
            },
            roomsStatsData: {
                graphs: {},
            },
            errors: {
                calls: null,
                rooms: null
            },
            loading: {
                calls: true,
                graphs: true,
                rooms: true
            },
            images: {
                illustrationCalls: require('@/assets/images/illustrations/calls.svg'),
                illustrationRooms: require('@/assets/images/illustrations/rooms.svg'),
            }
        }
    },
    computed: {
        callsGraphPerHour() {
            const graph = this.simpleLineChartDefaults()
            graph.layout.xaxis.tickformat = '%H:%M'
            graph.layout.height = 217
            // https://github.com/d3/d3-time-format/blob/master/README.md

            if (this.callsStatsData.graphs.seconds_per_hour) {
                graph.data[0].x = [ ...this.callsStatsData.graphs.seconds_per_hour.data[0].x ]
                graph.data[0].y = [ ...this.callsStatsData.graphs.seconds_per_hour.data[0].y ]
            }
            return graph
        },
        callsPieChartTotal() {
            const graph = this.simplePieChartDefaults()
            if (this.callsSummary.cospace_total) {
                const { duration, guest_duration } = this.callsSummary.cospace_total
                const userHours = duration - guest_duration

                graph.data[0].values = [userHours, guest_duration]
            }
            return graph
        },
        summary() {
            const result = {}
            Object.entries(this.callsStatsData.summary || {}).forEach(x => {
                result[x[0]] = x[0].match(/_total$/) ? x[1] : Object.entries(x[1]).map(y => ({ title: y[0], ...y[1] }))
            })
            return result
        },
        callsSummary() {
            let result = {
                peaks: {
                    perHour: {},
                },
                totals: {},
                extras: [],
            }

            if (!Object.keys(this.summary).length) {
                return result
            }

            result = { ...result, ...this.summary }
            result.totals = {
                ...result.totals,
                ...this.getCallStatsTotal(result),
            }
            result.legends = this.getCallStatsLegends(result.cospace_total)
            result.extras = this.getCallStatsExtras(result)

            if (this.callsGraphPerHour.data[0].y) {
                const max = getChartMax(this.callsGraphPerHour.data[0])

                result.peaks = {
                    perHour: {
                        label: $gettext('Peak'),
                        value: `${max.value} minuter kl ${max.label.split(' ')[1]}`,
                    },
                }
            }

            return result
        },
        roomsPersonPerHourChart() {
            const graph = this.simpleLineChartDefaults()
            graph.layout.height = 140
            graph.layout.xaxis.tickformat = ''

            if (this.roomsStatsData.graphs.per_hour) {
                const xaxis = [ ...this.roomsStatsData.graphs.per_hour.data[0].x ]
                graph.data[0].x = xaxis

                graph.data[0].y = [ ...this.roomsStatsData.graphs.per_hour.data[0].y ]
            }
            return graph
        },
        roomsPersonPerDayChart() {
            const graph = this.simpleBarChartDefaults()
            graph.layout.xaxis.tickformat = '%a'
            graph.layout.height = 140

            if (this.roomsStatsData.graphs.per_day) {
                graph.data[0].x = [ ...this.roomsStatsData.graphs.per_day.data[0].x ]
                graph.data[0].y = [ ...this.roomsStatsData.graphs.per_day.data[0].y ]
            }
            return graph
        },
        roomsSummary() {
            const result = {
                peaks: {
                    perHour: {},
                    perDay: {},
                },
                totals: {},
                extras: [],
            }

            if (!this.roomsStatsData) {
                return result
            }

            if (this.roomsPersonPerHourChart.data[0].y) {
                result.peaks = {
                    perHour: getChartMax(this.roomsPersonPerHourChart.data[0]),
                    perDay: getChartMax(this.roomsPersonPerDayChart.data[0]),
                }
            }

            if (result.peaks.perHour.value) {
                result.extras = result.extras.concat([
                    {
                        label: $gettext('Peak klockslag'),
                        value: result.peaks.perHour.value + ' @ ' + result.peaks.perHour.label
                    },
                    {
                        label: $gettext('Peak veckodag'),
                        value: result.peaks.perDay.value + ' @ ' + formatDate(result.peaks.perDay.label, 'eeee').toLowerCase()
                    },
                ])
            }

            return result
        },
    },
    mounted() {
        return this.getStats()
    },
    methods: {
        getCallStatsTotal(stats) {
            const total = parseInt(stats.cospace_total.duration, 10)
            const guest =  parseInt(stats.cospace_total.guest_duration, 10)
            return {
                total,
                guest,
                user: total - guest,
            }
        },
        getCallStatsExtras(stats) {
            return [
                {
                    label: $gettext('Unika samtal'),
                    value: parseInt(stats.cospace_total.call_count, 10)
                },
                {
                    label: $gettext('Deltagare'),
                    value: parseInt(stats.cospace_total.participant_count, 10)
                },
            ]
        },
        getCallStatsLegends(cospaceTotal) {
            const { duration, guest_duration } = cospaceTotal
            const userHours = duration - guest_duration

            const userPercent = userHours > 0 ? userHours / duration : 0
            const guestPercent = guest_duration > 0 ? guest_duration / duration : 0

            return [
                {
                    value: parseFloat(duration).toFixed(1),
                    percentage: '',
                    color: '',
                    label: $gettext('Timmar totalt'),
                },
                {
                    value: parseFloat(userHours).toFixed(1),
                    percentage: parseFloat(userPercent * 100).toFixed(1) + '%',
                    color: '#53B27B',
                    label: $gettext('Användartimmar'),
                },
                {
                    value: parseFloat(guest_duration).toFixed(1),
                    percentage: parseFloat(guestPercent * 100).toFixed(1) + '%x',
                    color: '#E71E18',
                    label: $gettext('Gästtimmar'),
                }
            ]
        },
        getStats() {
            this.loading.calls = true
            this.errors.calls = null
            this.loading.rooms = true
            this.errors.rooms = null

            this.getCallStats()
            this.getRoomStats()
        },
        getCallStats() {
            const params = {
                ts_start: localtimeSub({ hours: 24 }),
                ts_stop: localtime(),
                organization: null,
                protocol: null,
                only_gateway: false,
                multitenant: true,
                ignore_empty: true
            }

            return this.$store
                .api()
                .get('call_statistics/dashboard/', {params:params})
                .then(f => {
                    this.errors.calls = f.errors ? { ...f.errors } : null
                    this.loading.calls = false
                    this.callsStatsData = { ...f }
                    return f
                })
                .catch(e => {
                    this.loading.calls = false
                    this.errors.calls = e
                })
        },
        getRoomStats() {
            const params = {
                ts_start: localtimeSub({ days: 7 }),
                ts_stop: localtime(),
                server: 'person',
                only_gateway: false,
                only_hours: '7-17',
                only_days: '1-7',
                ignore_empty: 1,
                fill_gaps: 1,
                multitenant: true,
                ajax: 1
            }

            return this.$store
                .api()
                .get('room_statistics/dashboard/', {params:params})
                .then(f => {
                    this.errors.rooms = f.errors ? { ...f.errors } : null
                    this.loading.rooms = false
                    this.roomsStatsData = { ...f }
                    return f
                })
                .catch(e => {
                    this.loading.rooms = false
                    this.errors.rooms = e
                })
        }
    }
}
</script>
