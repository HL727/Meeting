<template>
    <v-dialog
        v-model="dialog"
        scrollable
        max-width="320"
    >
        <template v-slot:activator="{ on }">
            <VBtnFilter
                v-show="isVisible"
                :filters="filters"
                :hide-close="true"
                icon="mdi-eye"
                :text="$gettext('Visa för')"
                :disabled="loading"
                :load-indicator="clustersLoading"
                v-on="on"
            />
        </template>

        <v-card>
            <v-card-title>{{ title }}</v-card-title>
            <v-divider />
            <v-card-text class="pt-4">
                <template v-if="!hideCustomer">
                    <p
                        v-if="customersCount > 1"
                        class="overline"
                    >
                        <translate>Aktuell kund</translate>
                    </p>

                    <v-radio-group v-model="filterProvider">
                        <v-radio
                            :value="0"
                            :label="customersCount > 1 ? customer.title : $gettext('Standard')"
                        />
                    </v-radio-group>
                </template>

                <p
                    v-if="onlyClusters"
                    class="overline mb-0"
                >
                    {{ $ngettext('Kluster', 'Kluster', 1) }}
                </p>
                <p
                    v-else
                    class="overline mb-0"
                >
                    <translate>Kluster eller brygga</translate>
                </p>

                <v-text-field
                    v-model="search"
                    prepend-inner-icon="mdi-magnify"
                    :placeholder="$gettext('Sök') + '...'"
                />

                <div v-if="onlyClusters">
                    <v-radio-group
                        v-model="filterProvider"
                        class="mt-0"
                    >
                        <v-radio
                            v-for="cluster in clusters"
                            :key="'cluster' + cluster.id"
                            :value="cluster.id"
                            :label="cluster.title"
                            @change="provider = cluster.id"
                        />
                    </v-radio-group>
                </div>

                <v-expansion-panels
                    v-else
                    v-model="panel"
                >
                    <v-expansion-panel
                        v-for="cluster in clusters"
                        :key="'cluster' + cluster.id"
                        @change="provider = cluster.id"
                    >
                        <v-expansion-panel-header>
                            {{ cluster.title }}
                        </v-expansion-panel-header>
                        <v-expansion-panel-content>
                            <v-radio-group v-model="filterProvider">
                                <v-radio
                                    :label="$gettext('Hela klustret')"
                                    :value="cluster.id"
                                />
                                <template v-if="cluster.type !== 'vcs'">
                                    <v-radio
                                        v-for="provider in cluster.providers"
                                        :key="'provider' + provider.id"
                                        :label="provider.title"
                                        :value="provider.id"
                                    >
                                        {{ provider.title }}
                                    </v-radio>
                                </template>
                            </v-radio-group>
                        </v-expansion-panel-content>
                    </v-expansion-panel>
                </v-expansion-panels>
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

<script>
import { $gettext } from '@/vue/helpers/translate'

import VBtnFilter from '@/vue/components/filtering/VBtnFilter'

export default {
    name: 'VBtnFilterProvider',
    components: { VBtnFilter },
    props: {
        title: { type: String, default: ''},
        value: { type: [Number, Object], default: 0 },
        loading: { type: Boolean, default: false },
        hideCustomer: { type: Boolean, default: false },
        providerTypes: { type: Array, default: () => ['acano', 'pexip'] },
        onlyClusters: { type: Boolean, default: false },
        returnObject: { type: Boolean, default: false }
    },
    data() {
        const activeProvider = typeof this.value === 'number' ? this.value : this.value.id

        return {
            dialog: false,
            filterProvider: activeProvider,
            provider: activeProvider,
            clustersLoading: true,
            search: '',
            panel: null
        }
    },
    computed: {
        isVisible() {
            if (!this.isAdmin) {
                return false
            }

            if (this.onlyClusters && (this.customersCount <= 1 || this.clusters.length <= 1)) {
                return false
            }

            if (this.allBridges.length <= 1) {
                return false
            }

            return true
        },
        isAdmin() {
            const settings = this.$store.getters['settings']
            return settings.perms.admin
        },
        customers() {
            return this.$store.state.site.customers
        },
        customersCount() {
            return Object.keys(this.customers).length
        },
        customer() {
            return this.customers[this.$store.state.site.customerId] || {}
        },
        clusters() {
            const enableTypes = this.providerTypes

            let clusters = Object.values(this.$store.state.provider.clusters).filter(c => enableTypes.includes(c.type))

            if (this.search) {
                clusters = clusters.filter(c => {
                    return JSON.stringify(c)
                        .toLowerCase()
                        .indexOf(this.search.toLowerCase()) != -1
                })
            }

            return clusters
        },
        allBridges() {
            const bridges = []
            this.clusters.forEach(c => {
                bridges.push(...c.providers)
            })
            return bridges
        },
        allProviders() {
            const providers = []
            this.clusters.forEach(c => {
                providers.push(c)
                if (c.type !== 'vcs') providers.push(...c.providers)
            })
            return providers
        },
        activeProvider() {
            const providerId = (typeof this.value === 'object') ? this.value.id : this.value
            const provider = this.allProviders.find(p => providerId === p.id)

            if (!provider) {
                return null
            }

            if (!provider.cluster) {
                return { provider: null, cluster: provider }
            }

            return {
                provider: provider,
                cluster: this.allProviders.find(p => provider.cluster === p.id)
            }
        },
        filters() {
            if (this.clustersLoading) {
                return []
            }

            if (!this.activeProvider) {
                if (this.customersCount <= 1) {
                    return [{
                        title: $gettext('Standard')
                    }]
                }

                return [{
                    title: this.$ngettext('Kund', 'Kunder', 1),
                    value: this.customer.title
                }]
            }

            const activeFilter = []

            if (this.activeProvider.cluster) {
                activeFilter.push({title: this.$ngettext('Kluster', 'Kluster', 1), value: this.activeProvider.cluster.title})
            }
            if (this.activeProvider.provider) {
                activeFilter.push({title: $gettext('Brygga'), value: this.activeProvider.provider.title})
            }
            return activeFilter
        },
    },
    watch: {
        search() {
            this.panel = null
        }
    },
    mounted() {
        if (!this.isAdmin) return

        return this.$store.dispatch('provider/getClusters')
            .then(() => {
                this.clustersLoading = false
            })
    },
    methods: {
        applyFilters() {
            this.$emit('input',
                this.returnObject ?
                    this.allProviders.find(p => this.filterProvider === p.id) || { id: null } :
                    this.filterProvider
            )

            this.$emit('filter')
            this.dialog = false
        }
    }
}
</script>
