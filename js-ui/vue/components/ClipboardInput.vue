<template>
    <span>
        <slot v-bind="{ copy, popup }">
            <v-text-field
                readonly
                hide-details
                :value="$attrs.value"
                append-icon="mdi-content-copy"
                :append-outer-icon="openExternal ? 'mdi-open-in-new' : undefined"
                v-bind="$attrs"
                @click:append="copy($attrs.value)"
                @click:append-outer="popup(externalValue || $attrs.value)"
                v-on="$listeners"
            />
        </slot>
        <ClipboardSnackbar ref="snackbar" />
    </span>
</template>

<script>
import ClipboardSnackbar from '@/vue/components/ClipboardSnackbar'
export default {
    name: 'ClipboardInput',
    components: { ClipboardSnackbar },
    inheritAttrs: false,
    props: {
        openExternal: { type: Boolean, default: false },
        externalValue: { type: String, default: '' },
    },
    methods: {
        copy(text, container) {
            this.$refs.snackbar.copy(text, container)
        },
        popup(url) {
            window.open(url)
        }
    },
}
</script>
