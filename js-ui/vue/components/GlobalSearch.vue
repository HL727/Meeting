<template>
    <v-dialog
        v-model="show"
        persistent
        :z-index="99990"
        max-width="60rem"
        content-class="align-self-start"
    >
        <v-card light>
            <v-card-title class="py-4">
                <div>
                    <CustomerPicker
                        v-if="customers.length > 1"
                        prepend-icon="mdi-domain"
                        navigate
                        dense
                        flat
                        solo
                        :outlined="true"
                        :hide-details="true"
                        class="mr-4"
                        :queries="{ globalSearch: search }"
                    />
                </div>
                <v-text-field
                    ref="globalSearchField"
                    v-model="search"
                    :label="$gettext('Sök...')"
                    solo
                    hide-details
                    dense
                    flat
                    outlined
                    clearable
                    prepend-inner-icon="mdi-magnify"
                />
                <v-select
                    v-model="searchLimit"
                    :items="[3, 5, 10]"
                    :hide-details="true"
                    dense
                    outlined
                    class="align-center mx-4"
                    style="max-width:6rem;"
                    @change="searchDebounce"
                />
                <v-btn
                    color="primary"
                    class="ml-2"
                    fab
                    small
                    outlined
                    @click="closeSearch"
                >
                    <v-icon>mdi-close</v-icon>
                </v-btn>
            </v-card-title>

            <v-divider />
            <div style="position:relative;">
                <v-progress-linear
                    :active="searchDebounceLoading || searchLoading"
                    indeterminate
                    absolute
                    top
                />
            </div>

            <v-card-text
                v-if="(searchDebounceLoading || searchLoading) && search"
                class="grey lighten-4 text-center pt-4"
            >
                <translate>Söker efter</translate> "{{ search }}"...
            </v-card-text>
            <v-card-text
                v-else-if="search"
                height="40rem"
                class="grey lighten-4 pt-4"
            >
                <v-row>
                    <v-col
                        v-for="result in searchResults"
                        :key="result.label"
                        cols="4"
                        class="d-flex"
                    >
                        <v-card
                            class="align-self-stretch"
                            width="100%"
                            :style="{opacity: result.response && result.response.results.length > 0 ? 1 : 0.5}"
                        >
                            <v-card-text>
                                <p class="overline grey--text mb-0">
                                    <v-icon
                                        color="primary"
                                        size="30"
                                        class="mr-2"
                                    >
                                        {{ result.icon }}
                                    </v-icon>
                                    {{ result.label }}
                                </p>
                            </v-card-text>
                            <v-divider />
                            <template v-if="result.response && result.response.results.length > 0">
                                <v-list
                                    dense
                                    class="py-0"
                                >
                                    <v-list-item-group>
                                        <v-list-item
                                            v-for="item in result.response.results"
                                            :key="item.id"
                                            two-line
                                            @click="item.href ? closeSearchHref(item.href) : closeSearchTo(item.to)"
                                        >
                                            <v-list-item-content>
                                                <v-list-item-title>{{ item.listTitle }}</v-list-item-title>
                                                <v-list-item-subtitle>{{ item.listInfo }}</v-list-item-subtitle>
                                            </v-list-item-content>
                                        </v-list-item>
                                    </v-list-item-group>
                                </v-list>
                                <v-card-actions>
                                    <v-btn
                                        v-if="result.response.count > searchLimit"
                                        color="primary"
                                        text
                                        @click="closeSearchTo(result.to)"
                                    >
                                        <translate :translate-params="{count: result.response.count}">
                                            Visa alla - %{count}
                                        </translate>
                                    </v-btn>
                                </v-card-actions>
                            </template>
                            <v-card-text v-else>
                                <translate>Inga träffar</translate>
                            </v-card-text>
                        </v-card>
                    </v-col>
                </v-row>
            </v-card-text>
            <v-card-text
                v-else
                class="grey lighten-4 text-center pt-4"
            >
                <translate>Ange sökfras ovan</translate>
            </v-card-text>
        </v-card>
    </v-dialog>
</template>

<script>
import { defaultFilter } from '@/vue/helpers/vue'

import { $gettext } from '@/vue/helpers/translate'
import { replaceQuery } from '@/vue/helpers/url'

import CustomerPicker from '@/vue/components/tenant/CustomerPicker'
import { nowSub } from '@/vue/helpers/datetime'

export default {
    components: { CustomerPicker },
    props: {
        value: { type: Boolean, default: false }
    },
    data() {
        return {
            search: '',
            searchLoading: false,
            searchDebounceLoading: false,
            searchLimit: 3,
            searchResponse: {},
            searchTimeout: null,
        }
    },
    computed: {
        show: {
            get() {
                return this.value
            },
            set(value) {
                this.$emit('input', value)
            }
        },
        isPexip() {
            return this.$store.state.site.isPexip
        },
        customers() {
            return Object.values(this.$store.state.site.customers || {})
        },
        settings() {
            return this.$store.state.site || {}
        },
        // eslint-disable-next-line max-lines-per-function
        searchTypes() {
            return {
                endpoints: {
                    label: this.$ngettext('System', 'System', 2),
                    icon: 'mdi-dns-outline',
                    labelKey: 'title',
                    infoKey: 'info',
                    show: this.settings.enableEPM,
                    route: {
                        all: 'epm_list',
                        searchKey: 'search',
                        single: 'endpoint_details'
                    }
                },
                users: {
                    label: $gettext('Användare'),
                    icon: 'mdi-account-multiple',
                    labelKey: 'name',
                    infoKey: this.isPexip ? 'email' : 'jid',
                    show: this.settings.enableCore,
                    route: {
                        all: 'user_list',
                        searchKey: 'user_id',
                        single: 'user_details'
                    }
                },
                cospaces: {
                    label: this.$ngettext('Mötesrum', 'Mötesrum', 2),
                    icon: 'mdi-door-closed',
                    labelKey: 'name',
                    infoKey: this.isPexip ? 'sip_uri' : 'uri',
                    show: this.settings.enableCore,
                    route: {
                        all: 'cospaces_list',
                        searchKey: 'cospace_id',
                        single: 'cospaces_details'
                    }
                },
                tenants: {
                    label: this.$ngettext('Kund', 'Kunder', 2),
                    icon: 'mdi-domain',
                    labelKey: 'title',
                    infoKey: 'info',
                    show: this.customers.length > 1,
                    route: {
                        query: { key: 'customer', itemKey: 'id' },
                        all: this.settings.enableCore ? 'customer_dashboard' : 'epm_customer_dashboard',
                        searchKey: 'search',
                    }
                },
                meetings: {
                    label: $gettext('Bokade möten'),
                    icon: 'mdi-calendar',
                    labelKey: 'title',
                    infoKey: 'creator',
                    show: this.settings.enableCore,
                    route: {
                        all: 'meetings_list',
                        searchKey: 'meeting_id',
                        single: 'calls_details'
                    }
                },
                calls: {
                    label: $gettext('Möten'),
                    icon: 'mdi-google-classroom',
                    labelKey: 'name',
                    infoKey: 'start_time',
                    show: this.settings.enableCore,
                    route: this.isPexip ? {
                        all: 'calls_list',
                        searchKey: 'call_id',
                        single: 'call_details_pexip'
                    } : {
                        all: 'calls_list',
                        searchKey: 'call_id',
                        single: 'calls_details'
                    }
                },
            }
        },
        mappedRoomSystems() {
            return this.$store.getters['endpoint/endpoints'].filter(endpoint => {
                return ['title', 'sip', 'h323', 'h323_e164', 'ip', 'product_name', 'notifiers'].some(v => {
                    return defaultFilter(endpoint[v], this.search, null)
                })
            }).map(endpoint => {
                return {
                    ...endpoint,
                    info: endpoint.sip || endpoint.h323 || endpoint.h323_e164 || endpoint.ip
                }
            })
        },
        mappedTenants() {
            const clusters = this.$store.state.provider.clusters

            return Object.values(this.$store.state.customer.customers).map(t => {
                const cluster = (t.mcu_provider in clusters) ? clusters[t.mcu_provider].title : ''

                return {
                    ...t,
                    info: cluster,
                    cluster: cluster,
                }
            }).filter(t => {
                return ['title', 'pexip_tenant_id', 'acano_tenant_id', 'cluster'].some(v => {
                    return defaultFilter(t[v], this.search, null)
                })
            })
        },
        mappedSearchResponses() {
            const searchResponses = { ...this.searchResponse }

            if (this.settings.enableEPM) {
                const endpoints = this.mappedRoomSystems
                searchResponses['endpoints'] = {
                    results: endpoints.slice(0, this.searchLimit),
                    count: endpoints.length
                }
            }

            if (this.customers.length > 1) {
                const tenants = this.mappedTenants
                searchResponses['tenants'] = {
                    results: tenants.slice(0, this.searchLimit),
                    count: tenants.length,
                }
            }

            return searchResponses
        },
        searchResults() {
            if (!this.search) return []

            return Object.entries(this.searchTypes).filter(r => r[1].show).map(r => {
                const itemKey = r[0]
                const itemResult = r[1]
                const response = this.mappedSearchResponses[itemKey]

                if (!response || !response.results) {
                    return { ...itemResult, response }
                }
                response.results = response.results.map(item => {
                    return {
                        listTitle: item[itemResult.labelKey],
                        listInfo: item[itemResult.infoKey],
                        href: !itemResult.route.query ? null : {
                            [itemResult.route.query.key]: item[itemResult.route.query.itemKey]
                        },
                        to: item.details_url ? item.details_url : {
                            name: itemResult.route.single,
                            params: { id: item.id }
                        },
                        ...item
                    }
                })

                return {
                    to: {
                        name: itemResult.route.all,
                        query: { [itemResult.route.searchKey]: this.search }
                    },
                    ...itemResult,
                    response
                }
            })
        },

    },
    watch: {
        search(newValue) {
            if (newValue) {
                setTimeout(() => {
                    if (this.$refs.globalSearchField) {
                        this.$refs.globalSearchField.$refs.input.focus()
                    }
                }, 10)
                this.searchDebounce()
            }
        },
    },
    methods: {
        searchDebounce() {
            clearTimeout(this.searchTimeout)
            this.searchDebounceLoading = true

            this.searchTimeout = setTimeout(() => {
                if (this.searchLoading) {
                    this.searchDebounce()
                }
                else {
                    this.searchTimeout = null
                    this.newSearch()
                }
            }, 500)
        },
        closeSearchHref(query) {
            location.href = replaceQuery(location.href, query)
        },
        closeSearchTo(to) {
            this.closeSearch()
            this.$router.push(to).catch(() => {})
        },
        closeSearch() {
            this.search = ''
            this.show = false
        },
        searchCore() {
            if (!this.settings.enableCore) {
                return Promise.resolve()
            }

            return Promise.all([
                this.$store.dispatch('cospace/search', {
                    search: this.search,
                    limit: this.searchLimit
                }),
                this.$store.dispatch('user/search', {
                    search: this.search,
                    limit: this.searchLimit
                }),
                this.$store.dispatch('meeting/search', {
                    limit: this.searchLimit,
                    title: this.search,
                    ts_start: nowSub({ hours: 1 }),
                }),
                this.$store.dispatch('call/getCalls', {
                    limit: this.searchLimit,
                    search: this.search,
                })
            ]).then(values => {
                this.searchResponse.cospaces = values[0]
                this.searchResponse.users = values[1]
                this.searchResponse.meetings = values[2]
                this.searchResponse.calls = values[3]
            })
        },
        searchRooms() {
            if (!this.settings.enableEPM) {
                return Promise.resolve()
            }

            return this.$store.dispatch('endpoint/getEndpoints')
        },
        searchShared() {
            return Promise.all([
                this.$store.dispatch('customer/getCustomers'),
                this.$store.dispatch('provider/getClusters')
            ])
        },
        newSearch() {
            this.searchLoading = true

            return Promise.all([
                this.searchCore(),
                this.searchRooms(),
                this.searchShared()
            ]).then(() => {
                if (this.searchTimeout) {
                    this.searchLoading = false
                    return
                }

                this.searchLoading = false
                this.searchDebounceLoading = false
            })
        },
    }
}
</script>
