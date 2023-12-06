<template>
    <Page
        icon="mdi-calendar"
        :title="$gettext('Bokade möten')"
        :actions="pageActions"
        search-width=""
    >
        <template v-slot:search>
            <div class="">
                <v-form
                    class="d-flex mr-4"
                    :class="{'flex-wrap': $vuetify.breakpoint.xsOnly}"
                    @submit.prevent="searchDebounce(true)"
                >
                    <v-text-field
                        v-model="search"
                        class="mr-4"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök möte') + '...'"
                        :style="searchInputStyle"
                        outlined
                        dense
                    />
                    <v-datetime-picker
                        v-model="tsStart"
                        :input-attrs="{
                            outlined: true,
                            dense: true,
                            hideDetails: true,
                            class: 'mr-4',
                            style: 'max-width:12rem;'
                        }"
                        :label="$gettext('Fr.o.m.')"
                    />
                    <v-datetime-picker
                        v-model="tsStop"
                        :input-attrs="{
                            outlined: true,
                            dense: true,
                            hideDetails: true,
                            class: 'mr-4',
                            style: 'max-width:12rem;'
                        }"
                        :label="$gettext('T.o.m.')"
                    />
                    <v-btn
                        color="primary"
                        :loading="loading"
                        class="px-1 mr-md-4"
                        type="submit"
                        @click.prevent="searchDebounce"
                    >
                        <v-icon>mdi-refresh</v-icon>
                    </v-btn>
                </v-form>
            </div>
        </template>
        <template v-slot:filter>
            <VBtnFilter
                :disabled="loading"
                :filters="filterList"
                :style="filterButtonStyle"
                @click="filterDialog = true"
                @removeFilter="removeFilter"
            />
        </template>
        <template v-slot:content>
            <ErrorMessage :error="error" />

            <v-data-table-paginated
                :loading="loading"
                :items="meetings"
                multiple
                disable-sort
                :options.sync="pagination"
                :headers="activeHeaders"
                :server-items-length="page.count || -1"
                @update:page="setPage"
            >
                <template v-slot:item.title="{ item }">
                    <router-link
                        :to="item.details_url"
                        :class="{
                            'text-decoration-line-through': item.ts_unbooked || !item.was_activated
                        }"
                    >
                        {{ item.title }}
                    </router-link>
                </template>
                <template v-slot:item.customer="{ item }">
                    <a :href="`/?customer=${item.customer}`">{{ item.customerName }}</a>
                </template>
                <template v-slot:item.endpoints="{ item }">
                    <router-link
                        v-for="endpoint in item.endpoints"
                        :key="endpoint.id"
                        :to="{ name: 'endpoint_details', params: { id: endpoint.id } }"
                        class="mr-2"
                    >
                        {{ endpoint.title }}
                    </router-link>
                </template>
                <template v-slot:item.ts_start="{ item }">
                    {{ item.ts_start|timestamp }}
                </template>
                <template v-slot:item.ts_stop="{ item }">
                    {{ item.ts_stop|time }}
                    <template v-if="date(item.ts_start) != date(item.ts_stop)">
                        <span :title="item.ts_stop|timestamp">(*)</span>
                    </template>
                </template>
            </v-data-table-paginated>
            <v-dialog
                v-model="filterDialog"
                max-width="320"
            >
                <v-card>
                    <v-card-title><translate>Filtrera</translate></v-card-title>
                    <v-divider />
                    <v-card-text>
                        <UserPicker
                            :search.sync="filters.creator"
                            item-search="jid"
                            :label="$gettext('Sök efter skapad av')"
                        />
                        <OrganizationPicker
                            v-if="enableOrganization"
                            v-model="filters.organization"
                            :label="$gettext('Organisationsenhet')"
                            input-name="organization_unit"
                            hide-add-new
                        />
                        <EndpointPicker
                            v-if="settings.enableEPM"
                            v-model="filters.endpoint"
                            :label="$ngettext('System', 'System', 1)"
                            hide-add-new
                            single
                        />
                        <v-checkbox
                            v-model="filters.only_active"
                            :label="$gettext('Endast aktiva')"
                        />
                        <v-checkbox
                            v-if="Object.keys(settings.customers).length > 1 && settings.perms.staff"
                            v-model="filters.all_customers"
                            :label="$gettext('Visa alla kunder')"
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-actions>
                        <v-btn
                            type="submit"
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
        </template>
    </Page>
</template>

<script>
import { itemListSearchPrefix } from '@/consts'
import { replaceQuery } from '@/vue/helpers/url'
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'
import VDatetimePicker from '@/vue/components/datetime/DateTimePicker'
import UserPicker from '@/vue/components/user/UserPicker'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'
import { formatISO } from '@/vue/helpers/datetime'
import EndpointPicker from '@/vue/components/epm/endpoint/EndpointPicker'

export default {
    name: 'MeetingList',
    components: {EndpointPicker, ErrorMessage, Page, UserPicker, VDatetimePicker, VBtnFilter, OrganizationPicker },
    mixins: [PageSearchMixin],
    props: {
        onlyEndpoints: Boolean,
        includeExternal: Boolean,
        endpoint: { type: Number, default: null },
    },
    data() {
        const pageHistory = history.state?.page || {}
        const orgUnit = (this.$route.query.organization_unit || '').replace(itemListSearchPrefix, '')
        const initialFilters = {
            creator: '',
            organization: orgUnit ? parseInt(orgUnit) : null,
            all_customers: false,
            only_active: false,
            ...(pageHistory.filters || {})
        }
        return {
            tsStart: pageHistory.tsStart || new Date(new Date() - 60 * 60 * 1000),
            tsStop: pageHistory.tsStop || '',
            page: { count: pageHistory.count || null },
            pagination: { page: 1, itemsPerPage: 10, ...( pageHistory.pagination || {} ) },
            headers: [
                { text: $gettext('Rubrik'), value: 'title' },
                { text: $gettext('Starttid'), value: 'ts_start' },
                { text: $gettext('Sluttid'), value: 'ts_stop' },
                { text: $gettext('Typ'), value: 'type_str' },
                { text: $gettext('Skapad av'), value: 'creator' },
            ],
            search: pageHistory.search ||
                (this.$route.query.meeting_id || '').replace(itemListSearchPrefix, ''),
            filters: { ...initialFilters },
            activeFilters: { ...initialFilters },
            filterDialog: false,
            error: null,
            firstLoad: true
        }
    },
    computed: {
        customers() {
            return this.$store.state.site.customers
        },
        endpoints() {
            return this.$store.state.endpoint.endpoints
        },
        pageActions() {
            return [
                {
                    icon: 'mdi-plus',
                    hidden: this.onlyEndpoints,
                    click: () => this.$router.push({ name: 'meetings_add' })
                },
                {
                    type: 'refresh',
                    click: () => this.searchDebounce()
                }
            ]
        },
        searchInputStyle() {
            return this.$vuetify.breakpoint.mdAndUp ?
                { maxWidth: '20rem' } : null
        },
        filterButtonStyle() {
            return this.$vuetify.breakpoint.mdAndUp ?
                { maxWidth: '25rem', marginLeft: '2rem' } : null
        },
        organizations() {
            return this.$store.getters['organization/all']
        },
        selectedOrganization() {
            return this.organizations.find(o => o.id === this.activeFilters.organization)
        },
        // eslint-disable-next-line max-lines-per-function
        filterList() {
            const activeFilter = []

            if (this.activeFilters.creator) {
                activeFilter.push({
                    key: 'creator',
                    title: $gettext('Skapad av'),
                    value: this.activeFilters.creator
                })
            }
            if (this.activeFilters.all_customers) {
                activeFilter.push({
                    key: 'all_customers',
                    title: $gettext('Visa alla kunder')
                })
            }
            if (this.activeFilters.only_active) {
                activeFilter.push({
                    key: 'only_active',
                    title: $gettext('Bara aktiva')
                })
            }
            if (this.activeFilters.endpoint) {
                activeFilter.push({
                    key: 'endpoint',
                    title: this.$ngettext('System', 'System', 1),
                    value: this.endpoints[this.activeFilters.endpoint[0]].title
                })
            }

            if (this.selectedOrganization) {
                activeFilter.push({
                    key: 'organization',
                    title: 'OU',
                    value: this.selectedOrganization.name
                })
            }

            return activeFilter
        },
        enableOrganization() {
            return this.$store.state.site.enableOrganization
        },
        meetings() {
            const meetings = this.page.results || []

            return meetings.map((m) => {
                return {
                    ...m,
                    customerName: m.customer in this.customers ? this.customers[m.customer].title : ''
                }
            })
        },
        settings() {
            return this.$store.state.site
        },
        activeHeaders() {
            let headers = this.headers

            if (this.meetings.some(m => m.endpoints && m.endpoints.length)) {
                headers = [headers[0], { text: $gettext('Endpoints'), value: 'endpoints' }, ...headers.slice(1)]
            }
            if (this.activeFilters.all_customers) {
                headers = [headers[0], { text: $gettext('Kund'), value: 'customer' }, ...headers.slice(1)]
            }

            return headers
        },
    },
    watch: {
        'pagination.itemsPerPage': function() {
            if (!this.firstLoad) this.searchDebounce()
        },
        search() {
            if (!this.firstLoad) this.searchDebounce(true)
        },
        tsStart() {
            if (!this.firstLoad) this.searchDebounce(true)
        },
        tsStop() {
            if (!this.firstLoad) this.searchDebounce(true)
        },
    },
    mounted() {
        this.$nextTick(this.loadData)
    },
    methods: {
        date(ts) {
            return this.$options.filters.date(ts)
        },
        setPage() {
            this.searchDebounce()
        },
        removeFilter({ filter }) {
            this.filters[filter.key] = null
            this.applyFilters()
        },
        applyFilters() {
            this.filterDialog = false
            this.activeFilters = { ...this.filters }

            this.searchDebounce(true)
        },
        addOrgUnitQuery(id) {
            location.href = replaceQuery(null, { organization_unit: id })
        },
        newSearch() {
            this.loadData()
        },
        // eslint-disable-next-line max-lines-per-function
        async loadData() {
            this.firstLoad = false
            this.setLoading(true)
            this.error = null

            const endpointArgs = {}
            if (this.onlyEndpoints) endpointArgs.only_endpoints = 1
            if (this.includeExternal) endpointArgs.include_external = 1
            if (this.endpoint) endpointArgs.endpoint = this.endpoint
            else if (this.activeFilters.endpoint) endpointArgs.endpoint = this.activeFilters.endpoint

            const { tsStart, tsStop } = this

            const response = await this.$store.dispatch('meeting/search', {
                page: this.pagination.page,
                limit: this.pagination.itemsPerPage,
                ...endpointArgs,
                title: this.search,
                ...this.activeFilters,
                only_active: this.activeFilters.only_active ? '1' : undefined,
                all_customers: this.activeFilters.all_customers ? '1' : undefined,
                ts_start: formatISO(tsStart),
                ts_stop: tsStop ? formatISO(tsStop) : '',
            }).catch(e => {
                this.error = e
            })

            this.page = response || {}

            history.replaceState({
                ...history.state,
                page: {
                    count: this.page.count,
                    tsStart,
                    tsStop,
                    search: this.search,
                    filters: { ...this.activeFilters },
                    pagination: { ...this.pagination },
                }
            }, '')

            this.setLoading(false)
        },
    },
}
</script>
