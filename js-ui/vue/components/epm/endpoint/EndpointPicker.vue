<template>
    <v-dialog
        max-width="1280px"
        scrollable
    >
        <template v-slot:activator="{ on }">
            <slot v-on="on">
                <v-btn
                    v-if="button"
                    color="primary"
                    v-on="on"
                >
                    <translate>{{ buttonText }}</translate>
                </v-btn>
                <v-text-field
                    v-else
                    readonly
                    :value="textValue"
                    v-on="on"
                />
            </slot>
        </template>

        <v-card>
            <v-card-title>
                <translate>Välj system</translate>
            </v-card-title>
            <v-divider />
            <v-card-text>
                <EndpointGrid
                    v-model="selected"
                    checkbox
                    :table-height="400"
                    :only-head-count="onlyHeadCount"
                    v-bind="$attrs"
                />
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-btn
                    ref="actionButton"
                    color="primary"
                    @click="done"
                >
                    {{ actionButtonText }}
                </v-btn>
                <v-spacer />
                <v-btn
                    v-close-dialog
                    color="red"
                    text
                >
                    <translate>Stäng</translate>
                    <v-icon
                        right
                        dark
                    >
                        mdi-close
                    </v-icon>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import EndpointGrid from '@/vue/components/epm/endpoint/EndpointGrid'
import { closeDialog } from '@/vue/helpers/dialog'
export default {
    components: { EndpointGrid },
    inheritAttrs: false,
    props: {
        button: {
            type: Boolean,
            default: false
        },
        buttonText: {
            type: String,
            default: $gettext('Välj system'),
        },
        actionButtonText: {
            type: String,
            default: $gettext('Välj'),
        },
        onlyHeadCount: { type: Boolean, default: false },
    },
    data() {
        return {
            selected: [],
        }
    },
    computed: {
        textValue() {
            if (!this.selected || !this.selected.length) {
                return this.buttonText
            }
            const endpoints = this.$store.state.endpoint.endpoints
            return this.selected.map(e => endpoints[e]?.title).join(', ')
        }
    },
    methods: {
        done() {
            this.$emit('confirm', this.selected)
            this.$emit('input', this.selected)
            closeDialog(this.$refs.actionButton)
        },
    },
}
</script>
