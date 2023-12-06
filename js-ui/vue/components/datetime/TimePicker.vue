<template>
    <v-dialog
        v-model="dialog"
        width="290px"
    >
        <template v-slot:activator="{ on }">
            <v-text-field
                v-model="time"
                :label="label"
                :name="inputName"
                v-bind="inputAttrs"
                append-icon-outer="mdi-clock"
                hide-details
                v-on="on"
                @click:append-outer="on.click"
                @keydown.down="on.click"
            />
        </template>
        <v-time-picker
            v-if="dialog"
            v-model="time"
            format="24hr"
            full-width
            @change="dialog = false"
        />
    </v-dialog>
</template>

<script>
import { parseDateString } from '@/vue/helpers/datetime'

export default {
    inheritAttrs: false,
    props: {
        value: { type: String, default: '' },
        inputName: { type: String, default: '' },
        inputAttrs: {
            type: Object,
            default() {
                return {}
            },
        },
    },
    data() {
        return {
            dialog: false,
            time: null,
        }
    },
    watch: {
        time() {
            this.$emit('input', this.time)
        },
    },
    created() {
        if (this.value) this.time = parseDateString(this.value).time
    },
}
</script>
