<template>
    <StatsForm
        v-bind="$attrs"
        ref="statsForm"
        only-epm
        v-on="$listeners"
    />
</template>

<script>
import StatsForm from '../../statistics/StatsForm'
export default {
    name: 'EPMStatsForm',
    components: { StatsForm },
    inheritAttrs: false,
    data() {
        return {
        }
    },
    computed: {
        allowDebug() {
            return this.$refs.statsForm?.allowDebug || {}
        }
    },
    methods: {
        submit() {
            return this.$refs.statsForm.submit()
        },
        reset() {
            return this.$refs.statsForm.reset()
        },
    }
}
</script>
