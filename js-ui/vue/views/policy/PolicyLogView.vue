<template>
    <Page icon="mdi-bug">
        <template v-slot:title>
            <h1><translate>Policy Debug</translate></h1>
        </template>
        <template v-slot:tabs>
            <v-tabs v-model="tab">
                <v-tab><translate>Statusändringar</translate></v-tab>
                <v-tab><translate>External policy-beslut</translate></v-tab>
                <v-tab><translate>Aktiva deltagare</translate> <translate>(lokalt)</translate></v-tab>
            </v-tabs>
        </template>
        <template v-slot:content>
            <v-row>
                <v-col md="8">
                    <v-tabs-items v-model="tab">
                        <v-tab-item>
                            <!-- Policy -->
                            <v-data-table-paginated
                                :loading="loading"
                                :headers="headers.log"
                                :items="logs.log"
                                :options.sync="logOptions.log.pagination"
                                sort-by="ts"
                                sort-desc
                                :server-items-length="historicLogView ? logOptions.log.count || -1 : -1"
                            >
                                <template v-slot:item.ts="{ item }">
                                    {{ item.ts | timestamp }}
                                </template>
                                <template v-slot:item.customer="{ item }">
                                    {{ (customers[item.customer] || {}).title }}
                                </template>
                                <template v-slot:item.type="{ item }">
                                    {{ types[item.limit] }}
                                </template>
                                <template v-slot:item.action="{ item }">
                                    <v-btn
                                        icon
                                        @click="filterGuid(item.guid)"
                                    >
                                        <v-icon>mdi-filter</v-icon>
                                    </v-btn>
                                </template>
                            </v-data-table-paginated>
                        </v-tab-item>

                        <v-tab-item>
                            <!-- External policy -->
                            <v-data-table
                                :loading="loading"
                                :headers="headers.externalPolicy"
                                :items="logs.externalPolicy"
                                :options.sync="logOptions.externalPolicy.pagination"
                                sort-by="ts"
                                sort-desc
                                :server-items-length="historicLogView ? logOptions.externalPolicy.count || -1 : -1"
                            >
                                <template v-slot:item.ts="{ item }">
                                    {{ item.ts | timestamp }}
                                </template>
                                <template v-slot:item.customer="{ item }">
                                    {{ (customers[item.customer] || {}).title }}
                                </template>
                                <template v-slot:item.action="{ item }">
                                    {{ actions[item.action] }}
                                </template>
                                <template v-slot:item.type="{ item }">
                                    {{ types[item.limit] }}
                                </template>
                            </v-data-table>
                        </v-tab-item>

                        <v-tab-item>
                            <!-- Active participants -->
                            <h2 v-translate>
                                Aktiva
                            </h2>
                            <v-data-table
                                :loading="loading"
                                :headers="headers.activeParticipants"
                                :items="logs.activeParticipants"
                                sort-by="ts_created"
                                :search="filter.customer ? filter.customer.title : ''"
                            >
                                <template v-slot:item.ts_created="{ item }">
                                    {{ item.ts_created | timestamp }}
                                </template>
                                <template v-slot:item.customer="{ item }">
                                    {{ (customers[item.customer] || {}).title }}
                                </template>
                                <template v-slot:item.name="{ item }">
                                    {{ item.name || item.guid }}
                                </template>
                                <template v-slot:item.action="{ item }">
                                    <v-btn
                                        icon
                                        @click="filterGuid(item.guid)"
                                    >
                                        <v-icon>mdi-filter</v-icon>
                                    </v-btn>
                                </template>
                            </v-data-table>

                            <h2 v-translate>
                                Nedkopplade
                            </h2>
                            <v-data-table
                                :headers="headers.activeParticipantsRemoved"
                                :items="logs.activeParticipantsRemoved"
                                sort-by="ts_removed"
                                sort-desc
                                :search="filter.customer ? filter.customer.title : ''"
                            >
                                <template v-slot:item.ts_created="{ item }">
                                    {{ item.ts_created | timestamp }}
                                </template>
                                <template v-slot:item.ts_removed="{ item }">
                                    ~{{ item.ts_removed | timestamp }}
                                </template>
                                <template v-slot:item.cluster="{ item }">
                                    {{ (clusterMap[item.cluster] || {}).title }}
                                </template>
                                <template v-slot:item.customer="{ item }">
                                    {{ item.customer ? (customers[item.customer] || {}).title : 'Default' }}
                                </template>
                                <template v-slot:item.action="{ item }">
                                    <v-btn
                                        icon
                                        @click="filterGuid(item.guid)"
                                    >
                                        <v-icon>mdi-filter</v-icon>
                                    </v-btn>
                                </template>
                            </v-data-table>
                        </v-tab-item>
                    </v-tabs-items>
                </v-col>
                <v-col md="4">
                    <v-card class="mt-4">
                        <v-card-title><translate>Filtrering</translate></v-card-title>
                        <v-card-text>
                            <v-datetime-picker
                                v-model="filter.ts_from"
                                :label="$gettext('Fr.o.m.')"
                            />
                            <v-datetime-picker
                                v-model="filter.ts_to"
                                :label="$gettext('T.o.m.')"
                            />
                            <CustomerPicker
                                v-model="filter.customer"
                                :label="$gettext('Välj kund')"
                                @input="clearLog"
                            />
                            <v-text-field
                                v-model="filter.cluster"
                                :label="$ngettext('Kluster', 'Kluster', 2)"
                                @keydown.enter="clearLog"
                            />
                            <v-text-field
                                v-model="filter.message"
                                :label="$gettext('Meddelande')"
                                @keydown.enter="clearLog"
                            />
                            <v-text-field
                                v-model="filter.guid"
                                :label="$gettext('GUID')"
                                clearable
                                @keydown.enter="clearLog"
                            />
                        </v-card-text>
                        <v-card-actions>
                            <v-btn @click="clearLog">
                                <translate>Filtrera</translate>
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-col>
            </v-row>

            <v-card v-if="legDebug && legDebug.loaded">
                <v-card-title><translate>Leg info</translate></v-card-title>

                <v-tabs>
                    <v-tab><translate>Leg</translate> ({{ legDebug.legs.length }})</v-tab>
                    <v-tab><translate>Event sink</translate> ({{ legDebug.cdr.length }})</v-tab>
                    <v-tab><translate>History</translate> ({{ legDebug.history.length }})</v-tab>

                    <v-tab-item>
                        <v-expansion-panels>
                            <v-expansion-panel
                                v-for="leg in legDebug.legs"
                                :key="leg.id"
                            >
                                <v-expansion-panel-header>
                                    <translate>Leg</translate>: {{ leg.display_name || leg.name }}
                                </v-expansion-panel-header>
                                <v-expansion-panel-content>
                                    <pre>{{ JSON.stringify(leg, null, 2) }}</pre>
                                </v-expansion-panel-content>
                            </v-expansion-panel>
                        </v-expansion-panels>
                    </v-tab-item>
                    <v-tab-item>
                        <v-expansion-panels>
                            <v-expansion-panel
                                v-for="cdr in legDebug.cdr"
                                :key="cdr.guid"
                            >
                                <v-expansion-panel-header>
                                    <translate>Event sink</translate>: {{ cdr.ts|timestamp }} {{ cdr.event }}
                                </v-expansion-panel-header>
                                <v-expansion-panel-content>
                                    <pre>{{ JSON.stringify(cdr, null, 2) }}</pre>
                                </v-expansion-panel-content>
                            </v-expansion-panel>
                        </v-expansion-panels>
                    </v-tab-item>
                    <v-tab-item>
                        <v-expansion-panels>
                            <v-expansion-panel
                                v-for="history in legDebug.history"
                                :key="history.guid"
                            >
                                <v-expansion-panel-header><translate>History</translate>: {{ history.ts|timestamp }} </v-expansion-panel-header>
                                <v-expansion-panel-content>
                                    <pre>{{ JSON.stringify(history, null, 2) }}</pre>
                                </v-expansion-panel-content>
                            </v-expansion-panel>
                        </v-expansion-panels>
                    </v-tab-item>
                </v-tabs>
            </v-card>
        </template>
    </Page>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import CustomerPicker from '../../components/tenant/CustomerPicker'
import {idMap} from '../../helpers/store'
import { formatISO, now } from '../../helpers/datetime'
import VDatetimePicker from '../../components/datetime/DateTimePicker'
import Page from '@/vue/views/layout/Page'
export default {
    components: {Page, VDatetimePicker, CustomerPicker },
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            filter: {
                customer: null,
                cluster: null,
                message: null,
                guid: null,
                ts_from: null,
                ts_to: null,
            },

            logData: {
                log: [],
                externalPolicy: [],
                activeParticipants: [],
                activeParticipantsRemoved: [],
            },
            logOptions: {
                log: {
                    count: 0,
                    pagination: { itemsPerPage: 20 },
                },
                externalPolicy: {
                    pagination: { itemsPerPage: 20 },
                    count: 0,
                },
            },
            legDebug: {
                leg: null,
                cdr: null,
                history: null,
                loaded: false,
            },
            updateInterval: null,
            loading: false,
            display: {
                policy: true,
                externalPolicy: true,
            },
            headers: {
                log: [
                    { text: $gettext('Tid'), value: 'ts' },
                    { text: $gettext('Meddelande'), value: 'message' },
                    { text: this.$ngettext('Kund', 'Kunder', 1), value: 'customer' },
                    { text: '', value: 'action', align: 'end' },
                ],
                externalPolicy: [
                    { text: $gettext('Tid'), value: 'ts' },
                    { text: $gettext('Meddelande'), value: 'message' },
                ],
                activeParticipants: [
                    { text: $gettext('Tid'), value: 'ts_created' },
                    { text: this.$ngettext('Kluster', 'Kluster', 1), value: 'cluster' },
                    { text: this.$ngettext('Kund', 'Kunder', 1), value: 'customer' },
                    { text: $gettext('Namn'), value: 'name' },
                    { text: $gettext('Gateway'), value: 'is_gateway' },
                    { text: '', value: 'action', align: 'end' },
                ],
                activeParticipantsRemoved: [
                    { text: $gettext('Borttagen'), value: 'ts_removed' },
                    { text: $gettext('Uppkopplad'), value: 'ts_created' },
                    { text: this.$ngettext('Kund', 'Kunder', 1), value: 'customer' },
                    { text: $gettext('Namn'), value: 'name' },
                    { text: $gettext('Gateway'), value: 'is_gateway' },
                    { text: '', value: 'action', align: 'end' },
                ],
            },
            lastIds: {
                log: null,
                externalPolicy: null,
                activeParticipants: null,
            },
            actions: {
                0: 'Ignore',
                10: 'Log',
                100: 'Reject',
            },
            tab: 0,
        }
    },
    computed: {
        historicLogView() {
            return !!this.filter.ts_to
        },
        clusterMap() {
            return this.$store.state.provider.clusters || {}
        },
        logs() {
            return {
                log: this.logData.log || [],
                externalPolicy: this.logData.externalPolicy || [],
                activeParticipants: this.logData.activeParticipants || [],
                activeParticipantsRemoved: this.logData.activeParticipantsRemoved || [],
            }
        },
        filterParams() {
            return {
                message__contains: this.filter.message || undefined,
                guid: this.filter.guid || undefined,
                cluster: this.filter.cluster || undefined,
                customer: this.filter.customer || undefined,
                ts__gte: this.filter.ts_from || undefined,
                ts__lte: this.filter.ts_to || undefined,
            }
        },
        customers() {
            return this.$store.state.site.customers
        },
    },
    watch: {
        'logOptions.log.pagination.page': function() {
            if (this.historicLogView) this.loadPolicyLog()
        },
        'logOptions.log.pagination.itemsPerPage': function() {
            if (this.historicLogView) this.loadPolicyLog()
        },
        'logOptions.externalPolicy.pagination.page': function() {
            if (this.historicLogView) this.loadExternalPolicyLog()
        },
        'logOptions.externalPolicy.pagination.itemsPerPage': function() {
            if (this.historicLogView) this.loadExternalPolicyLog()
        },
    },
    mounted() {
        this.updateInterval = setInterval(() => {
            if (this.loading) return
            if (this.filterParams.ts__lte && formatISO(this.filterParams.ts__lte) < now()) return  // old dates
            this.loadAll()
        }, 2000)
    },
    beforeDestroy() {
        clearInterval(this.updateInterval)
    },
    methods: {
        clearLog() {
            for (const k in this.logData) this.logData[k] = []
            for (const k in this.lastIds) this.lastIds[k] = null
            this.loadAll()
        },
        filterGuid(guid) {
            this.filter.guid = guid
            this.logData.log = []
            this.lastIds.log = null
            this.tab = 0
            this.loadAll()
        },
        async loadHistory(url, dataKey) {
            const pagination = this.logOptions[dataKey].pagination
            const params = {
                ...this.filterParams,
                guid: this.filter.guid || undefined,
                limit: this.logOptions[dataKey].pagination.itemsPerPage,
                offset: (pagination.page - 1) * pagination.itemsPerPage,
            }
            return await this.$store
                .api()
                .get(url, { params })
                .then(response => {
                    this.logOptions[dataKey].count = response.count
                    this.logData[dataKey] = Object.freeze(response.results)
                })
        },
        async loadLive(url, dataKey) {
            const params = {
                ...this.filterParams,
                id__gt: this.lastIds[dataKey] || undefined,
            }

            return await this.$store
                .api()
                .get(url, { params })
                .then(response => {
                    if (!response.results?.length) return

                    const start = Math.max(0, (this.logData[dataKey] || []).length - 1000)
                    this.logData[dataKey] = Object.freeze(this.logData[dataKey].slice(start, start + 1000).concat(response.results))
                    this.lastIds[dataKey] = response.results[0].id
                })
        },
        loadPolicyLog() {
            if (this.historicLogView) {
                return this.loadHistory('debug/policy_log/', 'log')
            } else {
                return this.loadLive('debug/policy_log/', 'log')
            }
        },
        async loadExternalPolicyLog() {
            if (this.historicLogView) {
                return this.loadHistory('debug/external_policy_log/', 'externalPolicy')
            } else {
                return this.loadLive('debug/external_policy_log/', 'externalPolicy')
            }
        },
        async loadActiveParticipants() {
            const params = this.filterParams

            await this.$store
                .api()
                .get('debug/active_participant/', { params })
                .then(response => {
                    const removed = []

                    const active = idMap(response, 'guid')

                    this.logs.activeParticipants.forEach(participant => {
                        if (!active[participant.guid]) {
                            removed.push({ts_removed: new Date(), ...participant})
                        }
                    })
                    this.logData.activeParticipants = Object.freeze(response)

                    const start = Math.max(0, this.logData.activeParticipantsRemoved.length - 1000)
                    this.logData.activeParticipantsRemoved = Object.freeze(this.logData.activeParticipantsRemoved.slice(start, start + 1000).concat(removed))
                })
        },
        async loadLegData() {
            if (this.filter.guid) {
                let response
                try {
                    response = await this.$store.api().get('debug/leg/', {params: { guid: this.filter.guid}})
                } catch(e) {
                    return
                }
                this.loading = false
                this.legDebug = Object.values(response).filter(v => v && v.length).length ? {...response, loaded: true} : null
            } else {
                this.legDebug = null
            }
        },
        loadClusters() {
            return this.$store.dispatch('provider/getClusters')
        },
        loadAll() {
            this.loading = true
            this.loadLegData()
            Promise.all([this.loadClusters(), this.loadExternalPolicyLog(), this.loadPolicyLog(), this.loadActiveParticipants()])
                .then(() => {
                    this.loading = false
                })
                .catch(() => {
                    setTimeout(() => {
                        this.loading = false
                    }, 500)
                })
        }
    },
}
</script>
