<template>
    <Page
        icon="mdi-weather-cloudy-arrow-right"
        :title="$gettext('Proxyklienter')"
        :actions="[{ type: 'refresh', click: () => loadData() }]"
        :loading="loading"
    >
        <template v-slot:content>
            <v-row>
                <v-col
                    cols="12"
                    md="8"
                >
                    <v-data-table
                        :loading="loading"
                        :items="filteredProxies"
                        :headers="headers"
                        sort-by="id"
                        sort-desc
                    >
                        <template v-slot:item.name="{ item }">
                            <EndpointProxyStatusIndicator :proxy="item" />

                            <span v-if="!$store.state.site.perms.staff">{{ item.name || item.first_ip }}</span>
                            <a
                                v-else
                                href="#"
                                @click.prevent="edit(item)"
                            >{{ item.name || item.first_ip || $gettext('Tom') }}</a>
                        </template>

                        <template v-slot:item.button="{ item }">
                            <v-btn-confirm
                                icon
                                @click="remove(item)"
                            >
                                <v-icon>mdi-delete</v-icon>
                            </v-btn-confirm>
                            <v-btn
                                v-if="!item.ts_activated"
                                icon
                                @click="edit(item)"
                            >
                                <v-icon>mdi-check</v-icon>
                            </v-btn>
                        </template>
                        <template v-slot:item.last_connect="{ item }">
                            {{ item.last_connect|since }}
                        </template>
                        <template v-slot:item.last_active="{ item }">
                            {{ item.last_active|since }}
                        </template>
                    </v-data-table>
                </v-col>
                <v-col
                    cols="12"
                    md="4"
                >
                    <v-card class="mt-4">
                        <v-card-title><translate>Statusändringar</translate></v-card-title>
                        <v-divider />
                        <v-list v-if="latestProxyStatusChanges.length > 0">
                            <template v-for="notice in allStatusChanges">
                                <v-list-item
                                    :key="notice.id"
                                    :three-line="!notice.overrideTitle"
                                >
                                    <v-list-item-title v-if="notice.overrideTitle">
                                        {{ notice.overrideTitle }}
                                    </v-list-item-title>
                                    <v-list-item-content v-else>
                                        <v-list-item-subtitle v-text="notice.created" />

                                        <v-list-item-title v-if="notice.proxy">
                                            <a
                                                href="#"
                                                @click.prevent="edit(notice.proxy)"
                                            >
                                                <strong>{{ notice.proxy.name }}</strong> ({{ notice.proxy.last_connect_ip }})
                                            </a>
                                        </v-list-item-title>
                                        <v-list-item-subtitle>
                                            <v-chip
                                                v-if="notice.is_online === null"
                                                class="mr-2"
                                                x-small
                                                color="yellow"
                                            >
                                                <translate>Connect</translate>
                                            </v-chip>
                                            <v-chip
                                                v-else-if="notice.connect"
                                                class="mr-2"
                                                x-small
                                                dark
                                                color="orange"
                                            >
                                                <translate>Connect</translate>
                                            </v-chip>

                                            <v-chip
                                                v-else-if="notice.online"
                                                class="mr-2"
                                                x-small
                                                dark
                                                color="green"
                                            >
                                                <translate>Online</translate>
                                            </v-chip>
                                            <v-chip
                                                v-else-if="!notice.overrideTitle"
                                                class="mr-2"
                                                x-small
                                                dark
                                                color="red"
                                            >
                                                <translate>Offline</translate>
                                            </v-chip>
                                        </v-list-item-subtitle>
                                    </v-list-item-content>
                                </v-list-item>
                                <v-divider :key="`split${notice.id}`" />
                            </template>
                        </v-list>
                        <v-card-text v-else>
                            <translate>Inga notiser för närvarande.</translate>
                        </v-card-text>
                    </v-card>
                </v-col>
            </v-row>

            <v-dialog
                :value="!!editProxy"
                max-width="800"
                @input="editProxy = null"
            >
                <v-card @keydown.enter="delaySubmit">
                    <v-card-title class="headline">
                        <translate v-if="editProxy && editProxy.ts_activated">
                            Redigera proxyklient
                        </translate>
                        <translate v-else>
                            Aktivera proxyklient
                        </translate>
                    </v-card-title>

                    <v-card-text>
                        <v-text-field v-model="form.name" />

                        <v-combobox
                            v-model="form.ip_nets"
                            multiple
                            chips
                            :label="$gettext('Matcha nya system automatiskt från dessa ip-serier')"
                            :hint="$gettext('Tabb-separerad. Använd 0.0.0.0/0 för samtliga')"
                        />
                    </v-card-text>

                    <v-card-actions>
                        <v-btn
                            color="primary"
                            @click="delaySubmit"
                        >
                            <translate>Spara</translate>
                        </v-btn>
                        <v-btn v-close-dialog>
                            <translate>Avbryt</translate>
                        </v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>
        </template>
    </Page>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'
import Page from '@/vue/views/layout/Page'
import VBtnConfirm from '@/vue/components/VBtnConfirm'
import EndpointProxyStatusIndicator from '@/vue/components/epm/endpointproxy/EndpointProxyStatusIndicator'
import {timestamp} from '@/vue/helpers/datetime'

export default {
    components: {Page, EndpointProxyStatusIndicator, VBtnConfirm },
    props: {
        visible: { type: Boolean },
    },
    data() {
        return {
            loading: true,
            editProxy: null,
            form: {
                name: '',
                ip_nets: [],
            },
            headers: [
                { text: $gettext('Namn'), value: 'name' },
                { text: 'IP', value: 'last_connect_ip' },
                { text: $gettext('Senaste anslutning'), value: 'last_connect' },
                { text: $gettext('Senast kontrollerad'), value: 'last_active' },
                ...(this.$store.state.site.perms.staff ? [{ text: '', value: 'button', align: 'end' }] : []),
            ],
            filters: {},
        }
    },
    computed: {
        proxies() {
            return this.$store.state.endpoint.proxies
        },
        allStatusChanges() {
            return [...this.latestProxyStatusChanges, { overrideTitle: $gettext('Arkiv') + ':' }, ...this.proxyStatusChanges]
        },
        proxyStatusChanges() {
            return this.$store.state.endpoint.proxyStatusChanges.map(this.convertStatusObject)
        },
        latestProxyStatusChanges() {
            return this.$store.state.endpoint.latestProxyStatusChanges.map(this.convertStatusObject)
        },
        filteredProxies() {
            const proxies = this.proxies
            const filters = Object.entries(this.filters).filter(f => f[1])

            if (!filters) return proxies

            return Object.values(proxies).filter(proxy => {
                return filters.every(f => proxy[f[0]] === f[1])
            })
        }
    },
    watch: {
        visible(newValue) {
            if (newValue) this.loadData()
        },
    },
    mounted() {
        this.loadData()
    },
    methods: {
        convertStatusObject(change) {
            return {
                ...change,
                proxy: this.proxies[change.proxy],
                created: timestamp(change.ts_created),
                connect: change.is_connect,
                online: change.is_online
            }
        },
        delaySubmit() {
            // make sure comboboxes are saved
            return new Promise(resolve => setTimeout(() => resolve(this.editProxy && this.activate(this.editProxy.id)), 100))
        },
        edit(proxy) {
            this.editProxy = proxy
            this.form.name = proxy.name
            this.form.ip_nets = proxy.ip_nets
        },
        remove(proxy) {
            return this.$store.dispatch('endpoint/deleteProxy', proxy.id)
        },
        activate(id) {
            this.editProxy = null
            return this.$store.dispatch('endpoint/updateProxy', { id, ...this.form })
        },
        loadData() {
            this.loading = true
            return Promise.all([
                this.$store.dispatch('endpoint/getProxies'),
                this.$store.dispatch('endpoint/getProxyStatusChanges'),
                this.$store.dispatch('endpoint/getLatestProxyStatusChanges'),
            ]).then(() => {
                this.loading = false
            })
        },
    },
}
</script>
