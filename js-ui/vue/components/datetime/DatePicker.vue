<template>
    <v-dialog
        v-model="dialog"
        width="290px"
    >
        <template v-slot:activator="{ on }">
            <v-text-field
                v-model="date"
                :label="inputAttrs.label || null"
                :name="inputName"
                v-bind="inputAttrs"
                append-icon-outer="mdi-calendar"
                hide-details
                @click:append-outer="on.click"
                @keydown.down="on.click"
            />
        </template>
        <v-date-picker
            v-if="dialog"
            v-model="date"
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
        value: { type: [Date, String], default: null },
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
            date: null,
        }
    },
    watch: {
        date() {
            this.$emit('input', this.date)
        },
    },
    created() {
        if (this.value) this.date = parseDateString(this.value).date
    },
}
</script>
