<template>
    <EndpointTaskGrid
        ref="grid"
        :endpoint-id="id"
        @refreshed="emitter.emit('loading', false)"
    />
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'

import EndpointTaskGrid from '@/vue/components/epm/endpoint/EndpointTaskGrid'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'

export default {
    name: 'EndpointTasks',
    components: { EndpointTaskGrid },
    mixins: [SingleEndpointMixin],
    data() {
        return {
            emitter: new GlobalEventBus(this),
        }
    },
    mounted() {
        this.emitter.on('refresh', () => { this.$refs.grid.loadData() })
    }
}
</script>
