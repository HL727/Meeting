<template>
    <v-dialog
        :value="value"
        scrollable
        max-width="800"
        @input="$emit('cancel')"
    >
        <v-card>
            <v-card-title class="headline">
                <translate>Välj mall</translate>
            </v-card-title>
            <v-divider />
            <v-card-text class="pa-0">
                <EndpointTemplateGrid
                    v-model="selectedTemplate"
                    :templates="templates"
                    :loading="loading"
                    @error="error = $event"
                />
            </v-card-text>
            <v-divider />
            <ErrorMessage :error="error" />
            <v-card-actions>
                <v-btn
                    color="primary"
                    :disabled="!selectedTemplate.length"
                    @click="$emit('load', selectedTemplate)"
                >
                    <translate>Välj mall</translate>
                </v-btn>
                <v-spacer />
                <v-btn
                    text
                    color="red"
                    @click="$emit('cancel')"
                >
                    <translate>Avbryt</translate>
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
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import EndpointTemplateGrid from '@/vue/components/epm/EndpointTemplateGrid'

export default {
    name: 'EndpointTemplatePicker',
    components: { ErrorMessage, EndpointTemplateGrid },
    props: {
        requireCommands: Boolean,
        requireSettings: Boolean,
        value: Boolean,
    },
    data() {
        return {
            selectedTemplate: [],
            loading: false,
            error: null
        }
    },
    computed: {
        templates() {
            let items = Object.values(this.$store.state.endpoint.templates) || []
            if (this.requireCommands) items = items.filter(t => t.commands && !!t.commands.length)
            if (this.requireSettings) items = items.filter(t => t.settings && !!t.settings.length)
            return items
        },
    },
    watch: {
        value() {
            this.$store.dispatch('endpoint/getTemplates')
        }
    },
    mounted() {
        this.loading = true
        return this.$store.dispatch('endpoint/getTemplates').then(() => this.loading = false)
    },
}
</script>
