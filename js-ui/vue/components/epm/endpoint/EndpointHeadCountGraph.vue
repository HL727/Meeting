<template>
    <div
        v-if="countGraph.count || loading"
        class="mb-4"
    >
        <h3 v-if="title">
            {{ title }}
        </h3>
        <v-alert
            v-if="!graphLoading && !countGraph.count"
            type="info"
            outlined
        >
            <translate>Hittar ingen historik.</translate>
        </v-alert>
        <v-card-text v-else-if="graphLoading || loading">
            <v-skeleton-loader
                tile
                type="image"
                height="100"
            />
        </v-card-text>
        <Plotly
            v-if="countGraph.count && !loading"
            :data="countGraph.count.data"
            :layout="{ ...countGraph.count.layout, height: 200 }"
            responsive
            v-bind="plotlyProps"
            @afterplot="graphLoading = false"
        />
    </div>
</template>
<script>
import SingleEndpointMixin from '../../../views/epm/mixins/SingleEndpointMixin'

import { translate } from 'vue-gettext'
const $gettext = translate.gettext

export default {
    name: 'EndpointHeadCount',
    components: {
        Plotly: () => import(/* webpackChunkName: "plotly" */ 'vue-plotly').then(p => p.Plotly),
    },
    mixins: [SingleEndpointMixin],
    props: {
        loading: { type: Boolean },
        title: { type: String, default: $gettext('Rumsanvändning, antal personer (senaste 48h)') },
        plotlyProps: { type: Object, required: false, default: null },
    },
    data() {
        return {
            countGraph: {},
            graphLoading: false,
        }
    },
    mounted() {
        setTimeout(() => this.load(), 400)
    },
    methods: {
        load() {
            this.graphLoading = true
            return this.$store.dispatch('endpoint/getHeadCount', { id: this.id, hours: 4 }).then(graph => {
                this.countGraph = graph || {}
                this.$emit('statsLoaded', this.countGraph)
            })
        },
    },
}
</script>
