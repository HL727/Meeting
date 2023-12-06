<template>
    <span>{{ uptime }}</span>
</template>

<script>
export default {
    props: {
        endpoint: { type: Object, default() { return {} }  },
    },
    computed: {
        uptime() {
            if (!('uptime' in this.endpoint.status)) return 0

            return this.endpoint.status.uptime
        },
    },
}
</script>
