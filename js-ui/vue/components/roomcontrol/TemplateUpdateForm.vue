<template>
    <v-card>
        <v-card-title class="headline mb-2">
            {{ template.title }}
        </v-card-title>
        <v-card-subtitle><translate>Skapad</translate> {{ created }}</v-card-subtitle>
        <v-divider />
        <v-tabs
            v-model="tab"
            background-color="transparent"
            color="primary"
            grow
        >
            <v-tab key="content">
                <translate>Innehåll</translate>
            </v-tab>
            <v-tab key="controls">
                <translate>Kontroller</translate>
            </v-tab>
            <v-tab key="endpoints">
                <translate>System</translate>
            </v-tab>
            <v-tab key="delete">
                <translate>Ta bort</translate>
            </v-tab>
        </v-tabs>
        <v-divider />
        <v-tabs-items v-model="tab">
            <v-tab-item key="content">
                <v-card-text>
                    <v-text-field
                        v-model="form.title"
                        :label="$gettext('Rubrik')"
                        required
                    />
                    <v-textarea
                        v-model="form.description"
                        :hide-details="true"
                        outlined
                        :label="$gettext('Beskrivning')"
                    />
                </v-card-text>
            </v-tab-item>
            <v-tab-item key="controls">
                <v-card-text>
                    <v-autocomplete
                        v-model="form.controls"
                        :items="controls"
                        chips
                        small-chips
                        :label="$gettext('Valda kontroller')"
                        multiple
                    >
                        <template v-slot:selection="data">
                            <v-chip
                                v-bind="data.attrs"
                                :input-value="data.selected"
                                close
                                @click="data.select"
                                @click:close="remove(data.item)"
                            >
                                {{ data.item.text }}
                            </v-chip>
                        </template>
                    </v-autocomplete>
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
                        <translate>Denna mall är inte installerad i något system</translate>
                    </v-alert>
                </v-card-text>
            </v-tab-item>
            <v-tab-item key="delete">
                <v-card-text class="text-center">
                    <v-btn
                        depressed
                        color="red"
                        dark
                        @click="deleteTemplate(template.id)"
                    >
                        <span><translate>Ta bort</translate> {{ template.title }}</span>
                    </v-btn>
                </v-card-text>
            </v-tab-item>
        </v-tabs-items>

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
        <v-divider v-if="!errorAlert" />

        <v-card-actions>
            <v-btn
                v-if="tab < 2"
                color="primary"
                :disabled="loading"
                @click="updateTemplate"
            >
                <translate>Uppdatera</translate>
            </v-btn>
            <span v-else-if="tab === 2">
                <EndpointPicker
                    v-if="!selectedEndpoints.length"
                    :button-text="$gettext('Lägg till')"
                    :action-button-text="$gettext('Installera i system')"
                    button
                    @confirm="provisionEndpoints($event)"
                />
                <!-- TODO: not working
                    <template v-slot:default="{ on }">
                        <v-btn color="primary" v-on="on">
                            <translate>Lägg till</translate>
                        </v-btn>
                    </template>
                </EndpointPicker>
                -->
                <v-btn
                    v-if="selectedEndpoints.length"
                    color="primary"
                    class="ml-3"
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
import moment from 'moment'

import { $gettext } from '@/vue/helpers/translate'

import EndpointPicker from '@/vue/components/epm/endpoint/EndpointPicker'

export default {
    components: { EndpointPicker },
    props: {
        template: { type: Object, required: true },
    },
    data() {
        return {
            form: {
                title: '',
                description: '',
                controls: []
            },
            tab: 0,
            error: '',
            errorAlert: null,
            success: '',
            successAlert: false,
            loading: false,
            selectedEndpoints: [],
            endpointHeaders: [
                { text: $gettext('System'), value: 'title' }
            ]
        }
    },
    computed: {
        created() {
            return moment(this.template.ts_created).format('YYYY-MM-DD HH:mm:ss')
        },
        controls() {
            return Object.values(this.$store.state.roomcontrol.controls).map(control => {
                return {
                    text: control.title,
                    value: control.id
                }
            })
        },
        matchedEndpoints() {
            return this.template.endpoints.map(e => {
                return this.$store.state.endpoint.endpoints[e]
            })
        }
    },
    mounted() {
        this.form = {
            title: this.template.title,
            description: this.template.description,
            controls: this.template.controls.map(c => c.id)
        }
        this.$store.dispatch('endpoint/getEndpoints')
    },
    methods: {
        filter (item, query, text) {
            if (!query) {
                return true
            }

            return text
                .toLowerCase()
                .indexOf(query.toString().toLowerCase()) > -1
        },
        remove (item) {
            const index = this.form.controls.indexOf(item.value)
            if (index >= 0) this.form.controls.splice(index, 1)
        },
        resetFormStatus() {
            this.error = ''
            this.errorAlert = false
            this.success = ''
            this.successAlert = false
            this.loading = true
        },
        errorMessage(message) {
            this.loading = false
            this.error = message
            this.errorAlert = true
        },
        deleteTemplate() {
            this.resetFormStatus()

            return this.$store
                .dispatch('roomcontrol/deleteTemplate', this.template.id)
                .then(() => {
                    this.$emit('close')
                })
                .catch(e => {
                    this.errorMessage(e.toString())
                })
        },
        updateTemplate() {
            this.resetFormStatus()

            const data = {
                ...this.form
            }

            this.$store.dispatch('roomcontrol/updateTemplate', { id: this.template.id, data }).then(() => {
                this.loading = false
                this.$emit('created')
            }).then(() => {
                this.success = $gettext('Mallen är nu uppdaterad')
                this.successAlert = true
            }).catch(e => {
                this.errorMessage(e.toString())
            })
        },

        async provisionEndpoints(endpoints) {
            const ids = endpoints.map(e => e.id || e)

            this.successAlert = this.success = false
            await this.$store.dispatch('endpoint/provision', { endpoints: ids, room_control_templates: [this.template.id] })
            this.success = $gettext('Åtgärden har lagts till i kön')
            this.successAlert = true
            // eslint-disable-next-line
            this.template.endpoints = [...new Set([...this.template.endpoints, ...ids]).values()]  // FIXME event
        },
        async deprovisionEndpoints() {
            const ids = this.selectedEndpoints.map(e => e.id)
            this.successAlert = this.success = false
            await this.$store.dispatch('endpoint/provision', { endpoints: ids, room_control_templates: [this.template.id], room_controls_delete_operation: '1' })
            this.success = $gettext('Åtgärden har lagts till i kön')
            this.successAlert = true
        }
    }
}
</script>
