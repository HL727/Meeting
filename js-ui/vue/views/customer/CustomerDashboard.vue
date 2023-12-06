<template>
    <Page
        icon="mdi-domain"
        :actions="[
            { type: 'refresh', click: () => loadData() }
        ]"
    >
        <template v-slot:actions>
            <v-list-item-icon class="ma-0 align-self-center">
                <v-tooltip bottom>
                    <template v-slot:activator="{ on, attrs }">
                        <v-btn
                            class="ml-2"
                            href="/admin/provider/customer/add/?_popup=1"
                            fab
                            small
                            color="primary"
                            v-bind="attrs"
                            v-on="on"
                            @click.native="popup($event, '/admin/provider/customer/add/?_popup=1')"
                        >
                            <v-icon>mdi-plus</v-icon>
                        </v-btn>
                    </template>
                    <span><translate>Lägg till</translate></span>
                </v-tooltip>
            </v-list-item-icon>
        </template>
        <template v-slot:title>
            <h1 class="d-flex align-center">
                <span><translate>Kunder</translate></span>
                <v-chip
                    class="ml-4 font-weight-regular"
                    color="grey lighten-2"
                    small
                >
                    {{ $gettextInterpolate($gettext('%{count} totalt'), { count: customers.length }) }}
                </v-chip>
            </h1>
        </template>
        <template v-slot:search>
            <v-form @submit.prevent="loadData()">
                <div class="d-flex align-center">
                    <v-text-field
                        v-model="customerSearch"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök kund') + '...'"
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
        <template v-slot:filter>
            <VBtnFilter
                class="ml-4 d-xl-none"
                icon="mdi-dns"
                :text="$ngettext('Kluster', 'Kluster', 2)"
                :disabled="loading"
                :filters="activeClusters"
                :show-remove-all="true"
                :style="filterButtonStyle"
                @click="clusterDialog = true"
                @removeFilter="removeFilter"
                @removeAllFilters="removeAllClusters"
            />
            <VBtnFilter
                class="ml-2"
                :disabled="loading"
                :filters="activeFilters"
                :show-remove-all="true"
                :style="filterButtonStyle"
                @click="filterDialog = true"
                @removeFilter="removeFilter"
                @removeAllFilters="removeAllFilters"
            />
        </template>

        <v-row>
            <v-col
                cols="3"
                class="d-none d-xl-block"
            >
                <p class="overline mt-2 mb-3">
                    {{ $ngettext('Kluster', 'Kluster', 2) }}
                </p>
                <v-card outlined>
                    <TreeView
                        v-model="selectedClusters"
                        selectable
                        :label="$gettext('Sök kluster')"
                        :items="clustersWithLinks"
                        :count-items="customers"
                        count-items-key="mcu_provider"
                        show-empty
                        item-text="title"
                        item-key="id"
                    >
                        <template v-slot:append="{ item }">
                            <span class="grey--text">{{ item.totalCount ? `(${item.totalCount})` : '' }}</span>
                            <v-btn
                                icon
                                :href="item.popup ? item.addLink : undefined"
                                :to="item.popup ? undefined : item.addLink"
                                @click.native="item.popup ? popup($event, item.addLink) : () => true"
                            >
                                <v-icon>mdi-plus</v-icon>
                            </v-btn>
                        </template>
                    </TreeView>
                </v-card>
            </v-col>
            <v-col
                cols="12"
                xl="9"
            >
                <ErrorMessage :error="error" />

                <v-data-table
                    :items="activeCustomers"
                    :headers="customerHeaders"
                    :search="customerSearch"
                    :loading="loading"
                >
                    <template v-slot:item.title="{ item }">
                        <strong><a :href="`/?customer=${item.id}`">{{ item.title }}</a></strong>
                    </template>
                    <template v-slot:item.actions="{ item }">
                        <v-btn
                            icon
                            :href="`/admin/provider/customer/${item.id}/change/#customermatch_set-group`"
                        >
                            <v-icon>mdi-pencil</v-icon>
                        </v-btn>
                    </template>
                    <template v-slot:item.cluster.title="{ item }">
                        <template v-if="item.cluster">
                            {{ item.cluster.title || '-' }}
                            <small
                                v-if="item.acano_tenant_id || item.pexip_tenant_id"
                                class="d-flex grey--text"
                                style="white-space: nowrap;"
                            >
                                <strong>{{ (item.acano_tenant_id || item.pexip_tenant_id || '').substr(0, 8) }}</strong>
                                <span>{{ (item.acano_tenant_id || item.pexip_tenant_id || '').slice(8) }}</span>
                            </small>
                        </template>
                    </template>
                    <template v-slot:item.usage.endpoints="{ item }">
                        <a
                            v-if="item.usage.endpoints"
                            target="_top"
                            :href="$router.resolve({ name: 'epm_list', query: { customer: item.id } }).href"
                        >{{ item.usage.endpoints }}
                        </a>
                    </template>
                    <template v-slot:item.usage.endpoint_proxies="{ item }">
                        <a
                            v-if="item.usage.endpoint_proxies"
                            target="_top"
                            :href="$router.resolve({ name: 'epm_proxies', query: { customer: item.id } }).href"
                        >{{ item.usage.endpoint_proxies }}
                        </a>
                    </template>
                    <template v-slot:item.usage.meetings="{ item }">
                        <a
                            v-if="item.usage.meetings"
                            target="_top"
                            :href="$router.resolve({ name: 'meetings_list', query: { customer: item.id } }).href"
                        >{{ item.usage.meetings }}
                        </a>
                    </template>
                    <template v-slot:item.usage.cospaces="{ item }">
                        <a
                            v-if="item.usage.cospaces"
                            target="_top"
                            :href="$router.resolve({ name: 'cospaces_list', query: { customer: item.id } }).href"
                        >{{ item.usage.cospaces }}
                        </a>
                    </template>
                    <template v-slot:item.usage.address_books="{ item }">
                        <a
                            v-if="item.usage.address_books"
                            target="_top"
                            :href="$router.resolve({ name: 'addressbook_list', query: { customer: item.id } }).href"
                        >{{ item.usage.address_books }}
                        </a>
                    </template>
                    <template v-slot:item.usage.admin_users="{ item }">
                        <a
                            v-if="item.usage.admin_users"
                            :href="`/admin/auth/user/?customer__id__exact=${item.id}`"
                        >{{ item.usage.admin_users }}</a>
                    </template>
                    <template v-slot:item.usage.matches="{ item }">
                        <a
                            v-if="item.usage.matches"
                            :href="`/admin/provider/customer/${item.id}/change/#customermatch_set-group`"
                        >{{ item.usage.matches }}</a>
                    </template>
                </v-data-table>

                <v-dialog
                    v-model="clusterDialog"
                    scrollable
                    max-width="420"
                >
                    <v-card>
                        <v-card-title>
                            {{ $ngettext('Kluster', 'Kluster', 2) }}
                        </v-card-title>
                        <v-divider />
                        <v-card-text>
                            <TreeView
                                v-model="filterSelectedClusters"
                                selectable
                                :label="$gettext('Sök kluster')"
                                :items="clustersWithLinks"
                                :count-items="customers"
                                count-items-key="mcu_provider"
                                show-empty
                                item-text="title"
                                item-key="id"
                                style="margin: 0 -16px;"
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

                <v-dialog
                    v-model="filterDialog"
                    scrollable
                    max-width="320"
                >
                    <v-card>
                        <v-card-title><translate>Filtrera</translate></v-card-title>
                        <v-divider />
                        <v-card-text class="pt-4">
                            <p class="overline">
                                <translate>Typ</translate>
                            </p>

                            <v-radio-group v-model="filterProviderType">
                                <v-radio
                                    :value="0"
                                    :label="$gettext('Alla typer')"
                                />
                                <v-radio
                                    v-for="clusterType in filterTypes"
                                    :key="clusterType.value"
                                    :value="clusterType.value"
                                    :label="clusterType.title"
                                />
                            </v-radio-group>
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
            </v-col>
        </v-row>
    </Page>
</template>

<script>
import { $gettext, $ngettext } from '@/vue/helpers/translate'
import { globalEmit } from '@/vue/helpers/events'

import Page from '@/vue/views/layout/Page'

import TreeView from '@/vue/components/tree/TreeView'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import { handleDjangoAdminPopup } from '@/vue/helpers/dialog'

export default {
    name: 'CustomerProviderDashboard',
    components: { Page, TreeView, VBtnFilter, ErrorMessage },
    data() {
        return {
            providerType: 0,
            selectedClusters: [],
            customerSearch: (this.$route.query.search || ''),
            loading: false,
            filterProviderType: 0,
            filterSelectedClusters: [],
            filterDialog: false,
            filterTypes: [
                {
                    value: 'pexip',
                    title: $gettext('Pexip'),
                },
                {
                    value: 'acano',
                    title: $gettext('Cisco Meeting Server'),
                }
            ],
            clusterDialog: false,
            error: null,
        }
    },
    computed: {
        activeClusters() {
            return this.selectedClusters.map(c => {
                const cluster = this.clusters.find(clusterItem => clusterItem.id === c) || {
                    id: c,
                    value: this.$gettext('Okänd'),
                }
                return {
                    key: cluster.id,
                    title: this.$ngettext('Kluster', 'Kluster', 1),
                    value: cluster.title,
                }
            })
        },
        activeFilters() {
            if (!this.selectedClusters.length && !this.providerType) {
                return []
            }

            return this.providerType ? [{
                key: 'provider',
                title: $gettext('Typ'),
                value: this.filterTypes.find(f => f.value === this.providerType).title
            }] : []
        },
        customerHeaders() {
            return [
                { text: $gettext('Namn'), value: 'title' },
                { text: '', value: 'actions', width: 5 },
                { text: this.$ngettext('Kluster', 'Kluster', 1), value: 'cluster.title' },
                ...(this.settings.enableEPM
                    ? [
                        { text: $gettext('Endpoints'), value: 'usage.endpoints', width: 5 },
                        { text: $gettext('Proxyklienter'), value: 'usage.endpoint_proxies', width: 5 },
                        { text: $gettext('Adressböcker'), value: 'usage.address_books', width: 5 },
                    ] : []
                ),
                ...(this.settings.enableCore
                    ? [
                        { text: $gettext('Möten'), value: 'usage.meetings', width: 5 },
                        { text: $ngettext('Mötesrum', 'Mötesrum', 2), value: 'usage.cospaces', width: 5 },
                        { text: $gettext('Matchningsregler'), value: 'usage.matches', width: 5 },
                    ] : []
                ),
                { text: $gettext('Adminanvändare'), value: 'usage.admin_users', width: 5 },
            ]
        },
        customers() {
            const clusters = this.$store.state.provider.clusters
            return Object.values(this.$store.state.customer.customers).map(c => {
                return {
                    usage: {},
                    ...c,
                    cluster: clusters[c.mcu_provider],
                }
            })
        },
        settings() {
            return this.$store.state.site
        },
        clusters() {
            return Object.values(this.$store.state.provider.clusters).map(c => ({ ...c }))
        },
        clustersWithLinks() {
            return this.clusters.map(cluster => {
                let addLink = `/admin/provider/customer/add/?_popup=1&cluster=${cluster.id}&clustersettings_set-cluster=${cluster.id}&lifesize_provider=${cluster.id}`
                let popup = true
                if (cluster.type === 'acano') {
                    addLink = `/core/admin/tenants/?provider=${cluster.id}`
                    popup = false
                }
                return {
                    ...cluster,
                    addLink,
                    popup,
                }
            })
        },
        activeCustomers() {
            return this.customers.filter(c => {
                if (this.selectedClusters.length && this.selectedClusters.indexOf(c.mcu_provider) === -1) {
                    return false
                }
                if (this.providerType && (!c.cluster || this.providerType !== c.cluster.type)) {
                    return false
                }
                return true
            })
        },
        filterButtonStyle() {
            return this.$vuetify.breakpoint.mdAndUp ?
                { maxWidth: '40rem' } : null
        },
    },
    mounted() {
        return this.loadData()
    },
    methods: {
        applyFilters() {
            this.selectedClusters = [ ...this.filterSelectedClusters ]
            this.providerType = this.filterProviderType
            this.filterDialog = false
            this.clusterDialog = false
        },
        removeAllClusters() {
            this.filterSelectedClusters = []
            this.applyFilters()
        },
        removeAllFilters() {
            this.filterProviderType = 0
            this.applyFilters()
        },
        removeFilter({ filter }) {
            if (filter.key === 'provider') {
                this.filterProviderType = 0
            }
            else {
                this.$delete(this.filterSelectedClusters, this.filterSelectedClusters.indexOf(filter.key))
            }
            this.applyFilters()
        },
        dataLoaded() {
            this.loading = false
            globalEmit(this, 'loading', false)
        },
        loadData() {
            this.loading = true
            this.error = null

            return Promise.all([
                this.$store.dispatch('customer/getCustomers'),
                this.$store.dispatch('provider/getClusters')
            ]).then(() => {
                this.dataLoaded()
            }).catch(e => {
                this.dataLoaded()
                this.error = e
            })
        },
        popup(ev, href) {
            if (handleDjangoAdminPopup(href, 'customer', () => this.loadData())) {
                ev.preventDefault()
            }
        }
    },
}
</script>
