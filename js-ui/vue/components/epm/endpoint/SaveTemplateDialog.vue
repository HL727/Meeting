<template>
    <v-dialog
        v-model="internalValue"
        max-width="320"
    >
        <v-card>
            <v-card-title class="headline">
                <translate>Spara som mall</translate>
            </v-card-title>
            <v-divider />
            <v-card-text>
                <v-text-field
                    v-model="newTemplateName"
                    :label="$gettext('Namn på mall')"
                />
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-btn
                    color="primary"
                    :disabled="!newTemplateName"
                    @click="saveTemplate"
                >
                    <translate>Spara mall</translate>
                </v-btn>
                <v-spacer />
                <v-btn
                    color="red"
                    text
                    @click="internalValue = false"
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
export default {
    name: 'SaveTemplateDialog',
    props: {
        value: { type: Boolean, required: true },
        endpoint: { type: Object, required: true },
        configuration: { type: Array, required: false, default() { return [] }},
        commands: { type: Array, required: false, default() { return [] }},
    },
    data() {
        return {
            newTemplateName: '',
            internalValue: this.value,
        }
    },
    watch: {
        value(val) {
            this.internalValue = val
        },
        internalValue(val) {
            this.$emit('input', val)
        }
    },
    methods: {
        serializeConfiguration() {
            return (this.configuration || []).map(config => ({
                key: config.path,
                value: config.value,
            }))
        },
        serializeCommands() {
            return (this.commands || []).map(command => ({
                command: command.command.path,
                arguments: command.arguments,
                body: command.body,
            }))
        },
        saveTemplate() {
            const settings = this.serializeConfiguration()
            const commands = this.serializeCommands()

            return this.$store
                .dispatch('endpoint/saveTemplate', {
                    name: this.newTemplateName,
                    manufacturer: this.endpoint.manufacturer,
                    model: this.endpoint.product_name,
                    settings,
                    commands,
                })
                .then(template => {
                    this.internalValue = false
                    this.newTemplateName = ''
                    this.$emit('created', template)
                })
        }
    }
}
</script>
