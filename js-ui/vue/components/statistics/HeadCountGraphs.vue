<template>
    <div>
        <div
            v-if="graphs.per_date || loading"
            :loading="loading"
            class="mb-4"
        >
            <h3><translate>Antal deltagare per datum</translate></h3>
            <v-skeleton-loader
                v-if="!graphsLoaded || loading"
                tile
                type="card"
            />
            <Plotly
                v-if="!loading && graphs.per_date"
                :data="graphs.per_date.data"
                :layout="graphs.per_date.layout"
                responsive
                @afterplot="graphsLoaded = true"
            />
        </div>
        <v-divider class="mb-4" />
        <v-row>
            <v-col
                v-if="graphs.per_hour || loading"
                md="6"
                :loading="loading"
            >
                <div class="mb-4">
                    <h3><translate>Antal deltagare per klockslag</translate></h3>
                    <v-skeleton-loader
                        v-if="!graphsLoaded || loading"
                        tile
                        type="card"
                    />
                    <Plotly
                        v-if="!loading && graphs.per_hour"
                        :data="graphs.per_hour.data"
                        :layout="graphs.per_hour.layout"
                        responsive
                        @afterplot="graphsLoaded = true"
                    />
                </div>
            </v-col>
            <v-col
                v-if="graphs.per_hour || loading"
                md="6"
                :loading="loading"
            >
                <div class="mb-4">
                    <h3><translate>Antal deltagare per veckodag</translate></h3>
                    <v-skeleton-loader
                        v-if="!graphsLoaded || loading"
                        tile
                        type="card"
                    />
                    <Plotly
                        v-if="!loading && graphs.per_day"
                        :data="graphs.per_day.data"
                        :layout="graphs.per_day.layout"
                        responsive
                        @afterplot="graphsLoaded = true"
                    />
                </div>
            </v-col>
        </v-row>
    </div>
</template>
<script>
export default {
    name: 'HeadCountGraphs',
    components: {
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    props: {
        graphs: { type: Object, default() { return {} }},
        loading: { type: Boolean, default: false },
    },
    data() {
        return {
            graphsLoaded: false,
        }
    }
}
</script>
