<template>
    <Page
        icon="mdi-server-network"
        :actions="[{ type: 'refresh', click: () => loadData() }]"
        :loading="loading"
    >
        <template v-slot:title>
            <h1 class="d-flex align-center">
                <span><translate>Videomötesbryggor</translate></span>
                <v-chip
                    class="ml-4 font-weight-regular"
                    color="grey lighten-2"
                    small
                >
                    {{ $gettextInterpolate($gettext('%{count} kluster'), { count: clusters.length }) }}
                </v-chip>
            </h1>
        </template>
        <template
            v-if="settings.enableCore"
            v-slot:actions
        >
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
                        to="/setup/cluster/?type=4"
                    >
                        <v-list-item-title>
                            <translate>Cisco Meeting Server</translate>
                        </v-list-item-title>
                    </v-list-item>
                    <v-list-item
                        link
                        to="/setup/call_control/?type=5"
                    >
                        <v-list-item-title>
                            <translate>VCS</translate>
                        </v-list-item-title>
                    </v-list-item>
                    <v-list-item
                        link
                        to="/setup/cluster/?type=6"
                    >
                        <v-list-item-title>
                            <translate>Pexip Infinity</translate>
                        </v-list-item-title>
                    </v-list-item>
                </v-list>
            </v-menu>
        </template>
        <template v-slot:search>
            <v-form @submit.prevent="loadData()">
                <div class="d-flex align-center">
                    <v-text-field
                        v-model="search"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök videomötesbrygga') + '...'"
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
                @click="filterDialog = true"
                @removeFilter="removeFilter"
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
                v-else-if="!clusters.length"
                type="info"
                text
            >
                <translate>Hittade inga resultat</translate>
            </v-alert>
            <v-row v-else>
                <v-col
                    v-for="cluster in clusters"
                    :key="`cluster${cluster.id}`"
                    cols="12"
                    md="6"
                    xl="4"
                >
                    <v-card>
                        <v-progress-linear
                            color="orange"
                            :active="true"
                            :value="100"
                        />
                        <v-card-title>
                            <span class="mr-4">{{ cluster.title }}</span>
                            <v-spacer />
                            <v-btn
                                color="primary"
                                icon
                                :href="`/admin/provider/cluster/${cluster.id}/change/`"
                                target="_blank"
                                @click="popup($event, `/admin/provider/cluster/${cluster.id}/change/?_popup=1`, 'cluster')"
                            >
                                <v-icon>mdi-pencil</v-icon>
                            </v-btn>
                            <v-btn
                                v-if="cluster.type === 'acano'"
                                :href="`/setup/cms/${cluster.id}/extend/`"
                                color="primary"
                                icon
                            >
                                <v-icon>mdi-plus</v-icon>
                            </v-btn>
                            <v-btn
                                v-else-if="cluster.type === 'vcs'"
                                :href="`/setup/vcs/${cluster.id}/`"
                                color="primary"
                                icon
                            >
                                <v-icon>mdi-plus</v-icon>
                            </v-btn>
                            <v-btn
                                v-else-if="cluster.type === 'pexip' && (!clusterProviders[cluster.id] || !clusterProviders[cluster.id].length)"
                                :href="`/setup/vcs/${cluster.id}/`"
                                color="primary"
                                icon
                            >
                                <v-icon>mdi-plus</v-icon>
                            </v-btn>
                        </v-card-title>
                        <v-divider />
                        <v-simple-table v-if="clusterProviders[cluster.id]">
                            <template v-slot:default>
                                <tbody>
                                    <tr
                                        v-for="provider in clusterProviders[cluster.id]"
                                        :key="`provider${provider.id}`"
                                    >
                                        <td>{{ provider.title }}</td>
                                        <td
                                            class="text-right"
                                            width="1"
                                        >
                                            <div class="d-flex">
                                                <v-btn
                                                    v-if="settings.perms.api"
                                                    class="ml-3"
                                                    :to="{
                                                        name: 'calls_list',
                                                        query: { provider: provider.id },
                                                    }"
                                                    icon
                                                    :title="$gettext('Möten')"
                                                >
                                                    <v-icon>mdi-google-classroom</v-icon>
                                                </v-btn>
                                                <v-btn
                                                    v-if="settings.perms.api"
                                                    class="ml-3"
                                                    :to="{
                                                        name: 'rest_client',
                                                        query: { provider: provider.id },
                                                    }"
                                                    icon
                                                    title="API"
                                                >
                                                    <v-icon>mdi-package-variant-closed</v-icon>
                                                </v-btn>
                                                <v-btn
                                                    v-if="provider.web_admin"
                                                    :href="provider.web_admin"
                                                    class="ml-3"
                                                    target="_blank"
                                                    icon
                                                    :title="$gettext('Webadmin')"
                                                >
                                                    <v-icon>mdi-iframe</v-icon>
                                                </v-btn>
                                                <v-btn
                                                    icon
                                                    :href="`/admin/provider/provider/${provider.id}/change/`"
                                                    class="ml-3"
                                                    target="_blank"
                                                    @click="popup($event, `/admin/provider/provider/${provider.id}/change/?_popup=1`, 'provider')"
                                                >
                                                    <v-icon>mdi-pencil</v-icon>
                                                </v-btn>
                                            </div>
                                        </td>
                                    </tr>
                                </tbody>
                            </template>
                        </v-simple-table>
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
                                                <!-- TODO: wrong url -->
                                                <template v-if="cluster.type === 'acano'">
                                                    <v-list-item :href="`/core/admin/tenants/?provider=${cluster.id}`">
                                                        <v-list-item-icon>
                                                            <v-icon color="primary">
                                                                mdi-chevron-right
                                                            </v-icon>
                                                        </v-list-item-icon>
                                                        <v-list-item-content>
                                                            <v-list-item-title><translate>Hantera tenants</translate></v-list-item-title>
                                                        </v-list-item-content>
                                                    </v-list-item>
                                                </template>
                                                <template v-if="cluster.type === 'pexip'">
                                                    <v-list-item :href="`/admin/customer/customermatch/?cluster__id__exact=${cluster.id}`">
                                                        <v-list-item-icon>
                                                            <v-icon color="primary">
                                                                mdi-chevron-right
                                                            </v-icon>
                                                        </v-list-item-icon>
                                                        <v-list-item-content>
                                                            <v-list-item-title><translate>Kundmatchning</translate></v-list-item-title>
                                                        </v-list-item-content>
                                                    </v-list-item>
                                                    <v-list-item :to="{ name: 'policy_rules', query: { provider: cluster.id } }">
                                                        <v-list-item-icon>
                                                            <v-icon color="primary">
                                                                mdi-chevron-right
                                                            </v-icon>
                                                        </v-list-item-icon>
                                                        <v-list-item-content>
                                                            <v-list-item-title><translate>Call routing-regler</translate></v-list-item-title>
                                                        </v-list-item-content>
                                                    </v-list-item>
                                                    <v-list-item :href="`/admin/policy/clusterpolicy/?cluster__id__exact=${cluster.id}`">
                                                        <v-list-item-icon>
                                                            <v-icon color="primary">
                                                                mdi-chevron-right
                                                            </v-icon>
                                                        </v-list-item-icon>
                                                        <v-list-item-content>
                                                            <v-list-item-title><translate>Policy-inställningar</translate></v-list-item-title>
                                                        </v-list-item-content>
                                                    </v-list-item>
                                                </template>
                                            </v-list-item-group>
                                        </v-list>
                                        <ClipboardInput
                                            v-if="cluster.cdr_url"
                                            :label="$gettext('CDR/eventsink-url')"
                                            :value="cluster.cdr_url"
                                        />
                                        <ClipboardInput
                                            v-if="cluster.policy_url"
                                            :label="$gettext('Policy url')"
                                            :value="cluster.policy_url"
                                        />
                                    </v-expansion-panel-content>
                                </v-expansion-panel>
                            </v-expansion-panels>
                        </v-card-text>
                    </v-card>
                </v-col>
            </v-row>

            <v-dialog
                v-model="filterDialog"
                max-width="320"
            >
                <v-card>
                    <v-card-title><translate>Filtrera</translate></v-card-title>
                    <v-divider />
                    <v-card-text>
                        <v-radio-group
                            v-model="filterProviderType"
                            class="mb-0"
                            hide-details
                        >
                            <v-radio
                                :value="0"
                                :label="$gettext('Alla')"
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
        </template>
    </Page>
</template>

<script>
import { handleDjangoAdminPopup } from '@/vue/helpers/dialog'
import { $gettext } from '@/vue/helpers/translate'
import { groupList } from '@/vue/helpers/store'

import Page from '@/vue/views/layout/Page'

import ClipboardInput from '@/vue/components/ClipboardInput'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'

export default {
    name: 'ProviderDashboard',
    components: { Page, ClipboardInput, VBtnFilter },
    data() {
        return {
            providerType: 0,
            search: '',
            loading: false,
            filterProviderType: 0,
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
            selectedClusters: [],
            customerSearch: '',
        }
    },
    computed: {
        filters() {
            if (!this.providerType) {
                return []
            }

            return [{
                key: this.providerType,
                title: $gettext('Typ'),
                value: this.filterTypes.find(f => f.value === this.providerType).title
            }]
        },
        settings() {
            return this.$store.state.site
        },
        clusters() {
            return Object.values(this.$store.state.provider.clusters).map(c => ({ ...c })).filter(c => {
                if (this.providerType && this.providerType !== c.type) {
                    return false
                }

                return JSON.stringify(c)
                    .toLowerCase()
                    .indexOf(this.search.toLowerCase()) != -1

            })
        },
        providers() {
            return Object.values(this.$store.state.provider.providers)
        },
        clusterProviders() {
            return groupList(this.providers, 'cluster')
        },
    },
    mounted() {
        return this.loadData()
    },
    methods: {
        applyFilters() {
            this.providerType = this.filterProviderType
            this.filterDialog = false
        },
        removeFilter() {
            this.filterProviderType = 0
            this.applyFilters()
        },
        loadData() {
            this.loading = true

            return Promise.all([
                this.$store.dispatch('provider/getClusters'),
                this.$store.dispatch('provider/getProviders'),
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
    },
}
</script>

