<template>
    <Page
        icon="mdi-calendar-star"
        :actions="[{ type: 'refresh', click: () => loadData() }]"
        :loading="loading"
    >
        <template v-slot:title>
            <h1 class="d-flex align-center">
                <span><translate>Kalendertjänster</translate></span>
                <v-chip
                    class="ml-4 font-weight-regular"
                    color="grey lighten-2"
                    small
                >
                    {{ $gettextInterpolate($gettext('%{count} tjänster'), { count: cloudAccounts.length, }) }}
                </v-chip>
            </h1>
        </template>
        <template v-slot:actions>
            <v-list-item-icon class="ma-0 align-self-center">
                <v-menu offset-y>
                    <template v-slot:activator="{ attrs, on }">
                        <v-btn
                            color="primary"
                            class="ml-2"
                            fab
                            small
                            :disabled="loading"
                            v-bind="attrs"
                            v-on="on"
                        >
                            <v-icon>mdi-plus</v-icon>
                        </v-btn>
                    </template>
                    <v-list>
                        <v-list-item
                            link
                            to="/setup/ews/"
                        >
                            <v-list-item-title>
                                <translate>Exchange Web Services</translate>
                            </v-list-item-title>
                        </v-list-item>
                        <v-list-item
                            link
                            to="/setup/msgraph/"
                        >
                            <v-list-item-title>
                                <translate>Microsoft Graph (Outlook 365)</translate>
                            </v-list-item-title>
                        </v-list-item>
                    </v-list>
                </v-menu>
            </v-list-item-icon>
        </template>
        <template v-slot:search>
            <v-form @submit.prevent="loadData()">
                <div class="d-flex align-center">
                    <v-text-field
                        v-model="search"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök tjänster') + '...'"
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
                :disabled="loading"
                :filters="filters"
                hide-close
                always-show-remove-all
                @click="filterDialog = true"
                @removeAllFilters="removeFilter"
            />
        </template>
        <template v-slot:content>
            <v-row v-if="loading">
                <v-col
                    v-for="item in 10"
                    :key="item"
                    md="12"
                    lg="6"
                    xl="4"
                >
                    <v-skeleton-loader
                        class="mx-auto"
                        max-width="600"
                        type="card"
                    />
                </v-col>
            </v-row>
            <v-alert
                v-else-if="!filteredCloudAccounts.length"
                type="info"
                text
            >
                <translate>Hittade inga resultat</translate>
            </v-alert>
            <v-alert
                v-else
                border="left"
                text
                type="info"
            >
                <v-row
                    align="center"
                    class="d-block d-sm-flex"
                >
                    <v-col class="grow">
                        <translate>Exchange sparar inte inbjudningsinformation i rumsresursers kalendrar som standard. Detta gör att uppringningsinformation inte går att läsa ut från resursadressens kalenderhändelser förrän det aktiveras.</translate>
                        &nbsp;<a
                            href="https://docs.microsoft.com/en-us/exchange/troubleshoot/client-connectivity/calendar-shows-organizer-name"
                            target="_blank"
                        >
                            <translate>Mer information hos microsoft.</translate>
                        </a>
                    </v-col>
                    <v-col class="shrink">
                        <v-dialog
                            scrollable
                            max-width="640"
                        >
                            <template v-slot:activator="{ on, bind }">
                                <v-btn
                                    color="primary"
                                    v-bind="bind"
                                    v-on="on"
                                >
                                    <translate>Se kommandon</translate>
                                </v-btn>
                            </template>
                            <calendar-power-shell-instructions />
                        </v-dialog>
                    </v-col>
                </v-row>
            </v-alert>

            <v-row>
                <v-col
                    v-for="cloud in filteredCloudAccounts"
                    :key="`cloud${cloud.type || ''}${cloud.id}`"
                    cols="12"
                    md="6"
                    xl="4"
                >
                    <v-card>
                        <v-progress-linear
                            color="pink"
                            :active="true"
                            :value="100"
                        />
                        <v-card-title>
                            {{ cloud.username || cloud.name }} ({{ cloud.typeTitle }})
                            <v-spacer />
                            <v-btn
                                color="primary"
                                icon
                                :href="cloud.editUrl"
                                onclick="return !window.open(this.href, 'cloud', 'width=1024,height=600')"
                                target="_blank"
                            >
                                <v-icon>mdi-pencil</v-icon>
                            </v-btn>
                        </v-card-title>
                        <v-divider />
                        <v-card-text>
                            <p class="mb-0">
                                <strong>{{ $ngettext('Kund', 'Kunder', 1) }}</strong> {{ cloud.customerTitle }}
                            </p>
                            <div
                                v-if="cloud.last_sync"
                                class="mt-4"
                            >
                                <translate>Senast synkroniserad:</translate>
                                {{ cloud.last_sync | timestamp }}
                            </div>
                            <v-tooltip
                                v-if="cloud.last_sync_errors"
                                bottom
                            >
                                <template v-slot:activator="{ on }">
                                    <v-icon v-on="on">
                                        mdi-alert
                                    </v-icon>
                                </template>
                                <span>{{ cloud.last_sync_errors }}</span>
                            </v-tooltip>
                        </v-card-text>
                        <v-divider />
                        <v-card-text>
                            <v-expansion-panels>
                                <v-expansion-panel>
                                    <v-expansion-panel-header><translate>Inställningar</translate></v-expansion-panel-header>
                                    <v-expansion-panel-content>
                                        <v-list
                                            dense
                                            style="margin:0 -24px;"
                                            class="pt-0"
                                        >
                                            <v-list-item-group
                                                color="primary"
                                            >
                                                <v-list-item
                                                    v-if="cloud.calendarsUrl"
                                                    :href="cloud.calendarsUrl"
                                                    onclick="return !window.open(this.href, 'cloud_calendar', 'width=1024,height=600')"
                                                    target="_blank"
                                                >
                                                    <v-list-item-icon>
                                                        <v-icon color="primary">
                                                            mdi-chevron-right
                                                        </v-icon>
                                                    </v-list-item-icon>
                                                    <v-list-item-content>
                                                        <v-list-item-title><translate>Hantera kalendrar</translate></v-list-item-title>
                                                    </v-list-item-content>
                                                </v-list-item>
                                                <v-list-item @click="synchronize(cloud)">
                                                    <v-list-item-icon>
                                                        <v-icon color="primary">
                                                            mdi-chevron-right
                                                        </v-icon>
                                                    </v-list-item-icon>
                                                    <v-list-item-content>
                                                        <v-list-item-title><translate>Synkronisera nu</translate></v-list-item-title>
                                                    </v-list-item-content>
                                                </v-list-item>
                                                <v-list-item
                                                    v-if="cloud.token_update_url"
                                                    :href="cloud.token_update_url"
                                                >
                                                    <v-list-item-icon>
                                                        <v-icon color="primary">
                                                            mdi-chevron-right
                                                        </v-icon>
                                                    </v-list-item-icon>
                                                    <v-list-item-content>
                                                        <v-list-item-title><translate>Uppdatera inloggning</translate></v-list-item-title>
                                                    </v-list-item-content>
                                                </v-list-item>
                                            </v-list-item-group>
                                        </v-list>
                                    </v-expansion-panel-content>
                                </v-expansion-panel>
                            </v-expansion-panels>
                        </v-card-text>
                    </v-card>
                </v-col>
            </v-row>

            <v-dialog
                v-model="filterDialog"
                scrollable
                max-width="300"
            >
                <v-card>
                    <v-card-title>{{ $ngettext('Kund', 'Kunder', 2) }}</v-card-title>
                    <v-divider />
                    <TreeView
                        v-model="filteredCustomers"
                        selectable
                        :label="$gettext('Sök kund')"
                        :items="customers"
                        :count-items="cloudAccounts"
                        count-items-key="customer"
                        item-text="title"
                        item-key="id"
                    />
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
        </template>
    </Page>
</template>

<script>
import {filterList} from '@/vue/helpers/store'
import {handleDjangoAdminPopup} from '@/vue/helpers/dialog'

import Page from '@/vue/views/layout/Page'

import TreeView from '@/vue/components/tree/TreeView'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'
import CalendarPowerShellInstructions from '@/vue/components/provider/CalendarPowerShellInstructions'

export default {
    name: 'CloudDashboard',
    components: {CalendarPowerShellInstructions, Page, TreeView, VBtnFilter },
    data() {
        return {
            selectedCustomers: [],
            customerSearch: '',
            search: '',
            loading: false,
            filteredCustomers: [],
            filterDialog: false,
        }
    },
    computed: {
        filters() {
            if (!this.selectedCustomers) {
                return []
            }

            const customers = this.$store.state.customer.customers
            return this.selectedCustomers.map(id => {
                return {
                    key: `customer_${id}`,
                    title: this.$ngettext('Kund', 'Kunder', 1),
                    value: customers[id].title,
                }
            })
        },
        customers() {
            return Object.values(this.$store.state.customer.customers)
        },
        settings() {
            return this.$store.state.site
        },
        cloudAccounts() {
            const customers = this.$store.state.site.customers
            return [
                ...Object.values(this.$store.state.provider.ewsCredentials).map(c => ({
                    ...c,
                    type: 'ews',
                    typeTitle: 'EWS',
                    editUrl: `/admin/exchange/ewscredentials/${c.id}?popup=1`,
                    calendarsUrl: `/admin/exchange/ewscredentials/${c.id}?popup=1#calendar_set-group`,
                    customerTitle: customers[c.customer] ? customers[c.customer].title : '',
                })),
                ...Object.values(this.$store.state.provider.msGraphCredentials).map(c => ({
                    ...c,
                    type: 'msgraph',
                    typeTitle: 'Graph',
                    editUrl: `/admin/msgraph/msgraphcredentials/${c.id}?popup=1`,
                    calendarsUrl: `/admin/msgraph/msgraphcredentials/${c.id}?popup=1#calendar_set-group`,
                    customerTitle: customers[c.customer] ? customers[c.customer].title : '',
                })),
            ]
        },
        filteredCloudAccounts() {
            let accounts = this.cloudAccounts

            if (this.selectedCustomers.length) {
                accounts = filterList(accounts, 'customer', this.selectedCustomers)
            }

            if (this.search) {
                accounts = accounts.filter(a => {
                    return JSON.stringify(a)
                        .toLowerCase()
                        .indexOf(this.search.toLowerCase()) != -1
                })
            }

            return accounts
        },
    },
    mounted() {
        return this.loadData()
    },
    methods: {
        applyFilters() {
            this.selectedCustomers = [...this.filteredCustomers]
            this.filterDialog = false
        },
        removeFilter() {
            this.filteredCustomers = []
            this.applyFilters()
        },
        loadData() {
            this.loading = true

            return Promise.all([
                this.$store.dispatch('customer/getCustomers'),
                this.$store.dispatch('provider/getExchangeCredentials'),
                this.$store.dispatch('provider/getMSGraphCredentials'),
            ]).then(result => {
                this.loading = false
                return result
            })
        },
        popup(ev, href, namespace) {
            if (handleDjangoAdminPopup(href, namespace, () => this.loadData())) {
                ev.preventDefault()
            }
        },
        async synchronize(cloud) {
            this.loading = true
            if (cloud.type == 'ews')
                await this.$store.dispatch('provider/syncExchangeCredentials', cloud.id)
            else if (cloud.type == 'msgraph')
                await this.$store.dispatch('provider/syncMSGraphCredentials', cloud.id)
            this.loading = false
        },
    },
}
</script>
