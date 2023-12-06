<template>
    <v-card>
        <v-card-title class="headline">
            <translate>Lägg till ny rumskontroll</translate>
        </v-card-title>
        <v-divider />
        <v-card-text>
            <v-text-field
                v-model="form.title"
                :label="$gettext('Rubrik')"
                required
            />
            <v-textarea
                v-model="form.description"
                outlined
                :label="$gettext('Beskrivning')"
            />

            <v-card>
                <v-tabs
                    v-model="tab"
                    background-color="transparent"
                    color="primary"
                    grow
                >
                    <v-tab key="files">
                        <translate>Filer</translate>
                    </v-tab>
                    <v-tab key="zip">
                        <translate>Zip</translate>
                    </v-tab>
                </v-tabs>
                <v-card-text>
                    <v-tabs-items v-model="tab">
                        <v-tab-item key="files">
                            <v-file-input
                                v-model="form.fileXml"
                                multiple
                                counter
                                outlined
                                dense
                                small-chips
                                display-size
                                accept=".xml,.js"
                                :label="$gettext('Panel/makro (xml, js)')"
                            />
                        </v-tab-item>
                        <v-tab-item key="zip">
                            <v-file-input
                                v-model="form.fileZip"
                                outlined
                                dense
                                display-size
                                accept=".zip"
                                :label="$gettext('Paketerad zip')"
                            />
                        </v-tab-item>
                    </v-tabs-items>
                </v-card-text>
            </v-card>
        </v-card-text>

        <v-progress-linear
            color="primary"
            :active="!!uploading"
            :value="uploading"
        />
        <ErrorMessage
            :error="error"
            dense
            tile
            class="mb-0"
        />
        <v-divider v-if="!error" />

        <v-card-actions>
            <v-btn
                color="primary"
                :disabled="!valid || !!uploading"
                @click="create"
            >
                <translate>Lägg till</translate>
            </v-btn>
            <v-spacer />
            <v-btn
                text
                color="red"
                :disabled="!!uploading"
                @click="$emit('close')"
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
</template>

<script>
import ErrorMessage from '@/vue/components/base/ErrorMessage'
export default {
    components: { ErrorMessage },
    data() {
        return {
            form: {
                title: '',
                description: '',
                fileXml: [],
                fileZip: null,
            },
            tab: 0,
            uploading: 0,
            error: ''
        }
    },
    computed: {
        valid() {
            const formData = {
                ...this.form,
                fileType: this.tab === 0 ? 'files' : 'zip',
            }

            if (formData.title === '') {
                return false
            }
            if (formData.fileType === 'zip' && formData.fileZip === null) {
                return false
            }
            if (
                formData.fileType === 'files' &&
                !formData.fileXml.length
            ) {
                return false
            }

            return true
        },
    },
    methods: {
        create() {
            this.error = ''
            const fileType = this.tab === 0 ? 'files' : 'zip'

            const formData = new FormData()
            formData.append('title', this.form.title)
            formData.append('description', this.form.description)

            if (fileType === 'zip') {
                formData.append('files', this.form.fileZip, this.form.fileZip.name)
            } else if (fileType === 'files') {
                for (const file of this.form.fileXml) {
                    formData.append('files', file, file.name)
                }
            }
            const progress = percent => {
                this.uploading = percent * 100
            }

            this.$store.dispatch('roomcontrol/createControl', { form: formData, progress }).then(() => {
                this.uploading = 0
                this.$emit('created')
            }).catch(e => {
                this.error = e
                this.uploading = 0
            })
        },
    }
}
</script>
