<template>
    <div class="stats-header">
        <v-list-item class="py-2">
            <div
                v-if="loading"
                class="d-flex"
            >
                <v-skeleton-loader
                    width="140"
                    max-width="50%"
                    type="list-item-two-line"
                    style="margin:-16px"
                    class="mr-4 pl-0"
                />
                <v-skeleton-loader
                    width="140"
                    max-width="50%"
                    type="list-item-two-line"
                    style="margin:-16px"
                    class="pl-0"
                />
            </div>
            <ErrorMessage
                v-else-if="error"
                :error="error"
                dense
                outlined
                class="mb-0"
                style="margin-right:15rem;"
            />
            <v-alert
                v-else-if="noData"
                dense
                outlined
                type="info"
                style="margin-right:15rem;"
                class="mb-0"
            >
                <p class="mb-0">
                    <strong v-translate>Ingen data</strong>:
                </p>
                <translate>Ingen data hittades för att visa statistik</translate>
            </v-alert>
            <div
                v-else
                class="d-flex"
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
            <img
                :src="image"
                class="stats-illustration"
            >
        </v-list-item>
        <v-list-item
            v-if="!error && !noData && !hidePieChart"
            class="py-2"
        >
            <Plotly
                v-if="!loading"
                :data="pieChart.data"
                :layout="pieChart.layout"
                :display-mode-bar="false"
                class="mr-6"
                @afterplot="loadingGraph = false"
            />
            <v-list-item-content>
                <div
                    v-if="loading || loadingGraph"
                    class="d-flex align-center"
                >
                    <v-avatar
                        size="96"
                        class="mr-4"
                        color="grey lighten-3"
                    />
                    <v-skeleton-loader
                        width="100%"
                        max-width="200"
                        type="list-item-three-line"
                        class="mr-4"
                    />
                </div>
                <div
                    v-else
                    class="d-flex align-center"
                >
                    <v-simple-table
                        dense
                        class="mr-10"
                    >
                        <template v-slot:default>
                            <tbody>
                                <tr
                                    v-for="legend in legends"
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
                </div>
            </v-list-item-content>
        </v-list-item>
    </div>
</template>

<script>

import ErrorMessage from '@/vue/components/base/ErrorMessage'
export default {
    components: {
        ErrorMessage,
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    props: {
        title: { type: String, default: '' },
        advancedRoute: { type: Object, default() { return {} } },
        pieChart: { type: Object, default() { return {} } },
        error: { type: [Error, Object], default: null },
        legends: { type: Array, default: () => [] },
        extras: { type: Array, default: () => [] },
        loading: { type: Boolean, default: true },
        image: { type: String, default: '' },
        noData: { type: Boolean, default: false },
        hidePieChart: { type: Boolean, default: false }
    },
    data() {
        return {
            loadingGraph: true
        }
    }
}
</script>

<style scoped lang="scss">
    .stats-header {
        position: relative;
    }
    .stats-illustration {
        height: auto;
        width: 200px;
        max-width: 50%;
        margin: -100px -10px -20px auto;
        position: absolute;
        right: 0;
        top: 0;
    }
    tbody {
        tr:hover {
            background-color: transparent !important;
        }
        td {
            border: none !important;
        }
    }
</style>
