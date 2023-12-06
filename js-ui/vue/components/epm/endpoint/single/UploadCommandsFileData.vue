<template>
    <v-card
        v-if="!endpoint.has_direct_connection"
        class="mt-4"
    >
        <v-card-title>
            <translate>Uppdatera kommandospecifikation manuellt</translate>
        </v-card-title>
        <v-card-text>
            <v-form @submit.prevent="uploadCommand">
                <p>
                    1.
                    <translate>Ladda ner fil från systemet</translate>
                    :
                    <a
                        v-if="endpoint.ip"
                        :href="`https://${endpoint.ip}/command.xml`"
                        target="_blank"
                    >command.xml</a>
                    <span v-else>https://[IP]/command.xml</span>
                </p>
                <p>
                    2.
                    <translate>Ladda ner fil från systemet</translate>
                    :
                    <a
                        v-if="endpoint.ip"
                        :href="`https://${endpoint.ip}/valuespace.xml`"
                        target="_blank"
                    >valuespace.xml</a>
                    <span v-else>https://[IP]/valuespace.xml</span>
                </p>
                <v-file-input
                    v-model="form.command"
                    :label="'3. '+ $gettext('Ladda upp command.xml')"
                />
                <v-file-input
                    v-model="form.valuespace"
                    :label="'4. '+ $gettext('Ladda upp valuespace.xml')"
                />
                <v-btn
                    :disabled="!form.command || !form.valuespace"
                    type="submit"
                    color="primary"
                >
                    <translate>Ladda upp</translate>
                </v-btn>
            </v-form>
        </v-card-text>
    </v-card>
</template>
<script>
export default {
    name: 'UploadCommandsFileData',
    props: {
        endpoint: { type: Object, required: true },
    },
    data() {
        return {
            form: {
                command: null,
                valuespace: null,
            },
        }
    },
    methods: {
        uploadCommand() {
            const updateFormData = new FormData()
            updateFormData.append('command', this.form.command, this.form.command.name)
            updateFormData.append('valuespace', this.form.valuespace, this.form.valuespace.name)

            const progress = percent => {
                this.uploading = percent * 100
            }

            return this.$store
                .dispatch('endpoint/uploadCommand', {
                    endpointId: this.endpoint.id,
                    form: updateFormData,
                    progress
                })
                .then(() => {
                    this.form.command = null
                    this.form.valuespace = null
                    this.$emit('done')
                })
                .catch(e => this.$emit('error', e))
        },
    }
}
</script>
