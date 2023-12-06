<template>
    <div>
        <PageHeader
            v-if="!hideTitle"
            icon="mdi-download-network"
        >
            <template slot="title">
                <h3><translate>Firmware</translate></h3>
            </template>
            <template slot="actions">
                <v-btn
                    class="ml-2"
                    fab
                    small
                    color="primary"
                    @click="uploadDialog = true"
                >
                    <v-icon>mdi-plus</v-icon>
                </v-btn>
            </template>
        </PageHeader>
        <PageSearchFilter>
            <template slot="search">
                <v-form @submit.prevent="loadData()">
                    <div class="d-flex align-center">
                        <v-text-field
                            v-model="search"
                            hide-details
                            prepend-inner-icon="mdi-magnify"
                            :placeholder="$gettext('Sök firmware') + '...'"
                            outlined
                            dense
                            class="mr-4"
                        />
                        <v-btn
                            color="primary"
                            :loading="loading"
                            class="mr-md-4"
                            @click="loadData"
                        >
                            <v-icon>mdi-refresh</v-icon>
                        </v-btn>
                    </div>
                </v-form>
            </template>
            <template
                v-if="!endpoint"
                slot="filter"
            >
                <VBtnFilter
                    :disabled="loading"
                    :filters="filter"
                    :show-remove-all="true"
                    @click="filterDialog = true"
                    @removeFilter="removeFilter"
                    @removeAllFilters="removeAllFilters"
                />
            </template>
        </PageSearchFilter>

        <v-data-table
            :headers="activeHeaders"
            :items="filteredItems"
            :loading="loading"
        >
            <template v-slot:item.is_global="{ item }">
                <v-icon v-if="item.is_global">
                    mdi-check
                </v-icon>
            </template>
            <template v-slot:item.action="{ item }">
                <v-dialog
                    v-if="!endpoint || !endpoint.id"
                    :max-width="320"
                >
                    <template v-slot:activator="{ on }">
                        <v-btn
                            :title="$gettext('Kopiera')"
                            icon
                            v-on="on"
                        >
                            <v-icon>mdi-content-copy</v-icon>
                        </v-btn>
                    </template>
                    <EndpointFirmwareCopyForm
                        :firmware="item"
                        :available-products="availableProducts"
                        @done="loadData"
                    />
                </v-dialog>
                <v-btn
                    :title="$gettext('Ladda ner')"
                    icon
                    @click="downloadFirmware(item)"
                >
                    <v-icon>mdi-download</v-icon>
                </v-btn>
                <v-btn-confirm
                    :title="$gettext('Ta bort')"
                    :dialog-text="item.removeText"
                    icon
                    @click="deleteFirmware(item)"
                >
                    <v-icon>mdi-delete</v-icon>
                </v-btn-confirm>

                <v-dialog v-if="endpoint && endpoint.id">
                    <template v-slot:activator="{ on }">
                        <v-btn
                            :title="$gettext('Installera')"
                            icon
                            v-on="on"
                        >
                            <v-icon>
                                mdi-cube-send
                            </v-icon>
                        </v-btn>
                    </template>
                    <v-card>
                        <v-card-title><translate>Installera firmware</translate></v-card-title>
                        <v-card-text>
                            <v-checkbox
                                v-model="forceInstall"
                                :label="$gettext('Tvinga installation utan att fråga användare')"
                            />
                            <v-checkbox
                                v-model="scheduleNight"
                                :label="$gettext('Schemalägg till natten')"
                            />

                            <v-btn
                                class="mr-2"
                                color="primary"
                                @click="installFirmware($event, item, forceInstall, scheduleNight ? 'night' : null)"
                            >
                                <translate>Installera</translate>
                            </v-btn>
                            <v-btn
                                v-close-dialog
                                outlined
                            >
                                <translate>Avbryt</translate>
                            </v-btn>
                        </v-card-text>
                    </v-card>
                </v-dialog>
            </template>
            <template v-slot:item.ts_created="{ item }">
                {{ item.ts_created|timestamp }}
            </template>
        </v-data-table>

        <v-dialog
            v-model="uploadDialog"
            scrollable
            max-width="420"
        >
            <EndpointFirmwareForm
                :endpoint="endpoint"
                @done="uploadDialog = false"
            />
        </v-dialog>

        <v-dialog
            v-model="filterDialog"
            scrollable
            max-width="320"
        >
            <v-card>
                <v-card-title><translate>Filtrera</translate></v-card-title>
                <v-divider />
                <v-card-text>
                    <TreeView
                        v-if="$vuetify.breakpoint.smAndUp"
                        v-model="activeFilters.model"
                        style="margin:0 -24px;"
                        :items="items.length ? availableProductsMerged : []"
                        show
                    />
                    <v-select
                        v-else
                        v-model="activeFilters.model"
                        :label="$gettext('Filtrera på produkt')"
                        item-text="title"
                        :items="availableProducts"
                        multiple
                    />
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-btn
                        color="primary"
                        @click="applyFilters"
                    >
                        <translate>Tillämpa</translate>
                    </v-btn>
                    <v-spacer />
                    <v-btn
                        v-close-dialog
                        text
                        color="red"
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
    </div>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import PageHeader from '@/vue/views/layout/page/PageHeader'
import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'

import VBtnConfirm from '@/vue/components/VBtnConfirm'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'

import TreeView from '@/vue/components/tree/TreeView'
import { closeDialog } from '@/vue/helpers/dialog'
import EndpointFirmwareForm from '@/vue/components/epm/endpoint/EndpointFirmwareForm'
import EndpointFirmwareCopyForm from '@/vue/components/epm/endpoint/EndpointFirmwareCopyForm'

export default {
    components: {
        EndpointFirmwareCopyForm,
        EndpointFirmwareForm,
        PageHeader,
        PageSearchFilter,
        TreeView,
        VBtnConfirm,
        VBtnFilter,
    },
    props: {
        endpoint: { type: Object, required: false, default: null },
        hideTitle: { type: Boolean, default: false },
        flat: { type: Boolean, default: false },
    },
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            loading: true,
            forceInstall: false,
            scheduleNight: false,
            uploadDialog: false,
            availableProducts: [],
            filters: {
                model: [],
            },
            filterDialog: false,
            activeFilters: {
                model: []
            },
            search: '',
            headers: [
                {
                    text: $gettext('Version'),
                    value: 'version',
                },
                {
                    text: $gettext('Filnamn'),
                    value: 'orig_file_name',
                },
                ...(this.endpoint
                    ? []
                    : [
                        {
                            text: $gettext('Produkt'),
                            value: 'model',
                        },
                    ]),
                {
                    text: $gettext('Uppladdad'),
                    value: 'ts_created',
                },
                { text: '', value: 'action', align: 'end', sortable: false },
            ],
            createdSnackbar: null,
        }
    },
    computed: {
        availableProductsMerged() {
            const models = []
            this.items.forEach(f => {
                if (!models.find(m => m.id === f.model)) {
                    models.push({
                        id: f.model,
                        title: f.model
                    })
                }
            })

            return models.filter(f => !!f.id)
        },
        hasGlobalFirmware() {
            return this.filteredItems.some(f => f.is_global)
        },
        activeHeaders() {
            if (this.hasGlobalFirmware) {
                return [this.headers[0], { text: $gettext('Global'), value: 'is_global' }, ...this.headers.slice(1)]
            }
            return this.headers
        },
        filter() {
            return this.filters.model.map(f => {
                return {
                    title: $gettext('Produkt'),
                    value: f
                }
            })
        },
        items() {
            return Object.values(this.$store.state.endpoint.firmwares || {}).map(f => {
                return {
                    ...f,
                    removeText: f.is_global ?
                        $gettext('Är du säker? Denna firmware visas för alla kunder') :
                        $gettext('Är du säker?')
                }
            })
        },
        filteredItems() {
            const models = this.endpoint ? [this.endpoint.product_name] : this.filters.model
            let items = this.items

            if (models.length) {
                items = items.filter(f => models.includes(f.model))
            }
            if (this.search) {
                items = items.filter(f => {
                    return JSON.stringify(f)
                        .toLowerCase()
                        .indexOf(this.search.toLowerCase()) != -1
                })
            }

            return items
        },
    },
    mounted() {
        return Promise.all([this.loadData(), this.loadProducts()]).then(() => {
            this.loading = false
        })
    },
    methods: {
        loadProducts() {
            return this.$store.dispatch('endpoint/getFilters').then(values => {
                this.availableProducts = values.product_name
                    .map(p => ({ id: p, title: p }))
                    .filter(p => !!p.title)
            })
        },
        removeAllFilters() {
            this.activeFilters.model = []

            this.applyFilters()
        },
        applyFilters() {
            this.filterDialog = false
            this.filters.model = [ ...this.activeFilters.model ]
        },
        removeFilter({ index }) {
            this.$delete(this.activeFilters.model, index)
            this.applyFilters()
        },
        loadFirmwares() {
            return this.$store.dispatch('endpoint/getFirmwares').then(() => {
                this.loading = false
                this.$emit('refreshed')

            })
        },
        downloadFirmware(item) {
            return this.$store.dispatch('endpoint/downloadFirmware', item.id)
        },
        installFirmware(ev, item, force=false, constraint=undefined) {
            return this.$store
                .dispatch('endpoint/installFirmware', {
                    endpointId: this.endpoint.id,
                    firmwareId: item.id,
                    force,
                    constraint,
                })
                .then(() => {
                    this.uploadDialog = false
                    closeDialog(ev.target)
                })
        },
        deleteFirmware(item) {
            this.loading = true
            return this.$store
                .dispatch('endpoint/deleteFirmware', item.id)
                .then(() => {
                    return this.loadFirmwares()
                })
                .then(() => {
                    this.loading = false
                })
        },
        loadData() {
            this.loading = true
            return this.loadFirmwares()
        }
    },
}
</script>
