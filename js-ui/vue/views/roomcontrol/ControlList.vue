<template>
    <Page
        icon="mdi-apps-box"
        :title="$gettext('Paneler och makron')"
        :actions="pageActions"
    >
        <template v-slot:search>
            <v-form @submit.prevent="loadControls()">
                <div class="d-flex align-center">
                    <v-text-field
                        v-if="tab === 0"
                        v-model="searchControl"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök rumskontroller') + '...'"
                        outlined
                        dense
                        class="mr-4"
                    />
                    <v-text-field
                        v-else
                        v-model="searchTemplate"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök samlingar') + '...'"
                        outlined
                        dense
                        class="mr-4"
                    />
                    <v-btn
                        color="primary"
                        :loading="loading"
                        class="mr-md-4"
                        @click="loadControls"
                    >
                        <v-icon>mdi-refresh</v-icon>
                    </v-btn>
                </div>
            </v-form>
        </template>
        <template v-slot:tabs>
            <v-tabs
                v-model="tab"
                color="primary"
            >
                <v-tab key="controls">
                    <translate>Rumskontroller</translate>
                    <v-avatar
                        size="24"
                        :color="tab === 0 ? 'primary' : 'grey'"
                        class="white--text ml-2"
                    >
                        {{ Object.keys(controls).length }}
                    </v-avatar>
                </v-tab>
                <v-tab
                    key="templates"
                    :disabled="!templates.length"
                    :title="$gettext('Markera en eller flera kontroller för att skapa samlingar')"
                >
                    <translate>Samlingar</translate>
                    <v-avatar
                        size="24"
                        :color="tab === 1 ? 'primary' : 'grey'"
                        class="white--text ml-2"
                    >
                        {{ templates.length }}
                    </v-avatar>
                </v-tab>
            </v-tabs>
        </template>
        <template v-slot:content>
            <div class="pt-3 pb-6">
                <v-row v-if="loading">
                    <v-col
                        v-for="item in 10"
                        :key="item"
                        cols="12"
                        sm="6"
                        md="4"
                        lg="3"
                    >
                        <v-skeleton-loader
                            class="mx-auto"
                            max-width="300"
                            type="card"
                        />
                    </v-col>
                </v-row>

                <template v-if="tab === 0">
                    <v-card v-if="!Object.values(controls).length">
                        <v-card-text class="text-center">
                            <translate>Just nu finns inga kontroller med paneler eller makron.</translate>
                            <v-btn
                                color="primary"
                                class="mx-3"
                                @click="showCreateControlDialog"
                            >
                                <translate>Lägg till</translate>
                            </v-btn>
                        </v-card-text>
                    </v-card>
                    <v-card v-else-if="!filtredControls.length">
                        <v-card-text>
                            <translate>Hittar inga rumskontroller på din filtrering.</translate>
                        </v-card-text>
                    </v-card>

                    <v-row v-else>
                        <v-col
                            v-for="control in filtredControls"
                            :key="control.id"
                            cols="12"
                            sm="6"
                            md="4"
                            lg="3"
                        >
                            <v-card
                                elevation="1"
                                class="pt-0 d-flex flex-column flex-grow-1 align-self-stretch"
                            >
                                <v-progress-linear
                                    color="pink"
                                    :active="true"
                                    :value="100"
                                />

                                <v-card-title>
                                    <v-tooltip top>
                                        <template v-slot:activator="{ on }">
                                            <v-checkbox
                                                v-model="selectedControlIds[control.id]"
                                                dense
                                                :hide-details="true"
                                                :label="control.title"
                                                class="ma-0 pa-0"
                                                v-on="on"
                                            />
                                        </template>
                                        <span v-translate>Välj en eller flera kontroller för att exportera eller skapa samling.</span>
                                    </v-tooltip>
                                </v-card-title>
                                <v-card-subtitle class="mt-2">
                                    {{ control.description }}
                                </v-card-subtitle>
                                <v-spacer />
                                <v-list-item
                                    class="grey lighten-4 flex-grow-0 flex-shrink-1"
                                    style="flex-basis: auto;"
                                >
                                    <v-card-subtitle class="px-0 d-flex">
                                        <v-chip
                                            v-if="control.isPanel"
                                            color="grey darken-4"
                                            dark
                                            class="mr-1 px-2"
                                            small
                                        >
                                            <translate>Panel</translate>
                                        </v-chip>
                                        <span
                                            v-if="control.isPanel && control.isMacro"
                                            class="mr-1"
                                        >+</span>
                                        <v-chip
                                            v-if="control.isMacro"
                                            color="grey darken-4"
                                            class="px-2"
                                            dark
                                            small
                                        >
                                            <translate>Makro</translate>
                                        </v-chip>
                                    </v-card-subtitle>
                                    <v-spacer />
                                    <v-chip
                                        class="ml-auto px-2"
                                        outlined
                                        small
                                    >
                                        <strong class="mr-1">{{ control.files.length }}</strong>
                                        <span>{{ control.files.length > 0 ? 'filer' : 'fil' }}</span>
                                    </v-chip>
                                </v-list-item>

                                <v-divider />

                                <v-card-actions
                                    dark
                                    class="white"
                                >
                                    <v-btn
                                        color="primary"
                                        icon
                                        @click="showUpdateControlDialog(control)"
                                    >
                                        <v-icon>mdi-pencil</v-icon>
                                    </v-btn>
                                    <v-btn
                                        color="primary"
                                        icon
                                        @click="showExportControlDialog(control)"
                                    >
                                        <v-icon>mdi-download</v-icon>
                                    </v-btn>
                                </v-card-actions>
                            </v-card>
                        </v-col>
                    </v-row>
                </template>
                <RoomControlTemplates
                    v-if="tab === 1"
                    :templates="filteredTemplates"
                />
            </div>

            <TableActionDialog
                :count="tab === 0 && selectedControls.length > 1 ? selectedControls.length : 0"
                :title="$gettext('Val för samtliga valda rumskontroller')"
            >
                <v-card
                    outlined
                    class="mb-4"
                >
                    <v-card-text>
                        <v-btn
                            color="primary"
                            block
                            small
                            depressed
                            @click.stop="showCreateTemplateDialog"
                        >
                            <translate>Skapa samling</translate>
                        </v-btn>
                    </v-card-text>
                </v-card>
                <v-card outlined>
                    <v-card-text>
                        <v-btn
                            color="primary"
                            block
                            small
                            depressed
                            @click.stop="showBulkExportControlsDialog"
                        >
                            <translate>Ladda ner</translate>
                        </v-btn>
                    </v-card-text>
                </v-card>
            </TableActionDialog>

            <v-dialog
                v-model="dialogs.createControl"
                scrollable
                max-width="420"
            >
                <ControlCreateForm
                    v-if="dialogs.createControl"
                    @close="dialogs.createControl = false"
                    @created="dialogs.createControl = false"
                />
            </v-dialog>
            <v-dialog
                v-model="dialogs.updateControl"
                scrollable
                max-width="520"
            >
                <ControlUpdateForm
                    v-if="dialogs.updateControl"
                    :control="dialogControl"
                    @close="dialogs.updateControl = false"
                    @removed="selectedControlIds = {}"
                />
            </v-dialog>
            <v-dialog
                v-model="dialogs.exportControl"
                scrollable
                max-width="520"
            >
                <ControlExportForm
                    v-if="dialogs.exportControl"
                    :control="dialogControl"
                    @close="dialogs.exportControl = false"
                    @exported="dialogs.exportControl = false"
                />
            </v-dialog>
            <v-dialog
                v-model="dialogs.bulkExportControls"
                max-width="520"
            >
                <ControlBulkExportForm
                    v-if="dialogs.bulkExportControls"
                    :controls="selectedControls"
                    @close="dialogs.bulkExportControls = false"
                />
            </v-dialog>
            <v-dialog
                v-model="dialogs.createTemplate"
                max-width="520"
            >
                <TemplateCreateForm
                    v-if="dialogs.createTemplate"
                    :controls="selectedControls"
                    @close="dialogs.createTemplate = false"
                    @created="templateCreated"
                />
            </v-dialog>
        </template>
    </Page>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'

import Page from '@/vue/views/layout/Page'
import RoomControlTemplates from './RoomControlTemplates'

import ControlCreateForm from '@/vue/components/roomcontrol/ControlCreateForm'
import ControlUpdateForm from '@/vue/components/roomcontrol/ControlUpdateForm'
import ControlExportForm from '@/vue/components/roomcontrol/ControlExportForm'
import ControlBulkExportForm from '@/vue/components/roomcontrol/ControlBulkExportForm'
import TableActionDialog from '@/vue/components/TableActionDialog'
import TemplateCreateForm from '@/vue/components/roomcontrol/TemplateCreateForm'

export default {
    components: {
        Page,
        RoomControlTemplates,
        ControlCreateForm,
        ControlUpdateForm,
        ControlExportForm,
        ControlBulkExportForm,
        TemplateCreateForm,
        TableActionDialog
    },
    data() {
        return {
            emitter: new GlobalEventBus(this),
            dialogs: {
                createControl: false,
                updateControl: false,
                exportControl: false,
                createTemplate: false,
                bulkExportControls: false,
            },
            dialogControl: null,
            selectedControlIds: {},
            tab: 0,

            loading: true,

            searchControl: '',
            searchTemplate: '',

            filterDialog: false
        }
    },
    computed: {
        pageActions() {
            return [
                {
                    icon: 'mdi-plus',
                    click: () => this.showCreateControlDialog()
                },
                {
                    type: 'refresh',
                    click: () => this.loadControls()
                }
            ]
        },
        filtredControls() {
            return Object.values(this.controls).filter(c => {
                return JSON.stringify(c)
                    .toLowerCase()
                    .indexOf(this.searchControl.toLowerCase()) != -1
            })
        },
        controls() {
            return this.$store.state.roomcontrol.controls
        },
        selectedControls() {
            const controls = this.$store.state.roomcontrol.controls
            return Object.entries(this.selectedControlIds).filter(c => c[1] === true).map(c => {
                return controls[c[0]]
            })
        },
        filteredTemplates() {
            return this.templates.filter(t => {
                return JSON.stringify(t)
                    .toLowerCase()
                    .indexOf(this.searchTemplate.toLowerCase()) != -1
            })
        },
        templates() {
            const controls = this.$store.state.roomcontrol.controls

            if (!Object.keys(controls).length) {
                return Object.entries(this.$store.state.roomcontrol.templates)
            }

            return Object.entries(this.$store.state.roomcontrol.templates).map(template => {
                let fileCount = 0
                return {
                    ...template[1],
                    controls: template[1].controls.map(cid => {
                        const control = controls[cid]
                        fileCount += control.files.length
                        return control
                    }),
                    fileCount
                }
            })
        },
    },
    watch: {
        searchControl() {
            this.selectedControlIds = {}
        }
    },
    mounted() {
        this.loadControls()
    },
    methods: {
        resetFilters() {
            return false
        },
        loadControls() {
            this.loading = true
            this.emitter.emit('loading', true)

            return Promise.all([
                this.$store.dispatch('roomcontrol/getControls'),
                this.$store.dispatch('roomcontrol/getTemplates'),
            ]).then(() => {
                this.loading = false
                this.emitter.emit('loading', false)
            })
        },

        showCreateControlDialog() {
            this.dialogs.createControl = true
        },
        showUpdateControlDialog(control) {
            this.dialogControl = control
            this.dialogs.updateControl = true
        },
        showExportControlDialog(control) {
            this.dialogControl = control
            this.dialogs.exportControl = true
        },
        showBulkExportControlsDialog() {
            this.dialogs.bulkExportControls = true
        },

        showCreateTemplateDialog() {
            this.dialogs.createTemplate = true
        },
        templateCreated() {
            this.dialogs.createTemplate = false
            this.tab = 1
        }
    },
}
</script>
