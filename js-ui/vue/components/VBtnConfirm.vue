<template>
    <v-dialog
        modal
        max-width="320"
    >
        <template v-slot:activator="{ on: dialog }">
            <!-- TODO fix class="...", not in $attrs. Probably on v-dialog  -->
            <v-tooltip
                v-if="tooltip"
                bottom
            >
                <template v-slot:activator="{ on: tooltip, attrs }">
                    <v-btn
                        :class="buttonClass"
                        v-bind="{...$attrs, ...$attrs.bind, ...attrs}"
                        v-on="{ ...dialog, ...tooltip }"
                    >
                        <slot />
                    </v-btn>
                </template>
                <span>{{ tooltip }}</span>
            </v-tooltip>
            <v-btn
                v-else
                :class="buttonClass"
                v-bind="{...$attrs, ...$attrs.bind}"
                v-on="dialog"
            >
                <slot />
            </v-btn>
        </template>

        <v-card>
            <v-card-title>
                <translate>Bekräfta</translate>
            </v-card-title>
            <v-card-text>
                <slot name="dialog-text">
                    <span>{{ dialogText }}</span>
                </slot>
            </v-card-text>
            <v-divider class="my-0" />
            <v-card-actions>
                <v-btn
                    v-close-dialog
                    text
                    color="green"
                    @click="$emit('confirm')"
                    v-on="$listeners"
                >
                    <translate>Ja</translate>
                </v-btn>
                <v-btn
                    v-close-dialog
                    text
                    color="red"
                    @click="$emit('cancel')"
                >
                    <translate>Nej</translate>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

export default {
    inheritAttrs: false,
    props: {
        dialogText: { type: String, default: $gettext('Är du säker?') },
        tooltip: { type: String, default: '' },
        buttonClass: { type: String, default: '' }
    },
}
</script>
