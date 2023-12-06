<template>
    <Page
        icon="mdi-google-classroom"
        :title="$gettext('Möten')"
        :actions="pageActions"
    >
        <template v-slot:search>
            <v-form @submit.prevent="searchDebounce(true)">
                <div class="d-flex align-center">
                    <v-text-field
                        v-model="search"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök möte') + '...'"
                        outlined
                        dense
                        class="mr-4"
                    />
                    <v-btn
                        color="primary"
                        :loading="loading"
                        class="mr-md-4"
                        @click="searchDebounce"
                    >
                        <v-icon>mdi-refresh</v-icon>
                    </v-btn>
                </div>
            </v-form>
        </template>
        <template v-slot:filter>
            <VBtnFilterProvider
                v-model="provider"
                :title="$gettext('Visa möten för')"
                :loading="loading"
                :provider-types="['acano', 'pexip', 'vcs']"
                @filter="setProvider"
            />
        </template>
        <template v-slot:content>
            <ErrorMessage :error="error" />

            <v-data-table
                :loading="loading"
                :items="activeCalls"
                multiple
                disable-sort
                :options.sync="pagination"
                :headers="activeHeaders"
                :server-items-length="page.count || -1"
                @update:page="setPage"
            >
                <template v-slot:item.title="{ item }">
                    <router-link
                        v-if="item.pexip || isPexip"
                        :to="{
                            name: 'call_details_pexip',
                            params: { id: item.id },
                            query: {
                                cospace: item.cospace,
                                provider: provider || '',
                                ...(provider ? { customer: item.customerId } : {})
                            },
                        }"
                    >
                        {{ item.name || '-- No name --' }}
                    </router-link>
                    <router-link
                        v-else
                        :to="{ name: 'calls_details', params: { id: item.id } }"
                    >
                        {{
                            item.name || '-- No name --'
                        }}
                    </router-link>
                </template>
                <template v-slot:item.participants="{ item }">
                    <v-icon
                        v-if="callParticipantError[item.id]"
                        :title="callParticipantError[item.id]"
                    >
                        mdi-alert-outline
                    </v-icon>
                    <CallParticipantList
                        v-else
                        :participants="item.participants"
                    />
                </template>
            </v-data-table>

            <v-dialog
                v-model="addMeetingForm"
                scrollable
                :max-width="400"
            >
                <DialParticipantForm />
            </v-dialog>
        </template>
    </Page>
</template>

<script>
import { itemListSearchPrefix } from '@/consts'
import { idMap } from '@/vue/helpers/store'
import { $gettext } from '@/vue/helpers/translate'
import { duration } from '@/vue/helpers/datetime'

import Page from '@/vue/views/layout/Page'

import VBtnFilterProvider from '@/vue/components/filtering/VBtnFilterProvider'
import CallParticipantList from '@/vue/components/call/CallParticipantList'
import DialParticipantForm from '@/vue/components/call/DialParticipantForm'

import ErrorMessage from '@/vue/components/base/ErrorMessage'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'

export default {
    name: 'CallsList',
    components: {
        Page,
        VBtnFilterProvider,
        CallParticipantList,
        DialParticipantForm,
        ErrorMessage
    },
    mixins: [PageSearchMixin],
    data() {
        const pageHistory = history.state?.page || {}

        return {
            page: { count: pageHistory.count || null },
            pagination: { page: 1, itemsPerPage: 10, ...( pageHistory.pagination || {} ) },
            headers: [
                // See activeHeaders
                { text: $gettext('Möte'), value: 'title' },
                { text: $gettext('Uppkoppling'), value: 'duration' },
                { text: $gettext('Deltagare'), value: 'participants' },
                { text: '', align: 'end', value: 'actions' },
            ],
            search: pageHistory.search ||
                (this.$route.query.call_id || '').replace(itemListSearchPrefix, ''),
            provider: pageHistory.provider ||
                (this.$route.query.provider ? parseInt(this.$route.query.provider) : 0),
            calls: {},
            filterDialog: false,
            firstLoad: true,
            addMeetingForm: false,
            callParticipantError: {},
            error: null,
        }
    },

    computed: {
        customers() {
            return Object.values(this.$store.state.site.customers)
        },
        customer() {
            return this.$store.state.site.customers[this.$store.state.site.customerId]
        },
        allProviders() {
            const providers = []
            this.clusters.forEach(c => {
                providers.push({ title: c.title, id: c.id })
                providers.push(...c.providers)
            })
            return providers
        },
        activeProvider() {
            const provider = this.allProviders.find(p => this.provider === p.id)

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
        settings() {
            return this.$store.state.site
        },
        clusters() {
            return Object.values(this.$store.state.provider.clusters)
        },
        tenants() {
            const customers = Object.values(this.$store.state.site.customers || {})
            return {
                ...idMap(customers, 'acano_tenant_id'),
                ...idMap(customers, 'pexip_tenant_id'),
                '': undefined,
            }
        },
        callParticipants() {
            return this.$store.getters['call/callParticipants']
        },
        relationMaps() {
            const tenantMap = {}
            const tenantProviderMap = {}
            const tenantClusterMap = {}

            this.customers.forEach(c => {
                const tenantId = c.acano_tenant_id ? c.acano_tenant_id : c.pexip_tenant_id
                if (tenantId) {
                    tenantMap[tenantId] = c
                } else {
                    tenantProviderMap[c.provider] = c
                }
            })

            this.clusters.forEach(c => {
                tenantClusterMap[c.id] = tenantProviderMap[c.id]
                c.providers.forEach(p => {
                    tenantClusterMap[p.id] = p.id in tenantProviderMap
                        ? tenantProviderMap[p.id]
                        : tenantProviderMap[c.id]
                })
            })

            return { tenantMap, tenantClusterMap }
        },
        activeCalls() {

            const { tenantMap, tenantClusterMap } = this.relationMaps

            const fullCalls = this.$store.state.call.calls

            return Object.keys(this.calls || {}).map(callId => {
                const call = fullCalls[callId] || this.calls[callId]

                const customer = !call.tenant
                    ? tenantClusterMap[this.provider] || {}
                    : tenantMap[call.tenant] || {}

                return {
                    ...call,
                    duration: duration(call.ts_start),
                    participants: this.callParticipants[call.id],
                    customerName: customer.title,
                    customerId: customer.id,
                    participantError: this.callParticipantError[call.id],
                }
            })
        },
        customerId() {
            return this.$store.state.site.customerId
        },
        multiTenant() {
            const customerId = this.customerId
            return this.activeCalls.some(call => call.customerId && call.customerId !== customerId)
        },
        activeHeaders() {
            if (this.customers.length > 1 && this.multiTenant) {
                return [this.headers[0], { text: this.$ngettext('Kund', 'Kunder', 1), value: 'customerName' }, ...this.headers.slice(1)]
            }

            return this.headers
        },
        isPexip() {
            return this.$store.state.site.isPexip
        },
        pageActions() {
            return [
                { icon: 'mdi-plus', click: () => (this.addMeetingForm = true) },
                { type: 'refresh', click: () => this.searchDebounce() }
            ]
        }
    },
    watch: {
        pagination: {
            deep: true,
            handler() {
                if (!this.firstLoad) this.searchDebounce()
            }
        },
        search() {
            if (!this.firstLoad) {
                this.searchDebounce(true)
            }
        },
    },
    mounted() {
        this.$nextTick(this.loadData)

        if (this.settings.perms.admin) {
            this.$store.dispatch('provider/getClusters')
        }
    },
    methods: {
        setPage() {
            this.searchDebounce()
        },
        setProvider() {
            this.searchDebounce(true)
        },
        newSearch() {
            this.loadData()

            this.$router.push({
                query: {
                    search: this.search || undefined,
                    provider: this.provider || undefined
                },
            }).catch(e => e)
        },
        // eslint-disable-next-line max-lines-per-function
        loadData() {
            this.firstLoad = false
            this.setLoading(true)
            this.error = null

            const { search, provider } = this

            return this.$store
                .dispatch('call/getCalls', {
                    search,
                    provider: provider || '',
                    offset: (this.pagination.page - 1) * this.pagination.itemsPerPage,
                    limit: this.pagination.itemsPerPage,
                })
                .then(response => {
                    this.calls = idMap(response.results)
                    this.page = { ...response, results: undefined }

                    history.replaceState({
                        ...history.state,
                        page: {
                            count: this.page.count,
                            search,
                            provider,
                            pagination: { ...this.pagination },
                        }
                    }, '')

                    // eslint-disable-next-line promise/no-nesting
                    return this.fetchParticipants()
                        .then(() => {
                            this.setLoading(false)
                        })
                        .catch(e => {
                            this.error = e
                            this.setLoading(false)
                        })
                })
                .catch(e => {
                    this.error = e
                    this.setLoading(false)
                    this.calls = {}
                })
        },
        fetchParticipants() {
            return Promise.all(
                this.activeCalls.map(call =>
                    this.$store.dispatch('call/getCallData', {
                        callId: call.id,
                        provider: this.provider || '',
                        cospace: call.cospace,
                    }).then(r => {
                        this.$delete(this.callParticipantError, call.id)
                        return r
                    }).catch(e => {
                        this.callParticipantError[call.id] = e.toString()
                    })
                )
            )
        },
    },
}
</script>
