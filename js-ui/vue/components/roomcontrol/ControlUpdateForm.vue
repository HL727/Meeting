<template>
    <v-card>
        <v-card-title class="headline mb-2">
            {{ control.title }}
        </v-card-title>
        <v-card-subtitle><translate>Skapad</translate> {{ control.created }}</v-card-subtitle>

        <v-divider />
        <v-tabs
            v-model="tab"
            background-color="transparent"
            color="primary"
            grow
            @change="resetFormStatus(false)"
        >
            <v-tab key="content">
                <translate>Innehåll</translate>
            </v-tab>
            <v-tab key="files">
                <translate>Filer</translate>
            </v-tab>
            <v-tab key="upload">
                <translate>Ladda upp</translate>
            </v-tab>
            <v-tab key="endpoints">
                <translate>System</translate>
            </v-tab>
            <v-tab key="delete">
                <translate>Ta bort</translate>
            </v-tab>
        </v-tabs>
        <v-divider />

        <v-card-text class="px-2 pb-0">
            <v-tabs-items v-model="tab">
                <v-tab-item key="content">
                    <v-card-text>
                        <v-text-field
                            v-model="form.title"
                            :label="$gettext('Rubrik')"
                            :disabled="formDisabled"
                            required
                        />
                        <v-textarea
                            v-model="form.description"
                            outlined
                            :disabled="formDisabled"
                            :label="$gettext('Beskrivning')"
                        />
                    </v-card-text>
                </v-tab-item>
                <v-tab-item key="files">
                    <v-alert
                        v-if="!stateControl.isPanel && !stateControl.isMacro"
                        type="info"
                        class="mt-3"
                    >
                        <translate>Det finns inga kopplade panel- eller makrofiler just nu</translate>
                    </v-alert>

                    <v-list
                        v-if="stateControl.isPanel"
                        dense
                    >
                        <v-subheader><translate>Panel xml files</translate></v-subheader>
                        <v-list-item
                            v-for="file in stateControl.panels"
                            :key="`file-${file.id}`"
                            link
                            class="px-2"
                        >
                            <v-list-item-content>
                                <v-list-item-title v-text="file.name" />
                            </v-list-item-content>
                            <v-list-item-action>
                                <v-btn
                                    color="red"
                                    :disabled="formDisabled"
                                    icon
                                    @click="unlinkFile(file)"
                                >
                                    <v-icon>mdi-delete</v-icon>
                                </v-btn>
                            </v-list-item-action>
                        </v-list-item>
                    </v-list>
                    <v-divider
                        v-if="stateControl.isPanel && stateControl.isMacro"
                    />
                    <v-list
                        v-if="stateControl.isMacro"
                        dense
                    >
                        <v-subheader><translate>Macro js files</translate></v-subheader>
                        <v-list-item
                            v-for="file in stateControl.macros"
                            :key="`file-${file.id}`"
                            link
                            class="px-2"
                        >
                            <v-list-item-content>
                                <v-list-item-title v-text="file.name" />
                            </v-list-item-content>
                            <v-list-item-action>
                                <v-btn
                                    color="red"
                                    :disabled="formDisabled"
                                    icon
                                    @click="unlinkFile(file)"
                                >
                                    <v-icon>mdi-delete</v-icon>
                                </v-btn>
                            </v-list-item-action>
                        </v-list-item>
                    </v-list>
                </v-tab-item>
                <v-tab-item key="upload">
                    <v-card-text>
                        <v-file-input
                            v-model="form.files"
                            outlined
                            multiple
                            counter
                            dense
                            display-size
                            :disabled="formDisabled"
                            accept=".zip,.xml,.js"
                            :label="$gettext('Välj filer')"
                        />
                    </v-card-text>
                </v-tab-item>
                <v-tab-item key="endpoints">
                    <v-card-text>
                        <v-data-table
                            v-if="matchedEndpoints.length"
                            v-model="selectedEndpoints"
                            :items="matchedEndpoints"
                            :headers="endpointHeaders"
                            show-select
                            :hide-default-footer="matchedEndpoints.length <= 5"
                        />
                        <v-alert
                            v-else
                            type="info"
                        >
                            <translate>Denna kontroll är inte installerad i något system</translate>
                        </v-alert>
                    </v-card-text>
                </v-tab-item>
                <v-tab-item key="delete">
                    <v-card-text class="text-center">
                        <v-btn
                            color="red"
                            dark
                            :disabled="formDisabled"
                            @click="deleteControl()"
                        >
                            <span><translate>Ta bort</translate> {{ control.title }}</span>
                        </v-btn>
                    </v-card-text>
                </v-tab-item>
            </v-tabs-items>
        </v-card-text>

        <v-alert
            v-model="successAlert"
            tile
            dense
            dismissible
            border="top"
            type="success"
            class="mb-0"
        >
            {{ success }}
        </v-alert>
        <v-alert
            v-model="errorAlert"
            tile
            dense
            dismissible
            border="top"
            type="error"
            class="mb-0"
        >
            {{ error }}
        </v-alert>
        <v-divider v-if="!successAlert && !errorAlert" />
        <v-progress-linear
            color="primary"
            :active="!!uploading"
            :value="uploading"
        />
        <v-progress-linear
            color="primary"
            indeterminate
            :active="loading && !uploading"
        />

        <v-card-actions>
            <v-btn
                v-if="tab === 0"
                color="primary"
                :disabled="formDisabled"
                @click="updateControl"
            >
                <translate>Uppdatera</translate>
            </v-btn>
            <v-btn
                v-else-if="tab === 2"
                color="primary"
                :disabled="formDisabled"
                @click="uploadFiles"
            >
                <translate>Ladda upp</translate>
                <v-icon
                    right
                    dark
                >
                    mdi-cloud-upload
                </v-icon>
            </v-btn>
            <span v-else-if="tab === 3">
                <EndpointPicker
                    v-if="!selectedEndpoints.length"
                    :button-text="$gettext('Lägg till')"
                    button
                    :action-button-text="$gettext('Installera i system')"
                    @confirm="provisionEndpoints($event)"
                />
                <v-btn
                    v-if="selectedEndpoints.length"
                    color="primary"
                    @click="provisionEndpoints(selectedEndpoints)"
                >
                    <translate>Ominstallera</translate>
                    <v-icon
                        right
                        dark
                    >mdi-reload</v-icon>
                </v-btn>
                <v-btn
                    v-if="selectedEndpoints.length"
                    color="error"
                    class="ml-3"
                    @click="deprovisionEndpoints"
                >
                    <translate>Radera</translate>
                    <v-icon
                        right
                        dark
                    >mdi-delete</v-icon>
                </v-btn>
            </span>

            <v-spacer />
            <v-btn
                text
                color="red"
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
import { $gettext, $gettextInterpolate } from '@/vue/helpers/translate'
import EndpointPicker from '@/vue/components/epm/endpoint/EndpointPicker'
import { timestamp } from '@/vue/helpers/datetime'

export default {
    components: { EndpointPicker },
    props: {
        control: { type: Object, required: true },
    },
    data() {
        return {
            form: {
                title: '',
                description: '',
                files: []
            },
            tab: 0,
            loading: false,
            uploading: 0,
            error: '',
            errorAlert: false,
            success: '',
            successAlert: false,
            selectedEndpoints: [],
            endpointHeaders: [
                { text: $gettext('System'), value: 'title' }
            ]
        }
    },
    computed: {
        stateControl() {
            const c = this.$store.state.roomcontrol.controls[this.control.id]
            if (!c) { // e.g. just after delete
                return {
                    panels: [],
                    macros: [],
                }
            }

            const panels = []
            const macros = []

            ;(c.files || []).forEach(f => {
                const ext = f.name.split('.').pop()
                if (ext.toLowerCase() === 'xml') {
                    panels.push(f)
                }
                if (ext.toLowerCase() === 'js') {
                    macros.push(f)
                }
            })

            return {
                ...c,
                panels,
                macros,
                isPanel: panels.length,
                isMacro: macros.length,
                urlExport: c.url_export,
                created: timestamp(c.ts_created),
            }
        },
        formDisabled() {
            if (this.loading || this.uploading) {
                return true
            }

            return false
        },
        matchedEndpoints() {
            return (this.control.endpoints || []).map(e => {
                return this.$store.state.endpoint.endpoints[e]
            })
        }
    },
    mounted() {
        this.form = {
            ...this.form,
            title: this.control.title,
            description: this.control.description
        }
        this.$store.dispatch('endpoint/getEndpoints')
    },
    methods: {
        resetFormStatus(loading=true) {
            this.error = ''
            this.errorAlert = false
            this.success = ''
            this.successAlert = false
            this.loading = loading
        },
        successMessage(message) {
            this.loading = false
            this.uploading = 0
            this.success = message
            this.successAlert = true
        },
        errorMessage(message) {
            this.loading = false
            this.uploading = 0
            this.error = message
            this.errorAlert = true
        },
        deleteControl() {
            this.resetFormStatus()

            return this.$store
                .dispatch('roomcontrol/deleteControl', this.control.id).then(() => {
                    this.$emit('close')
                    this.$emit('removed')
                })
                .catch(e => {
                    this.errorMessage(e.toString())
                })
        },
        unlinkFile(file) {
            this.resetFormStatus()

            this.$store
                .dispatch('roomcontrol/deleteControlFile', file.id)
                .then(() => this.successMessage($gettextInterpolate($gettext('%{ name } är nu borttagen.'), { name: file.name })))
                .catch(e => this.errorMessage(e.toString()))
        },
        updateControl() {
            this.resetFormStatus()

            const updateFormData = new FormData()
            updateFormData.append('title', this.form.title)
            updateFormData.append('description', this.form.description)

            return this.$store
                .dispatch('roomcontrol/updateControl', {
                    id: this.control.id,
                    data: updateFormData,
                })
                .then(() => this.successMessage($gettext('Uppdatering klar.')))
                .catch(e => this.errorMessage(e.toString()))
        },
        uploadFiles() {
            this.resetFormStatus()

            const updateFormData = new FormData()
            if (this.form.files) {
                for (const file of this.form.files) {
                    updateFormData.append('files', file, file.name)
                }
            }

            const progress = percent => {
                this.uploading = percent * 100
            }

            return this.$store
                .dispatch('roomcontrol/addControlFiles', {
                    id: this.control.id,
                    data: updateFormData,
                    progress
                })
                .then(() => {
                    this.successMessage($gettext('Uppladdning lyckades.'))
                    this.form.files = []
                })
                .catch(e => this.errorMessage(e.toString()))
        },

        async provisionEndpoints(endpoints) {
            const ids = endpoints.map(e => e.id || e)

            this.successAlert = this.success = false
            await this.$store.dispatch('endpoint/provision', { endpoints: ids, room_controls: [this.control.id] })
            this.success = $gettext('Åtgärden har lagts till i kön')
            this.successAlert = true
            // eslint-disable-next-line
            this.control.endpoints = [...new Set([...this.control.endpoints, ...ids]).values()] // FIXME event
        },
        deprovisionEndpoints() {
            const ids = this.selectedEndpoints.map(e => e.id)
            this.successAlert = this.success = false
            this.$store.dispatch('endpoint/provision', { endpoints: ids, room_controls: [this.control.id], room_controls_delete_operation: '1' })
            this.success = $gettext('Åtgärden har lagts till i kön')
            this.successAlert = true
        }
    }
}
</script>
