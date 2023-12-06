<template>
    <div>
        <EndpointGrid
            ref="grid"
            v-model="selected"
            :table-footer-left="selected.length > 0"
            :show-empty="false"
            enable-navigation-history
            checkbox
            @loading="emitter.emit('loading', true)"
            @refreshed="refreshed"
        />

        <TableActionDialog
            :count="selected.length"
            :title="$gettext('Val för samtliga valda system')"
        >
            <v-btn
                class="mb-3"
                block
                small
                depressed
                color="primary"
                @click="updateDialog = true"
            >
                <translate>Redigera</translate>
            </v-btn>

            <v-btn
                class="mb-3"
                block
                small
                depressed
                color="primary"
                @click="provisionDialog = true"
            >
                <translate>Provisionera</translate>
            </v-btn>

            <v-btn
                class="mb-3"
                block
                small
                depressed
                color="primary"
                @click="exportExcel"
            >
                <translate>Exportera till excel</translate>
            </v-btn>

            <v-btn-confirm
                block
                small
                dark
                depressed
                color="red"
                @click="bulkDelete"
            >
                <translate>Ta bort alla valda</translate>
            </v-btn-confirm>
        </TableActionDialog>

        <v-dialog
            v-model="addDialog"
            scrollable
            :max-width="520"
        >
            <EndpointForm @complete="addEndpointComplete" />
        </v-dialog>

        <v-dialog
            v-if="addDoneDialog"
            v-model="addDoneDialog"
            scrollable
            max-width="400"
        >
            <v-card>
                <v-card-title><translate>Systemet är sparat i Rooms</translate></v-card-title>
                <v-divider />
                <v-card-text class="pt-6">
                    <v-alert
                        v-if="addedEndpoint && addedEndpoint.status_code && addedEndpoint.status_code < 0"
                        type="warning"
                        class="my-2"
                    >
                        <p v-translate>
                            Systemet kunde inte aktiveras just nu
                        </p>
                        <EndpointStatus
                            :endpoint="addedEndpoint"
                            text
                        />
                        <p>
                            <router-link :to="{ name: 'endpoint_details', params: { id: addedEndpoint.id }, query: { edit: '' }}">
                                <translate>Fortsätt redigera</translate>
                            </router-link>
                        </p>
                    </v-alert>
                    <translate>Fortsätt till provisioneringsvyn för att slutföra installationen och skriva ev. ändringar till systemet</translate>
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-btn
                        color="primary"
                        :to="{
                            name: 'endpoint_provision',
                            params: {
                                id: addedEndpoint ? addedEndpoint.id : null,
                            },
                        }"
                    >
                        <translate>Fortsätt</translate>
                    </v-btn>
                    <v-spacer />
                    <v-btn
                        v-close-dialog
                        text
                        color="red"
                    >
                        <translate>Avbryt</translate>
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>


        <v-dialog
            v-model="addBulk"
            scrollable
            :max-width="1500"
        >
            <EndpointBulkForm @complete="addEndpointBulkComplete" />
        </v-dialog>

        <v-dialog
            v-model="updateDialog"
            scrollable
            :max-width="640"
        >
            <EndpointBulkUpdateForm
                v-if="updateDialog"
                dialog
                :endpoints="selected"
                @update="reloadEndpoints"
                @cancel="updateDialog = false"
            />
        </v-dialog>

        <v-dialog
            v-model="provisionDialog"
            scrollable
            :max-width="1080"
        >
            <EndpointProvision
                v-if="selected.length"
                :id="selected[0]"
                :multiple="selected.length > 1 ? selected : []"
                dialog
            />
        </v-dialog>
    </div>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'

import EndpointGrid from '@/vue/components/epm/endpoint/EndpointGrid'
import EndpointProvision from '@/vue/views/epm/endpoint/single/EndpointProvision'
import EndpointBulkUpdateForm from '@/vue/components/epm/endpoint/EndpointBulkUpdateForm'
import VBtnConfirm from '@/vue/components/VBtnConfirm'
import TableActionDialog from '@/vue/components/TableActionDialog'
import EndpointBulkForm from '@/vue/components/epm/endpoint/EndpointBulkForm'
import EndpointForm from '@/vue/components/epm/endpoint/EndpointForm'

import EndpointsMixin from '@/vue/views/epm/mixins/EndpointsMixin'

export default {
    components: {EndpointBulkForm, EndpointForm, VBtnConfirm, TableActionDialog, EndpointProvision, EndpointBulkUpdateForm, EndpointGrid },
    mixins: [EndpointsMixin],
    data() {
        return {
            emitter: new GlobalEventBus(this),
            selected: [],
            provisionDialog: false,
            updateDialog: false,
            addDialog: false,
            addDoneDialog: false,
            addedEndpoint: null,
            addBulk: false,
        }
    },
    watch: {
        '$route.fullPath'() {
            this.emitter = new GlobalEventBus(this)
        }
    },
    mounted() {
        this.emitter.on('add', () => (this.addDialog = true))
        this.emitter.on('add-bulk', () => (this.addBulk = true))
        this.emitter.on('refresh', () => {
            this.emitter.emit('loading', true)
            this.$refs.grid.reloadEndpoints()
        })

        this.$store.commit('site/setBreadCrumb', [{ title: this.$ngettext('System', 'System', 2) }])
    },
    methods: {
        addEndpointComplete(endpoint) {
            this.addedEndpoint = endpoint
            this.addDialog = false
            this.addDoneDialog = true
        },
        addEndpointBulkComplete(endpoints) {
            this.addBulk = false
            return this.reloadEndpoints().then(() => {
                this.selected = endpoints.map(e => e.id)
                this.provisionDialog = true
            })
        },
        exportExcel() {
            return this.$store.dispatch('endpoint/excelExportDownload', this.selected)
        },
        bulkDelete() {
            return this.$store.dispatch('endpoint/deleteBulk', this.selected).then(() => {
                this.selected = []
            })
        },
        refreshed() {
            this.emitter.emit('loading', false)
        }
    },
}
</script>
