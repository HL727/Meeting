<template>
    <EPMRoomStatistics :enable-tenants="multitenant" />
</template>

<script>
import EPMRoomStatistics from '@/vue/views/epm/EPMRoomStatistics'

export default {
    name: 'RoomStatistics',
    components: {
        EPMRoomStatistics
    },
    props: {
        multitenant: { type: Boolean },
    },
}
</script>
