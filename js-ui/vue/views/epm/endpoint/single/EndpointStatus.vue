<template>
    <div>
        <PageSearchFilter>
            <template v-slot:search>
                <v-text-field
                    v-model="text_filter"
                    hide-details
                    prepend-inner-icon="mdi-magnify"
                    :placeholder="$gettext('Sök status') + '...'"
                    outlined
                    dense
                />
            </template>
            <template v-slot:filter>
                <v-btn
                    v-if="!reportActive"
                    color="primary"
                    small
                    @click="reportActive = !reportActive"
                >
                    <v-icon left>
                        mdi-file-document-box
                    </v-icon>
                    <span><translate>Skapa rapport</translate></span>
                </v-btn>

                <p
                    v-if="reportActive && !rootElements.length"
                    class="my-0"
                >
                    <translate>Välj en eller fler status</translate>
                </p>
                <div
                    v-else-if="reportActive && !!rootElements.length"
                    class="text-right"
                >
                    <v-btn
                        color="primary"
                        small
                        :disabled="!rootElements.length"
                        @click="reportDialog = true"
                    >
                        <v-icon left>
                            mdi-dns
                        </v-icon>
                        <translate>Välj system</translate>
                    </v-btn>
                </div>

                <v-btn
                    v-if="reportActive"
                    color="error"
                    class="ml-3"
                    fab
                    small
                    @click="reportActive = !reportActive"
                >
                    <v-icon>mdi-window-close</v-icon>
                </v-btn>
            </template>
        </PageSearchFilter>
        <v-divider />

        <TabLoaderIndicator v-if="loading" />
        <div v-else>
            <v-card
                v-if="error"
                class="my-4"
            >
                <v-card-text>
                    <v-alert type="error">
                        <strong><translate>Ett fel uppstod.</translate></strong><br>
                        <span
                            v-if="endpoint.has_direct_connection"
                            v-translate
                        >Kontrollera din anslutning och försök igen</span>
                        <span
                            v-else
                            v-translate
                        >Aktiv anslutning saknas, och ingen cachad data hittades</span>
                    </v-alert>
                    <v-textarea
                        readonly
                        light
                        class="mt-4"
                        :label="$gettext('Felinformation')"
                        :value="error"
                        rows="2"
                    />
                </v-card-text>
            </v-card>

            <v-alert
                v-if="!error && !loading && statusData.age > 60"
                type="info"
                class="mb-3"
            >
                <translate>Tid sedan informationen uppdaterades:</translate> {{ statusData.age|duration }}
            </v-alert>

            <v-tabs
                v-model="tabs"
                :vertical="$vuetify.breakpoint.mdAndUp"
                background-color="grey lighten-4"
            >
                <v-tab
                    v-for="node in statusObjects(status)"
                    :key="node.title"
                    class="text-left justify-start"
                >
                    {{ node.title }}
                    <v-icon
                        v-if="reportActive && rootElements.indexOf(node.title) != -1"
                        class="ml-auto"
                    >
                        mdi-check
                    </v-icon>
                </v-tab>
                <v-tab-item
                    v-for="node in statusObjects(status)"
                    :key="node.title + 'item'"
                >
                    <v-card flat>
                        <v-card-title>
                            {{ node.title }}
                        </v-card-title>
                        <v-card-text>
                            <StatusTree
                                :checkbox="reportActive"
                                :is-root="true"
                                :parent="node"
                                :tree="node.value ? [node.orig] : node.children"
                                :filter="filter"
                            />
                        </v-card-text>
                    </v-card>
                </v-tab-item>
            </v-tabs>
        </div>
        <v-dialog
            v-model="reportDialog"
            scrollable
            max-width="800"
        >
            <v-card>
                <v-card-title class="headline">
                    {{ reportResult ? $gettext('Rapport') : $gettext('Skapa rapport') }}
                </v-card-title>
                <v-divider />
                <v-card-text>
                    <EndpointGrid
                        v-if="!reportResult"
                        v-model="reportEndpoints"
                        checkbox
                    />

                    <v-simple-table v-if="reportResult">
                        <thead>
                            <tr>
                                <th />
                                <th
                                    v-for="(values, endpointId) of reportResult"
                                    :key="endpointId"
                                >
                                    {{ endpointMap[endpointId].title }}
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="(values, key, index) in Object.values(reportResult)[0]"
                                :key="key + index"
                            >
                                <td>{{ key }}</td>
                                <td
                                    v-for="(values, endpointId, index2) of reportResult"
                                    :key="key + index + endpointId + index2"
                                >
                                    {{ reportResult[endpointId][key] }}
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                    <v-alert
                        v-if="reportError"
                        type="error"
                    >
                        {{ reportError }}
                    </v-alert>
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-btn
                        v-if="!reportResult"
                        color="primary"
                        :loading="reportLoading"
                        :disabled="!reportEndpoints.length"
                        @click="createReport"
                    >
                        <translate>Skapa rapport</translate>
                    </v-btn>
                    <v-spacer />
                    <v-btn
                        color="red"
                        text
                        @click="cancel"
                    >
                        {{ reportResult ? $gettext('Stäng') : $gettext('Avbryt') }}
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
import { GlobalEventBus } from '@/vue/helpers/events'

import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'
import TabLoaderIndicator from '@/vue/views/epm/endpoint/single/TabLoaderIndicator'

import StatusTree from '@/vue/components/epm/endpoint/StatusTree'
import EndpointGrid from '@/vue/components/epm/endpoint/EndpointGrid'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'

export default {
    components: {
        TabLoaderIndicator,
        PageSearchFilter,
        EndpointGrid,
        StatusTree,
    },
    mixins: [SingleEndpointMixin],
    data() {
        return {
            emitter: new GlobalEventBus(this),
            loading: true,
            reportActive: false,
            reportDialog: false,
            reportEndpoints: [],
            reportLoading: false,
            reportError: null,
            reportResult: null,
            text_filter: '',
            tabs: 0,
            error: false,
        }
    },
    computed: {
        endpointMap() {
            return this.$store.state.endpoint.endpoints
        },
        statusData() {
            return this.$store.state.endpoint.status[this.id] || {}
        },
        status() {
            return this.$store.state.endpoint.status[this.id]?.data || []
        },
        rootElements() {
            return Object.values(this.$store.state.endpoint.report).map(path => path[0])
        },
    },
    mounted() {
        this.emitter.on('refresh', () => this.loadData())
        this.loadData()
    },
    methods: {
        statusObjects(nodes) {
            const filtered = !this.text_filter
                ? nodes
                : nodes.filter(
                    node =>
                        JSON.stringify(node)
                            .toLowerCase()
                            .indexOf(this.text_filter.toLowerCase()) != -1
                )
            return filtered.map(node => {
                const [title, options, children, value] = node
                return { title, options, children, value, orig: node }
            })
        },
        createReport() {
            this.reportLoading = true
            this.reportError = null
            this.$store
                .dispatch('endpoint/createReport', {
                    endpoints: this.reportEndpoints,
                    values: Object.values(this.$store.state.endpoint.report),
                })
                .then(response => {
                    this.reportResult = response
                    this.reportLoading = false
                })
                .catch(e => {
                    this.reportLoading = false
                    this.reportError = e.toString()
                })
        },
        cancel() {
            this.reportDialog = false
            this.reportResult = null
        },
        loadData() {
            this.loading = true
            this.error = ''
            this.$store.dispatch('endpoint/getFullStatus', this.id).then(() => {
                this.loading = false
                this.emitter.emit('loading', false)
            }).catch(e => {
                this.error = e.toString()
                this.loading = false
                this.emitter.emit('loading', false)
            })
        }
    }
}
</script>
