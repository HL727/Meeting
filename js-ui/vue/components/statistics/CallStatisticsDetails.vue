<template>
    <div>
        <v-divider />

        <template v-if="stats.has_data">
            <v-tabs
                v-if="dataTab !== -1"
                v-model="dataTab"
            >
                <template v-if="isCallStats">
                    <v-tab :disabled="loading">
                        {{ $gettext('Översikt') }}
                    </v-tab>
                    <v-tab
                        v-if="showMeetingRooms"
                        :disabled="loading"
                    >
                        {{ $ngettext('Mötesrum', 'Mötesrum', 2) }}
                    </v-tab>
                    <v-tab :disabled="loading">
                        <translate>Deltagare</translate>
                    </v-tab>
                    <v-tab :disabled="loading">
                        <translate>Grupp</translate>
                    </v-tab>
                </template>

                <v-tab v-if="hasDebug">
                    <v-icon class="mr-1">
                        mdi-bug
                    </v-icon>
                    <translate>Samtal</translate>
                </v-tab>
                <v-tab v-if="hasDebug">
                    <v-icon class="mr-1">
                        mdi-bug
                    </v-icon>
                    <translate>Deltagare</translate>
                </v-tab>
            </v-tabs>

            <v-divider />

            <v-expand-transition>
                <v-skeleton-loader
                    v-if="loading && isFirstTab"
                    tile
                    type="image"
                    height="90"
                />
                <v-card
                    v-else-if="isFirstTab"
                    flat
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
                            <div class="ml-auto">
                                <p
                                    v-translate
                                    class="mb-2"
                                >
                                    Exportera rapport
                                </p>
                                <v-btn
                                    v-if="stats.excel_report_url && !isDebug"
                                    color="primary"
                                    target="_blank"
                                    small
                                    outlined
                                    :href="stats.excel_report_url"
                                >
                                    <v-icon left>
                                        mdi-file-excel
                                    </v-icon>
                                    <translate>Excel</translate>
                                </v-btn>

                                <v-btn
                                    v-if="stats.excel_debug_report_url"
                                    target="_blank"
                                    class="ml-2"
                                    color="primary"
                                    small
                                    outlined
                                    :href="stats.excel_debug_report_url"
                                >
                                    <v-icon left>
                                        mdi-file-excel
                                    </v-icon>
                                    <translate>Debug-data</translate>
                                </v-btn>

                                <v-btn
                                    v-if="!hideExportPdf && stats.pdf_report_url && !isDebug"
                                    small
                                    class="ml-2"
                                    outlined
                                    color="primary"
                                    target="_blank"
                                    :href="stats.pdf_report_url"
                                >
                                    <v-icon left>
                                        mdi-file-pdf
                                    </v-icon>
                                    <translate>PDF</translate>
                                </v-btn>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>
            </v-expand-transition>
        </template>
        <v-alert
            v-else
            type="warning"
            class="mt-4"
        >
            <translate>Kunde inte hitta någon matchande information!</translate>
        </v-alert>

        <v-tabs-items
            v-if="stats.has_data && dataTab !== -1"
            ref="tabs"
            v-model="dataTab"
        >
            <v-tab-item v-if="isCallStats">
                <template v-if="graphs.sametime_graph">
                    <v-divider class="mb-4" />
                    <h3><translate>Samtidiga användare</translate></h3>
                    <v-skeleton-loader
                        v-if="loading || !graphsLoaded"
                        tile
                        type="image"
                        class="mt-4"
                    />
                    <Plotly
                        v-if="!loading && graphs.sametime_graph"
                        :data="graphs.sametime_graph.data"
                        :layout="graphs.sametime_graph.layout"
                        responsive
                        @afterplot="graphsLoaded = true"
                    />
                </template>
                <v-divider class="mb-4" />
                <h3><translate>Timmar per dag</translate></h3>
                <v-skeleton-loader
                    v-if="loading || !graphsLoaded"
                    tile
                    type="image"
                    class="mt-4"
                />
                <Plotly
                    v-if="!loading && graphs.graph"
                    :data="graphs.graph.data"
                    :layout="graphs.graph.layout"
                    responsive
                    @afterplot="graphsLoaded = true"
                />
            </v-tab-item>
            <v-tab-item v-if="showMeetingRooms && isCallStats">
                <v-text-field
                    v-model="search.cospace"
                    single-line
                    append-icon="mdi-magnify"
                    :label="$gettext('Sök') + '...'"
                    outlined
                    hide-details
                    dense
                    class="mt-4"
                    style="max-width:20rem;"
                />

                <v-card flat>
                    <v-data-table
                        :loading="loading"
                        :items="summary.cospace"
                        :search="search.cospace"
                        :headers="[
                            { text: $ngettext('Mötesrum', 'Mötesrum', 1), value: 'title' },
                            { text: $gettext('Timmar'), value: '0' },
                            { text: $gettext('Gästtimmar'), value: '1' },
                            { text: $gettext('Deltagare'), value: '2' },
                            { text: $gettext('Samtal'), value: '3' },
                        ]"
                    >
                        <template v-slot:item.title="{ item }">
                            <v-icon
                                v-if="item[4]"
                                @click.prevent="$emit('refilter', { cospace: item[4] })"
                            >
                                mdi-filter
                            </v-icon>
                            <v-btn
                                v-if="item[4]"
                                icon
                                :to="{ name: 'cospaces_details', params: { id: item[4] } }"
                            >
                                <v-icon>mdi-open-in-new</v-icon>
                            </v-btn>
                            {{ item.title }}
                        </template>
                    </v-data-table>
                </v-card>
            </v-tab-item>
            <v-tab-item v-if="isCallStats">
                <v-text-field
                    v-model="search.stats"
                    single-line
                    append-icon="mdi-magnify"
                    :label="$gettext('Sök') + '...'"
                    outlined
                    hide-details
                    dense
                    class="mt-4"
                    style="max-width:20rem;"
                />
                <v-data-table
                    :loading="loading"
                    :items="summary.user"
                    :search="search.stats"
                    :headers="[
                        { text: $gettext('Deltagare'), value: 'title' },
                        { text: $gettext('Timmar'), value: '0' },
                        { text: $gettext('Samtal'), value: '3' },
                    ]"
                >
                    <template v-slot:item.title="{ item }">
                        <v-icon
                            @click.prevent="$emit('refilter', { member: item.title })"
                        >
                            mdi-filter
                        </v-icon>
                        <v-btn
                            v-if="item[4]"
                            icon
                            :to="{ name: 'user_details', params: { id: item[4] } }"
                        >
                            <v-icon>mdi-open-in-new</v-icon>
                        </v-btn>
                        {{ item.title }}
                    </template>
                </v-data-table>
            </v-tab-item>
            <v-tab-item v-if="isCallStats">
                <v-text-field
                    v-model="search.stats"
                    single-line
                    append-icon="mdi-magnify"
                    :label="$gettext('Sök') + '...'"
                    outlined
                    hide-details
                    dense
                    class="mt-4"
                    style="max-width:20rem;"
                />

                <v-data-table
                    :loading="loading"
                    :items="summary.target_group"
                    :search="search.stats"
                    :headers="[
                        { text: $gettext('Grupp'), value: 'title' },
                        { text: $gettext('Timmar'), value: '0' },
                        { text: $gettext('Samtal'), value: '3' },
                    ]"
                >
                    <template v-slot:item.title="{ item }">
                        <v-icon
                            v-if="$store.state.site.enableGroups"
                            @click.prevent="$emit('refilter', { ou: item.title })"
                        >
                            mdi-filter
                        </v-icon>
                        {{ item.title }}
                    </template>
                </v-data-table>
            </v-tab-item>
            <v-tab-item v-if="hasDebug">
                <v-text-field
                    v-model="search.debugCalls"
                    single-line
                    append-icon="mdi-magnify"
                    :label="$gettext('Sök') + '...'"
                    outlined
                    hide-details
                    dense
                    class="mt-4"
                    style="max-width:20rem;"
                />
                <v-data-table
                    :loading="loading"
                    :items="stats.calls"
                    :search="search.debugCalls"
                    :headers="[
                        { text: $gettext('Rubrik'), value: 'cospace' },
                        { text: $gettext('Grupp'), value: 'ou' },
                        { text: $gettext('Start'), value: 'ts_start' },
                        { text: $gettext('Stopp'), value: 'ts_stop' },
                        { text: $gettext('Deltagare'), value: 'leg_count' },
                        { text: $gettext('Längd'), value: 'total_duration' },
                    ]"
                >
                    <template v-slot:item.cospace="{ item }">
                        <a :href="item.debug_url">{{ item.cospace }}</a>
                    </template>
                    <template v-slot:item.ts_start="{ item }">
                        {{ item.ts_start|timestamp }}
                    </template>
                    <template v-slot:item.ts_stop="{ item }">
                        {{ item.ts_stop|timestamp }}
                    </template>
                </v-data-table>
            </v-tab-item>
            <v-tab-item v-if="hasDebug">
                <v-text-field
                    v-model="search.debugParticipants"
                    single-line
                    append-icon="mdi-magnify"
                    :label="$gettext('Sök') + '...'"
                    outlined
                    hide-details
                    dense
                    class="mt-4"
                    style="max-width:20rem;"
                />

                <v-data-table
                    :loading="loading"
                    :items="stats.legs"
                    :search="search.debugParticipants"
                    :headers="[
                        { text: $gettext('Motstående part'), value: 'remote' },
                        { text: $gettext('Lokal part'), value: 'local' },
                        { text: $gettext('Samtal'), value: 'cospace' },
                        { text: $gettext('Grupp'), value: 'ou' },
                        { text: $gettext('Start'), value: 'ts_start' },
                        { text: $gettext('Stopp'), value: 'ts_stop' },
                    ]"
                >
                    <template v-slot:item.remote="{ item }">
                        <a :href="item.debug_url">{{ item.remote || item.target }}</a>
                    </template>
                    <template v-slot:item.ts_start="{ item }">
                        {{ item.ts_start|timestamp }}
                    </template>
                    <template v-slot:item.ts_stop="{ item }">
                        {{ item.ts_stop|timestamp }}
                    </template>
                </v-data-table>
            </v-tab-item>
        </v-tabs-items>
    </div>
</template>

<script>
export default {
    components: {
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    props: {
        stats: { type: Object, default() { return {} } },
        graphs: { type: Object, default() { return {} } },
        loading: { type: Boolean, default: false },
        extras: { type: Array, default() { return [] } },

        showMeetingRooms: { type: Boolean, default: false },
        hideExportPdf: { type: Boolean, default: false }
    },
    data() {
        return {
            dataTab: 0,
            graphsLoaded: false,
            search: {},
        }
    },
    computed: {
        summary() {
            const result = {}
            Object.entries(this.stats.summary || {}).forEach(x => {
                result[x[0]] = x[0].match(/_total$/) ? x[1] : Object.entries(x[1]).map(y => ({ title: y[0], ...y[1] }))
            })

            this.$emit('summary', result)

            return result
        },
        isCallStats() {
            return !this.isDebug
        },
        isDebug() {
            return !!this.stats.debug
        },
        hasDebug() {
            return this.stats.calls && this.stats.calls.length > 0
        },
        isFirstTab() {
            return this.dataTab === 0
        }
    },
    watch: {
        summary(newValue) {
            this.$emit('summary', newValue)
        },
        isDebug() {
            this.dataTab = -1  // remove tab to reindex tab values
            this.$forceUpdate()  // also fix tab translations
            this.$nextTick(() => {
                this.dataTab = 0
            })
        }
    }
}
</script>
