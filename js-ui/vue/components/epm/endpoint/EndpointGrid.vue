<template>
    <div>
        <slot name="header" />

        <PageSearchFilter :filter-style="filterStyle">
            <template v-slot:search>
                <v-form @submit.prevent="reloadEndpoints()">
                    <div class="d-flex align-center">
                        <v-text-field
                            v-model="searchValue"
                            hide-details
                            prepend-inner-icon="mdi-magnify"
                            :placeholder="$gettext('Sök system') + '...'"
                            outlined
                            dense
                            class="mr-4"
                        />
                        <v-btn
                            color="primary"
                            :loading="endpointsLoading"
                            class="mr-md-4"
                            @click="reloadEndpoints"
                        >
                            <v-icon>mdi-refresh</v-icon>
                        </v-btn>
                    </div>
                </v-form>
            </template>
            <template v-slot:filter>
                <VBtnFilter
                    class="d-xl-none"
                    :text="$gettext('Gruppering')"
                    icon="mdi-select-group"
                    :filters="grouping"
                    :disabled="endpointsLoading"
                    @click="groupingDialog = true"
                    @removeFilter="removeGroupFilter()"
                />

                <VBtnFilter
                    :filters="filters"
                    :disabled="endpointsLoading"
                    :show-remove-all="true"
                    class="ml-4"
                    @click="filterDialog = true"
                    @removeFilter="removeFilter($event)"
                    @removeAllFilters="removeAllFilters"
                />
            </template>
        </PageSearchFilter>

        <v-row>
            <v-col
                cols="3"
                class="d-none d-xl-block"
            >
                <p class="overline mb-0">
                    <translate>Gruppering</translate>
                </p>
                <v-skeleton-loader
                    v-if="loadingFilters"
                    type="image"
                />
                <EndpointGrouping
                    v-else
                    v-model="groupingSelections"
                    :target.sync="groupsTarget"

                    :endpoints="filteredEndpoints"
                    :show-empty="showEmpty"
                    :available-filters="availableFilters"

                    :disabled="$vuetify.breakpoint.lgAndDown"
                    @change="applyGrouping"
                />
            </v-col>
            <v-col
                cols="12"
                xl="9"
            >
                <slot
                    name="table"
                    :endpoints="groupFiltered"
                    :loading="endpointsLoading"
                    :search="searchValue"
                >
                    <v-data-table
                        v-model="checked"
                        :class="{'footer-left': tableFooterLeft}"
                        :headers="headers"
                        :items="groupFiltered"
                        :items-per-page.sync="pagination.perPage"
                        :page.sync="pagination.page"
                        :show-select="checkbox"
                        :single-select="single"
                        :search="searchValue"
                        :height="tableHeight"
                        :loading="endpointsLoading"
                    >
                        <template v-slot:item.title="{ item }">
                            <v-tooltip bottom>
                                <template v-slot:activator="{ on, attrs }">
                                    <div class="d-flex align-center">
                                        <EndpointStatus
                                            :endpoint="item"
                                            class="mr-1"
                                            ignore-meeting-status
                                        />
                                        <span>
                                            <a
                                                v-router-link="{ name: 'endpoint_details', params: { id: item.id } }"
                                                href="#"
                                                v-bind="attrs"
                                                v-on="on"
                                            >{{ item.title || '-- empty --' }}</a>
                                            <small class="d-block">{{ item.product_name }}</small>
                                        </span>
                                    </div>
                                </template>
                                <span>
                                    <strong><translate>MAC</translate>:</strong> {{ item.mac_address }}, <strong><translate>Grupp</translate>:</strong>
                                    {{ item.organizationPath || $gettext('empty') }}, <strong><translate>Firmware</translate>:</strong>
                                    {{ item.status.software_version }}
                                </span>
                            </v-tooltip>
                        </template>

                        <template v-slot:item.ip="{ item }">
                            <a
                                v-if="item.ip || item.hostname"
                                target="_blank"
                                :href="'https://' + (item.ip || item.hostname) + '/'"
                            >{{ item.ip || item.hostname }}
                            </a>
                        </template>

                        <template v-slot:[`header.${customHeader}`]>
                            <v-select
                                v-model="customHeader"
                                style="max-width: 140px;"
                                :items="customHeaders"
                                item-value="value"
                                dense
                                :hide-details="true"
                                class="d-inline-block"
                                @click.native.stop
                            />
                        </template>

                        <template v-slot:item.notifiers="{ item }">
                            <v-icon v-if="item.status.has_warnings">
                                mdi-alert
                            </v-icon>
                            <v-icon v-if="item.is_new">
                                mdi-new-box
                            </v-icon>
                        </template>
                    </v-data-table>
                </slot>
            </v-col>
        </v-row>

        <slot
            name="actions"
            :endpoints="checked"
        />

        <v-dialog
            v-model="groupingDialog"
            eager
            scrollable
            max-width="420"
        >
            <v-card>
                <v-card-title>
                    <translate>Gruppering</translate>
                </v-card-title>
                <v-divider />
                <v-card-text class="pa-0">
                    <v-skeleton-loader
                        v-if="loadingFilters"
                        type="image"
                    />
                    <EndpointGrouping
                        v-else
                        v-model="groupingSelections"
                        :target.sync="groupsTarget"

                        :endpoints="endpointList"
                        :show-empty="showEmpty"
                        :available-filters="availableFilters"
                    />
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-btn
                        color="primary"
                        @click="applyGrouping"
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

        <v-dialog
            v-model="filterDialog"
            scrollable
            max-width="420"
        >
            <v-card>
                <v-card-title>
                    <translate>Filtrera</translate>
                </v-card-title>
                <v-divider />
                <v-card-text v-if="activeFilters.form">
                    <v-combobox
                        v-model="activeFilters.form.status__software_version"
                        :items="availableFilters.firmware"
                        :label="$gettext('Firmware')"
                    />
                    <v-select
                        v-model="activeFilters.form.status_code"
                        :items="endpointStatusChoices"
                        item-value="id"
                        item-text="title"
                        :label="$gettext('Status')"
                    />

                    <v-checkbox
                        v-model="activeFilters.form.is_new"
                        hide-details
                        :label="$gettext('Endast nya system')"
                    />
                    <v-checkbox
                        v-model="activeFilters.form.webex_registration"
                        hide-details
                        :label="$gettext('Endast Webex-registrerade system')"
                    />
                    <v-checkbox
                        v-model="activeFilters.form.pexip_registration"
                        hide-details
                        :label="$gettext('Endast Pexip.me-registrerade system')"
                    />
                    <v-checkbox
                        v-model="activeFilters.form.status__has_warnings"
                        hide-details
                        :label="$gettext('Endast system med varningar')"
                    />
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-btn
                        color="primary"
                        :loading="filterLoading"
                        @click="applyDelayedFilters"
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
import { setQuery } from '@/vue/helpers/url'
import { idMap } from '@/vue/helpers/store'
import { getObjectValueByPath } from 'vuetify/lib/util/helpers'
import {
    endpointConnectionTypeChoices,
    endpointStatusChoices,
} from '@/vue/store/modules/endpoint/consts'

import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'

import VBtnFilter from '@/vue/components/filtering/VBtnFilter'
import EndpointGrouping from '@/vue/components/epm/endpoint/EndpointGrouping'

import EndpointsMixin from '@/vue/views/epm/mixins/EndpointsMixin'

const emptyFilters = {
    title: '',
    sip: '',
    h323: '',
    h323_e164: '',
    ip: '',
    product_name: '',
    location: '',
    serial: '',
    status__software_version: '',
    status__has_warnings: '',
    status_code: '',
    connection_type: '',
    online: '',
    warnings: '',
    is_new: '',
    webex_registration: '',
    pexip_registration: '',
}

const parseFormValues = (formData, query) => {
    const result = { ...formData }

    Object.entries(query)
        .filter(q => q[0] in emptyFilters && (q[1] || q[1] === 0))
        .forEach(q => {
            return result[q[0]] = q[1]
        })

    if (Array.isArray(result.status_code)) {
        result.status_code = result.status_code.map(s => parseInt(s, 10))
    }
    else {
        result.status_code = result.status_code || result.status_code === 0 ? parseInt(result.status_code, 10) : ''
    }

    result.is_new = !!result.is_new
    result.online = !!(result.online && parseInt(result.online, 10))
    result.status__has_warnings = !!result.status__has_warnings
    result.webex_registration = !!result.webex_registration

    return result
}

const emptySelections = {
    organizations: [],
    locations: [],
    models: [],
    status_code: [],
    connection_type: [],
}

const paginationDefault = {
    perPage: 10,
    page: 1,
}

const parseSelectionValues = (selectionData, query) => {

    if (!query.group_target || !selectionData.targets.includes(query.group_target)) {
        return { ...selectionData }
    }

    const result = { ...selectionData }
    const groupKey = query.group_target
    result.target = selectionData.targets.indexOf(groupKey)

    if (query.group_values === undefined) return result

    let groupValues = Array.isArray(query.group_values) ? query.group_values : [query.group_values]

    if (['locations', 'models'].includes(groupKey)) {  // string options
        result[groupKey] = groupValues
        return result
    }

    result[groupKey] = groupValues.map(v => v ? parseInt(v, 10) : null)
    return result

}

export default {
    name: 'EndpointGrid',
    components: {
        PageSearchFilter,
        VBtnFilter,
        EndpointGrouping,
    },
    mixins: [EndpointsMixin],
    props: {
        checkbox: { type: Boolean, default: false },
        value: { type: Array, default: () => [] },
        single: { type: Boolean, default: false },
        showEmpty: { type: Boolean, default: undefined },
        hideSearch: Boolean,
        search: { type: String, required: false, default: '' },
        tableHeight: { type: Number, default: undefined },
        tableFooterLeft: { type: Boolean, default: false },
        onlyHeadCount: { type: Boolean, default: false },
        endpointFiltering: { type: Function, default: null },
        endpointMapping: { type: Function, default: null },
        enableNavigationHistory: { type: Boolean, default: false },
    },
    // eslint-disable-next-line max-lines-per-function
    data() {
        const filterLabels = {
            title: '',
            sip: $gettext('SIP'),
            h323: $gettext('H323'),
            h323_e164: $gettext('E.164'),
            ip: $gettext('IP'),
            product_name: $gettext('Produktnamn'),
            location: $gettext('Plats'),
            serial: $gettext('Serienummer'),
            status__software_version: $gettext('Firmware'),
            status__has_warnings: $gettext('Har varning'),
            status_code: $gettext('Status'),
            connection_type: $gettext('Anslutning'),
            online: '',
            warnings: '',
            is_new: $gettext('Nya'),
            webex_registration: $gettext('Webex'),
            pexip_registration: $gettext('Pexip'),
        }

        const customHeaders = []
        const headerTitles = {
            serial_number: $gettext('Serienummer'),
            product_name: $gettext('Modell'),
            organizationPath: $gettext('Grupp'),
            'status.software_version': $gettext('Firmware'),
            mac_address: $gettext('MAC-adress'),
            h323_e164: 'E.164',
            h323: 'H323',
            location: $gettext('Plats'),
        }

        Object.entries(headerTitles).map(a => customHeaders.push({ value: a[0], text: a[1] }))

        const initalSelection = parseSelectionValues({
            target: null,
            targets: ['organizations', 'locations', 'models', 'status_code', 'connection_type'],
            ...emptySelections
        }, this.$route.query)

        return {
            checked: [],
            filter: parseFormValues(emptyFilters, this.$route.query),
            filterLabels: filterLabels,
            filterLoading: false,
            emptyFilters: emptyFilters,
            availableFilters: {},
            searchValue: this.search || this.$route.query.search || '',
            pagination: {
                perPage: this.$route.query.per_page ?
                    parseInt(this.$route.query.per_page, 10) :
                    paginationDefault.perPage,
                page: this.$route.query.page ?
                    parseInt(this.$route.query.page, 10) :
                    paginationDefault.page,
            },
            paginationDefault,
            filterDialog: false,
            activeFilters: {},
            customHeader: 'serial_number',
            customHeaders: customHeaders,
            headerTitles: headerTitles,
            selected: initalSelection,
            emptySelections,
            endpointStatusChoices,
            endpointConnectionTypeChoices,

            groupingDialog: false,
            groupingSelections: {
                ...initalSelection,
            },
            groupsTarget: initalSelection.target,
            lastUrl: '',
            loadingFilters: true,
        }
    },
    computed: {
        endpointStatus() {
            return this.$store.state.stats.endpointStatus
        },
        organizations() {
            return this.$store.getters['organization/tree']
        },
        filterStyle() {
            return this.$vuetify.breakpoint.mdAndUp ?
                { maxWidth: '75%', paddingLeft: '2rem' } : null
        },
        filters() {
            const activeFilter = []

            Object.entries(this.filter).forEach((f) => {
                const k = f[0]
                let v = f[1]

                if (v || v === 0) {
                    if (k === 'status_code') {
                        v = Array.isArray(v) ? v : [v]
                        v = v.map(code => this.endpointStatusChoices.find((s) => s.id === code).title).join(', ')
                    }
                    activeFilter.push({
                        key: k,
                        type: 'filter',
                        title: this.filterLabels[k],
                        value: v
                    })
                }
            })

            return activeFilter
        },
        headers() {
            const custom = {
                text: this.headerTitles[this.customHeader],
                value: this.customHeader,
                sortable: true,
                width: 200
            }

            return [
                { text: $gettext('Namn'), value: 'title' },
                { text: $gettext('URI'), value: 'uri' },
                { text: 'IP', value: 'ip' },
                custom,
                { text: '', value: 'notifiers', sortable: false, align: 'end' },
            ]
        },
        objectFilters() {
            const filters = this.availableFilters || {}
            return {
                ...filters,
                location: (filters.location || []).map(l => ({id: l, title: l || $gettext('<Okänd tillhörighet>')})),
                product_name: (filters.product_name || []).map(p => ({id: p, title: p || $gettext('<Okänd tillhörighet>')})),
            }
        },
        endpointList() {
            let endpoints = this.endpoints

            if (this.endpointFiltering) {
                endpoints = endpoints.filter(this.endpointFiltering)
            }

            if (this.endpointMapping) {
                endpoints = endpoints.map(this.endpointMapping)
            }

            return endpoints
        },
        filtersAsStrings() {
            return Object.entries(this.filter)
                .filter(item => item[1] || item[1] === 0)
                .map(i => [i[0], i[1].toString().toLocaleLowerCase()])
        },
        filteredEndpoints() {
            return this.endpointList.filter(endpoint => {
                return this.filterEndpointTest(endpoint)
            })
        },
        groupFiltered() {
            if (this.selected.target === null || this.selected.target === undefined) {
                return this.filteredEndpoints
            }

            const targetKey = this.selected.targets[this.selected.target] || 'organizations'
            const property = {
                organizations: 'org_unit',
                locations: 'location',
                models: 'product_name',
                status_code: 'status_code',
                connection_type: 'connection_type',
            }[targetKey]

            const selected = this.selected[targetKey] || null

            if (!selected || !selected.length) {
                return this.filteredEndpoints
            }

            return this.filteredEndpoints.filter(endpoint =>
                selected.includes(endpoint[property])
            )
        },
        grouping() {
            if (this.selected.target === null) {
                return []
            }

            const selectedTarget = this.selected.targets[this.selected.target]
            const selected = this.selected[selectedTarget] || null

            if (!selected || !selected.length) {
                return []
            }

            const groupLabels = {
                organizations: 'OU',
                locations: $gettext('Plats'),
                models: $gettext('Model'),
                status_code: $gettext('Status'),
                connection_type: $gettext('Anslutning'),
            }

            return [{
                title: groupLabels[selectedTarget]
            }]
        }
    },
    watch: {
        checked() {
            this.$emit(
                'input',
                this.checked.map(e => e.id)
            )
        },
        value() {
            this.initEndpoints()
        },
        filters(newValue) {
            this.$emit('filters', newValue)
        },
        filter() {
            this.setFilterUrlQuery()
        },
        selected: {
            deep: true,
            handler() {
                this.setFilterUrlQuery()
            }
        },
        filteredEndpoints(newValue) {
            this.$emit('endpoints', newValue)
        },
        filterDialog(newValue) {
            if (newValue && Object.keys(this.availableFilters).length === 0) {
                return this.$store.dispatch('endpoint/getFilters').then(filters => (this.availableFilters = filters))
            } else {
                this.$emit('input:filterDialog', false)
            }
        },
        search() {
            this.searchValue = this.search
        },
        searchValue() {
            this.setFilterUrlQuery()
        },
        pagination: {
            deep: true,
            handler() {
                this.setFilterUrlQuery()
            }
        },
        '$route.fullPath'() {
            this.reloadIfPathChange()
        },
    },
    mounted() {
        this.activeFilters = {
            form: {...this.emptyFilters, ...this.filter},
            selected: {...this.selected}
        }
        return this.$store.dispatch('endpoint/getFilters').then(filters => {
            this.availableFilters = filters
            this.loadingFilters = false
        })
    },
    methods: {
        filterEndpointTest(endpoint) {
            if (this.onlyHeadCount && !endpoint.has_head_count) {
                return false
            }

            for (const filter of this.filtersAsStrings) {
                if (filter[0] === 'online' && filter[1] !== '0' !== endpoint.status_code > 0)
                    return false
                else {
                    const cur = this.getEndpointFilterValue(endpoint, filter)
                    if (filter[0] === 'status_code' && !filter[1].split(',').includes(cur)) return false
                    if (filter[0] !== 'status_code' && cur.substr(0, filter[1].length) !== filter[1]) return false
                }
            }

            return true
        },
        getEndpointFilterValue(endpoint, filter) {
            const objectValue = getObjectValueByPath(endpoint, filter[0]?.replace('__', '.'), '')
            return objectValue === null ? '' : objectValue.toString().toLocaleLowerCase()
        },
        setFilterUrlQuery() {
            if (!this.enableNavigationHistory) return

            const query = { ...this.filter }

            if (this.selected.target !== null) {
                const groupKey = this.selected.targets[this.selected.target]
                let groupValues = [ ...this.selected[groupKey] ]

                if (groupValues.length) {
                    query.group_target = groupKey
                    query.group_values = groupValues
                }
            }

            if (this.searchValue) {
                query.search = this.searchValue
            }
            if (this.paginationDefault.page !== this.pagination.page) {
                query.page = this.pagination.page
            }
            if (this.paginationDefault.perPage !== this.pagination.perPage) {
                query.per_page = this.pagination.perPage
            }

            const url = setQuery(this.$route.fullPath, query, true)
            this.lastUrl = url

            if (setQuery(this.$route.fullPath, null, true) !== this.lastUrl) {
                this.$router.replace(url).catch(() => {})
                this.$nextTick(() => (this.$emit('refreshed')))
            }
        },
        reloadIfPathChange() {
            if (!this.enableNavigationHistory || this.lastUrl === setQuery(this.$route.fullPath, null, true)) return // same path

            this.lastUrl = this.$route.fullPath

            if (this.lastUrl === setQuery(this.$route.fullPath, {}, true)) {
                // root
                this.activeFilters.form = { ...this.emptyFilters }
                this.applyFilters()
                return
            }

            if (this.$route.query.group_target) {
                this.groupingSelections = parseSelectionValues(this.selected, this.$route.query)
                this.groupsTarget = this.groupingSelections.target
                this.applyGrouping()
            }

            this.activeFilters.form = parseFormValues(this.emptyFilters, this.$route.query)
            this.applyFilters()
        },
        removeGroupFilter() {
            this.groupsTarget = null
            this.groupingSelections = {...this.groupingSelections, ...this.emptySelections}
            this.applyGrouping()
        },
        applyGrouping() {
            this.selected.target = this.groupsTarget
            if (this.selected.target !== null) {
                const selectedKey = this.selected.targets[this.selected.target]
                this.$set(this.selected, selectedKey, this.groupingSelections[selectedKey])
            }
            this.groupingDialog = false
        },
        systemUsageClass(item) {
            if (!item.status || !item.status.type) return null
            return item.status.type.key
        },
        removeAllFilters() {
            this.activeFilters.form = { ...this.emptyFilters }
            this.applyFilters()
        },
        removeFilter({ filter }) {
            if (filter.type === 'filter') {
                this.activeFilters.form[filter.key] = null
            }
            else {
                this.activeFilters.selected[filter.type].splice(filter.index, 1)
            }

            this.applyFilters()
        },
        applyDelayedFilters() {
            // Fix for when hitting submit button while a text-field is focused
            this.filterLoading = true
            setTimeout(() => {
                this.filterLoading = false
                this.applyFilters()
            }, 250)
        },
        applyFilters() {
            this.filterDialog = false
            this.filter = Object.assign({}, this.filter, this.activeFilters.form)
            this.$emit('refreshed')
        },
        initEndpoints() {
            const endpointMap = idMap(this.endpoints)
            const newChecked = this.value.map(id => {
                if (typeof id == 'object') return id

                return endpointMap[id]
            })
            if (this.checked.length !== newChecked.length) {
                this.checked = newChecked
                return
            }
            if (
                this.checked.some((id, index) => {
                    return id !== newChecked[index]
                })
            ) {
                this.checked = newChecked
            }
        },
    }
}
</script>

<style lang="scss" scoped>
.v-expansion-panel-content.pa-0  {
    margin: 0 -24px;
}
</style>

<style lang="scss">
.v-data-table.footer-left .v-data-footer {
    justify-content: start;
}
</style>
