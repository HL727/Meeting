<template>
    <v-snackbar
        v-model="show"
        :bottom="true"
        :timeout="1500"
    >
        <translate>Text kopierad till urklipp.</translate>
        <v-btn
            dark
            text
            @click="show = false"
        >
            <translate>Stäng</translate>
        </v-btn>
    </v-snackbar>
</template>

<script>
export default {
    name: 'ClipboardSnackbar',
    data() {
        return {
            show: false
        }
    },
    methods: {
        copy(text, container) {
            this.show = true

            this.$copyText(text, container)
        }
    }
}
</script>
