<template>
    <PageAnalytics
        :title="$gettext('Rumsanalys')"
        icon="mdi-home-analytics"
        rooms
        display-head-count
        :enable-tenants="enableTenants"
    >
        <template v-slot:content="{ graphs, loading }">
            <template v-if="Object.keys(graphs).length">
                <v-divider class="mb-4" />
                <h3><translate>Max senaste 1h</translate></h3>
                <v-skeleton-loader
                    v-if="loading || !graphsLoaded"
                    tile
                    type="image"
                    class="mt-4"
                />
                <Plotly
                    v-if="!loading && graphs.now"
                    :data="graphs.now.data"
                    :layout="graphs.now.layout"
                    responsive
                    @afterplot="graphsLoaded = true"
                />
                <v-divider class="my-4" />
                <HeadCountGraphs
                    :graphs="graphs"
                    :graphs-loaded="graphsLoaded"
                    :loading="loading"
                />
            </template>
            <v-alert
                v-else
                type="warning"
            >
                <translate>Kunde inte hitta någon matchande information!</translate>
            </v-alert>
        </template>
    </PageAnalytics>
</template>

<script>
import PageAnalytics from '@/vue/views/layout/PageAnalytics'
import HeadCountGraphs from '@/vue/components/statistics/HeadCountGraphs'

export default {
    name: 'EPMRoomStatistics',
    components: {
        PageAnalytics,
        HeadCountGraphs,
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    props: {
        enableTenants: { type: Boolean, default: false },
    },
    data() {
        return {
            graphsLoaded: false,
        }
    }
}
</script>
