<template>
    <div>
        <v-alert
            v-if="done.length"
            type="success"
            border="left"
            class="mb-4"
            colored-border
        >
            <strong><translate>Sparade objekt</translate>:</strong>
            <div
                v-for="item in done"
                :key="item.id"
            >
                <router-link :to="{ name: 'endpoint_details', params: { id: item.id } }">
                    {{
                        item.title || item.id
                    }}
                </router-link>
            </div>
        </v-alert>

        <v-alert
            v-if="$store.state.site.perms.staff"
            type="info"
            text
            tile
        >
            <v-row>
                <v-col class="grow">
                    <translate>Du kan ändra så system läggs till automatiskt från utvalda IP-serier under Inställningar</translate>
                </v-col>
                <v-col class="shrink">
                    <v-btn
                        color="primary"
                        small
                        :to="{name: 'epm_settings'}"
                    >
                        <translate>Direktlänk till inställningar</translate>
                    </v-btn>
                </v-col>
            </v-row>
        </v-alert>

        <v-alert
            v-if="!endpoints.length"
            type="info"
            class="my-4"
        >
            <translate>Här visas system som lagts till genom passiv provisionering direkt i systemen. Just nu är listan tom.</translate>
        </v-alert>

        <v-data-table
            :loading="loading"
            :items="filteredEndpoints"
            :headers="headers"
            sort-by="id"
            sort-desc
        >
            <template v-slot:item.title="{ item }">
                {{ item.title || item.ip || $gettext('Tom') }}
            </template>

            <template v-slot:item.button="{ item }">
                <div class="d-flex align-center justify-end">
                    <v-btn
                        color="primary"
                        class="mr-2"
                        x-small
                        depressed
                        @click="edit(item)"
                    >
                        <translate>Godkänn</translate>
                    </v-btn>
                    <v-btn-confirm
                        icon
                        @click="remove(item)"
                    >
                        <v-icon>mdi-delete</v-icon>
                    </v-btn-confirm>
                </div>
            </template>

            <template v-slot:item.ts_created="{ item }">
                {{ item.ts_created|timestamp }}
            </template>
        </v-data-table>

        <v-dialog
            :value="!!editEndpoint"
            max-width="800"
            scrollable
            @input="editEndpoint = null"
        >
            <EndpointForm
                v-if="editEndpoint"
                :id="editEndpoint.id"
                approval
                @complete="completed"
            />
        </v-dialog>
    </div>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import EndpointForm from '@/vue/components/epm/endpoint/EndpointForm'
import VBtnConfirm from '@/vue/components/VBtnConfirm'

export default {
    components: { VBtnConfirm, EndpointForm },
    props: {
        visible: { type: Boolean },
    },
    data() {
        return {
            emitter: new GlobalEventBus(this),
            loading: true,
            editEndpoint: null,
            done: [],
            headers: [
                { text: 'ID', value: 'id' },
                { text: $gettext('Namn'), value: 'title' },
                { text: 'IP', value: 'ip' },
                { text: $gettext('Skapades'), value: 'ts_created' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {},
        }
    },
    computed: {
        endpoints() {
            return Object.values(this.$store.state.endpoint.incoming)
        },
        filteredEndpoints() {
            const endpoints = this.endpoints
            const filters = Object.entries(this.filters).filter(f => f[1])

            if (!filters) return endpoints

            return endpoints.filter(endpoint => {
                return filters.every(f => endpoint[f[0]] === f[1])
            })
        },
    },
    watch: {
        visible(newValue) {
            if (newValue) this.loadData()
        },
    },
    mounted() {
        this.emitter.on('refresh', () => this.loadData())

        return this.loadData()
    },
    methods: {
        edit(endpoint) {
            this.editEndpoint = endpoint
        },
        remove(endpoint) {
            return this.$store.dispatch('endpoint/deleteEndpoint', endpoint.id).then(() => {
                this.loadData()
            })
        },
        loadData() {
            this.loading = true
            this.emitter.emit('loading', true)
            return Promise.all([this.$store.dispatch('endpoint/getIncoming')]).then(() => {
                this.emitter.emit('loading', false)
                this.loading = false
            })
        },
        completed() {
            this.done.push(this.editEndpoint)
            this.editEndpoint = null
            this.loadData()
        },
    },
}
</script>
