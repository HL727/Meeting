<template>
    <Page
        icon="mdi-bug"
        :doc-url="debugViewDocsURL"
    >
        <template
            v-if="structure"
            v-slot:title
        >
            <h1>{{ structure.title }}</h1>
        </template>
        <template v-slot:content>
            <JsonDebugInfoDialog
                v-model="infoDialogIndex"
                :items="response.results"
                :structure="structure"
            />

            <v-row>
                <v-col
                    v-if="firstLoad && loading"
                    md="8"
                >
                    <v-skeleton-loader
                        type="table"
                        tile
                    />
                </v-col>
                <v-col
                    v-if="!(firstLoad && loading)"
                    md="8"
                >
                    <v-data-table
                        :loading="loading"
                        :items="filteredResults"
                        :headers="structure.headers"
                        disable-sort
                        :footer-props="footerProps"
                        :options.sync="pagination"
                        :server-items-length="(response && response.count) || -1"
                    >
                        <template v-slot:item.endpoint="{ item }">
                            <router-link
                                v-if="item.endpoint && endpoints[item.endpoint]"
                                :to="{ name: 'endpoint_details', params: { id: item.endpoint } }"
                            >
                                {{ endpoints[item.endpoint].title }}
                            </router-link>
                            <span v-else>{{ item.endpoint || '-' }}</span>
                        </template>
                        <template v-slot:item.customer="{ item }">
                            <router-link
                                v-if="item.customer && customers[item.customer]"
                                :to="{ name: 'start', query: { customer: item.customer } }"
                            >
                                {{ customers[item.customer].title }}
                            </router-link>
                            <span v-else>{{ item.customer || '-' }}</span>
                        </template>
                        <template v-slot:item.cluster_id="{ item }">
                            <span v-if="item.cluster_id && clusters[item.cluster_id]">{{ clusters[item.cluster_id].title || item.cluster_id }}</span>
                            <span v-else>{{ item.cluster_id || '-' }}</span>
                        </template>

                        <template v-slot:item.button="{ item }">
                            <v-icon
                                v-if="item.extra && item.extra.error"
                                color="red"
                                :title="item.extra.error"
                            >
                                mdi-alert
                            </v-icon>
                            <v-btn
                                color="primary"
                                dark
                                icon
                                @click="infoDialogIndex=item.index"
                            >
                                <v-icon color="lime darken-2">
                                    mdi-information
                                </v-icon>
                            </v-btn>
                        </template>
                    </v-data-table>
                </v-col>
                <v-col
                    md="4"
                    class="px-5 pt-6"
                >
                    <p class="my-5">
                        <v-icon>mdi-information-outline</v-icon>
                        {{ structure.description }}
                    </p>

                    <v-card class="my-4">
                        <v-card-text>
                            <v-text-field
                                v-model="contentFilter"
                                :label="$gettext('Sök innehåll')"
                                :hint="$gettext('case sensitive')"
                            />
                        </v-card-text>
                    </v-card>

                    <v-card
                        dark
                        :loading="loading"
                    >
                        <v-card-text>
                            <v-container>
                                <v-alert
                                    v-if="errors"
                                    type="error"
                                >
                                    <div
                                        v-for="error in errors"
                                        :key="`error-${error.label}`"
                                    >
                                        <strong>{{ error.label }}:</strong> {{ error.error }}
                                    </div>
                                </v-alert>
                                <v-form
                                    ref="form"
                                    lazy-validation
                                >
                                    <div
                                        v-for="(filter, query) in filters"
                                        :key="query"
                                    >
                                        <v-datetime-picker
                                            v-if="filter.type == 'datetime'"
                                            v-model="filter.value"
                                            :label="filter.text"
                                        />
                                        <v-text-field
                                            v-else
                                            v-model="filter.value"
                                            :type="filter.type"
                                            :label="filter.text"
                                        />
                                    </div>

                                    <v-btn
                                        color="lime darken-2"
                                        depressed
                                        class="mr-4"
                                        @click="search"
                                    >
                                        <translate>Filtrera</translate>
                                    </v-btn>
                                </v-form>
                            </v-container>
                        </v-card-text>
                    </v-card>
                </v-col>
            </v-row>
        </template>
    </Page>
</template>

<script>
import {$gettext} from '@/vue/helpers/translate'

import {debugViewStructure} from '@/vue/store/modules/debug_views/consts'
import {timestamp} from '@/vue/helpers/datetime'
import Page from '@/vue/views/layout/Page'
import VDatetimePicker from '../../components/datetime/DateTimePicker'
import JsonDebugInfoDialog from '@/vue/components/debug_views/JsonDebugInfoDialog'
import { extendFooterProps } from '@/vue/components/base/VDataTablePaginated'

const defaultFilters = {
    ts_created__gte: { text: $gettext('Skapad fr.o.m.'), type: 'datetime', value: new Date(new Date() - 3 * 24 * 60 * 60) },
    ts_created__lte: { text: $gettext('Skapad t.o.m.'), type: 'datetime' },
}

function initialState() {
    return {
        debugViewStructure: {},
        firstLoad: true,
        loading: true,
        response: {},
        pagination: { page: 1, itemsPerPage: 20 },
        limit: 10,
        dialogs: {},
        filters: {},
        errors: false,
        infoDialogIndex: null,
        contentFilter: '',
    }
}

export default {
    components: { JsonDebugInfoDialog, Page, VDatetimePicker },
    props: {
        debugView: {
            type: String,
            default: '',
            required: true,
        },
    },
    data: initialState,
    computed: {
        debugViewDocsURL() {
            return !this.debugView ? null : `debug_api_${this.debugView}`
        },

        structure() {
            return { ...this.debugViewStructure[this.debugView] || {}, key: this.debugView }
        },
        filteredResults() {
            const result = this.response.results || []
            if (!this.contentFilter) {
                return result
            }
            const search = this.contentFilter
            return result.filter(item => {
                if (typeof item.content == 'string') {
                    return item.content.indexOf(search) != -1
                }
                return JSON.stringify(item.content).indexOf(search) != -1
            })
        },
        endpoints() {
            return this.$store.state.endpoint.endpoints || {}
        },
        customers() {
            return this.$store.state.site.customers || {}
        },
        clusters() {
            return this.$store.state.provider.clusters || {}
        },
        footerProps() {
            return extendFooterProps({ showFirstLastPage: true })
        },
    },
    watch: {
        pagination: {
            handler(newValue, oldValue) {
                this.offset = (newValue.page - 1) * newValue.itemsPerPage
                this.limit = newValue.itemsPerPage

                if (newValue.page !== oldValue.page || newValue.itemsPerPage !== oldValue.itemsPerPage) {
                    this.requestResults()
                }
            },
            deep: true,
        },
        '$route.path'() {
            this.init()
        },
    },
    created() {
        this.init()
    },
    methods: {
        init() {
            const state = initialState()
            state.debugViewStructure = debugViewStructure(this.$store.state.site)
            state.filters = { ...defaultFilters, ...state.debugViewStructure[this.debugView].filters }
            Object.assign(this.$data, state)
            return Promise.all([
                this.requestResults(),
                this.$store.dispatch('provider/getClusters'),
                this.$store.dispatch('endpoint/getEndpoints'),
            ])
        },
        search() {
            this.pagination.page = 1
            return this.requestResults()
        },
        getFilterParams() {
            const { page, itemsPerPage } = this.pagination
            const filterParams = {}
            if (this.filters) {
                Object.entries(this.filters).forEach(([key, { value }]) => {
                    if (value) filterParams[key] = value
                })
            }

            return {
                ...filterParams,
                limit: itemsPerPage,
                offset: (page - 1) * itemsPerPage,
            }
        },
        requestResults() {

            if (this.loading && !this.firstLoad) return

            this.errors = false
            this.loading = true

            return this.$store
                .dispatch('debug_views/getData', {
                    module: this.debugView,
                    params: this.getFilterParams(),
                })
                .then(response => {
                    this.loading = false
                    this.firstLoad = false
                    const results = response.results.map((item, index) => {
                        return {
                            index,
                            parts: [],
                            ...item,
                            partsCount: item.parts ? item.parts.length : item.content && item.content.length,
                            ts_created: timestamp(item.ts_created),
                        }
                    })
                    // Note: frozen results so that vue doesnt need to add observers to all items
                    this.response = { ...response, results: Object.freeze(results) }
                })
                .catch(e => {
                    this.loading = false
                    this.errors = this.getErrors(e)
                })
        },
        getErrors(response) {

            if (!response.errors) {
                const e = response
                return [{ label: 'error', error: e.error || (e && e.toString()) || $gettext('Error') }]
            }
            return Object.entries(response.errors || {}).map(([field, values]) => {
                return {
                    label: this.filters[field]?.text || field,
                    error: values.join(', '),
                }
            })
        }
    },
}
</script>

