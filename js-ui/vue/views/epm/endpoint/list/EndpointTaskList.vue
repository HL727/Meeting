<template>
    <div>
        <EndpointTaskGrid
            ref="grid"
            @loading="emitter.emit('loading', true)"
            @refreshed="emitter.emit('loading', false)"
        />
    </div>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'

import EndpointTaskGrid from '@/vue/components/epm/endpoint/EndpointTaskGrid'

export default {
    name: 'EndpointTaskList',
    components: { EndpointTaskGrid },
    data() {
        return {
            emitter: new GlobalEventBus(this),
        }
    },
    mounted() {
        this.emitter.on('refresh', () => this.$refs.grid.loadData())
    },
}
</script>
