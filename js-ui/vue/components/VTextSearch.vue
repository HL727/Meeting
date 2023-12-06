<template>
    <v-text-field
        v-bind="computedProps"
        hide-details
        clearable
        solo
        dense
        outlined
        flat
        prepend-inner-icon="mdi-magnify"
        v-on="$listeners"
    />
</template>

<script>
import { VTextField } from 'vuetify/lib'

export default {
    name: 'VTextSearch',
    extends: VTextField,

    computed: {
        computedProps() {
            return {
                ...this.$props
            }
        }
    }
}
</script>
