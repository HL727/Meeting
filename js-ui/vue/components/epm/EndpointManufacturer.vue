<template>
    <span>{{ manufacturerText }}</span>
</template>

<script>
import { endpointManufacturerNames } from '@/vue/store/modules/endpoint/consts'

export default {
    props: {
        endpoint: { type: Object, default() { return {} } },
    },
    computed: {
        manufacturer() {
            return this.endpoint.manufacturer
        },
        manufacturerText() {
            return endpointManufacturerNames[this.manufacturer] || 'Other'
        },
    },
}
</script>
