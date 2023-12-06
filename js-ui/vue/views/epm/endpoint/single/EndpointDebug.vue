<template>
    <Page
        icon="mdi-bug"
        :title="endpoint.title || endpoint.hostname || endpoint.ip"
        :actions="reloadInterval ? null : [{ type: 'refresh', 'click': startReload }]"
    >
        <template v-slot:content>
            <v-row class="mt-4">
                <v-col>
                    <v-simple-table v-if="endpoint.id">
                        <tbody>
                            <tr>
                                <th v-translate>
                                    SIP
                                </th>
                                <td>{{ endpoint.sip }}</td>
                            </tr>
                            <tr>
                                <th><translate>E-postadress</translate>:</th>
                                <td>
                                    <a :href="'mailto:' + endpoint.email_address">{{
                                        endpoint.email_address
                                    }}</a>
                                </td>
                            </tr>
                            <tr v-if="endpoint.sip_aliases && endpoint.sip_aliases.length">
                                <th><translate>E-post/SIP-alias</translate>:</th>
                                <td>
                                    <v-chip-group>
                                        <v-chip
                                            v-for="alias in endpoint.sip_aliases || []"
                                            :key="'alias'+alias"
                                            small
                                            pill
                                        >
                                            {{ alias }}
                                        </v-chip>
                                    </v-chip-group>
                                </td>
                            </tr>
                            <tr>
                                <th>IP</th>
                                <td>
                                    <a
                                        v-if="endpoint.ip"
                                        target="_blank"
                                        :href="'https://' + endpoint.ip + '/'"
                                    >{{ endpoint.ip }}</a>
                                </td>
                            </tr>
                            <tr v-if="endpoint.ip">
                                <th>Device event log</th>
                                <td>
                                    <a
                                        target="_blank"
                                        :href="'https://' + endpoint.ip + '/web/logs/file/current/eventlog/all.log'"
                                    ><translate>Visa (endast direktanslutning)</translate></a>
                                </td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    MAC-adress
                                </th>
                                <td>{{ endpoint.mac_address }}</td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    Hostname
                                </th>
                                <td>
                                    <a
                                        v-if="endpoint.hostname"
                                        target="_blank"
                                        :href="'https://' + endpoint.hostname + '/'"
                                    >{{ endpoint.hostname }}</a>
                                </td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    Kalendrar
                                </th>
                                <td>
                                    <v-data-table
                                        hide-default-footer
                                        :items="calendars"
                                        :headers="calendarHeaders"
                                    />
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                </v-col>
                <v-col>
                    <v-simple-table v-if="endpoint.id">
                        <tbody>
                            <tr>
                                <th v-translate>
                                    Status
                                </th>
                                <td>
                                    <v-icon v-if="endpoint.status_code < 0">
                                        mdi-alert
                                    </v-icon> {{ endpoint.status_text }}
                                </td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    Senast uppdaterad
                                </th>
                                <td>
                                    <span v-if="endpoint.status.ts_last_check">
                                        {{ endpoint.status.ts_last_check|since }}
                                    </span>
                                    <v-icon v-else>
                                        mdi-alert
                                    </v-icon>
                                </td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    Senast online
                                </th>
                                <td>
                                    <span v-if="endpoint.status.ts_last_online">
                                        {{ endpoint.status.ts_last_online|since }}
                                    </span>
                                    <v-icon v-else>
                                        mdi-alert
                                    </v-icon>
                                </td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    Liveevents
                                </th>
                                <td>
                                    <span v-if="endpoint.status.ts_last_event">
                                        {{ endpoint.status.ts_last_event|since }}
                                    </span>
                                    <v-icon v-else>
                                        mdi-alert
                                    </v-icon>
                                </td>
                            </tr>
                            <tr v-if="endpoint.connection_type == 0">
                                <th v-translate>
                                    Provisioneringsmeddelanden
                                </th>
                                <td>
                                    <span v-if="endpoint.status.ts_last_provision">
                                        {{ endpoint.status.ts_last_provision|since }}
                                    </span>
                                    <v-icon v-else>
                                        mdi-alert
                                    </v-icon>
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                </v-col>
                <v-col>
                    <v-alert
                        v-if="statusLoaded && !status.has_direct_connection"
                        type="info"
                        class="mb-4"
                    >
                        <translate>Aktiv anslutning saknas.</translate>
                    </v-alert>
                    <v-card
                        dark
                        :loading="!statusLoaded"
                    >
                        <v-card-text>
                            <translate>Call control</translate>

                            <v-form @submit.prevent="callControl('dial', dialNumber)">
                                <SipSelector
                                    v-model="dialNumber"
                                    :error-messages="callControlError"
                                />
                                <v-btn
                                    type="submit"
                                    color="orange"
                                >
                                    <translate>Ring upp</translate>
                                </v-btn>
                            </v-form>

                            <div v-if="status.in_call">
                                <p><translate>Nuvarande samtal</translate>: {{ status.in_call }} ({{ status.call_duration|duration }})</p>
                                <v-btn
                                    color="error"
                                    @click="callControl('disconnect')"
                                >
                                    <translate>Lägg på</translate>
                                </v-btn>
                            </div>

                            <div v-if="status.incoming">
                                <p><translate>Inkommande samtal</translate>: {{ status.incoming }}</p>
                                <v-btn @click="callControl('answer')">
                                    <translate>Svara</translate>
                                </v-btn>
                                <v-btn
                                    color="error"
                                    @click="callControl('reject')"
                                >
                                    <translate>Avvisa</translate>
                                </v-btn>
                            </div>
                        </v-card-text>
                    </v-card>

                    <v-card
                        dark
                        class="mt-4"
                        :loading="callControlLoading"
                    >
                        <v-card-text>
                            <v-layout>
                                <v-btn
                                    v-if="status.muted"
                                    :title="$gettext('Unmute')"
                                    icon
                                    @click="callControl('mute', 'false')"
                                >
                                    <v-icon>mdi-microphone</v-icon>
                                </v-btn>
                                <v-btn
                                    v-if="!status.muted"
                                    :title="$gettext('Mute')"
                                    icon
                                    @click="callControl('mute', 'true')"
                                >
                                    <v-icon>mdi-microphone-off</v-icon>
                                </v-btn>

                                <v-slider
                                    :title="$gettext('Volume')"
                                    class="ml-4"
                                    min="0"
                                    max="100"
                                    :value="status.volume"
                                    hide-details
                                    @change="callControl('volume', $event)"
                                />

                                <v-spacer />
                                <v-btn-confirm
                                    :title="$gettext('Reboot')"
                                    icon
                                    @click="callControl('reboot')"
                                >
                                    <v-icon>mdi-power</v-icon>
                                </v-btn-confirm>
                            </v-layout>
                        </v-card-text>
                    </v-card>
                </v-col>
            </v-row>

            <v-row>
                <v-col>
                    <v-card>
                        <v-calendar
                            type="custom-daily"
                            :end="calendarEnd"
                            :events="meetings"
                            first-time="06:00"
                            :last-time="lastTime"
                            @click:event="$router.push($event.event.url)"
                        />
                    </v-card>

                    <v-card
                        v-if="endpoint.has_head_count"
                        class="mt-4"
                    >
                        <EndpointHeadCount
                            :id="id"
                            :title="$gettext('Rumsanvändning')"
                        />
                    </v-card>
                </v-col>
                <v-col>
                    <v-card>
                        <v-card-title><translate>Kö</translate></v-card-title>
                        <EndpointTaskGrid
                            :endpoint-id="id"
                            latest
                            :changed-since="yesterday"
                        />
                    </v-card>
                    <!-- event log -->
                    <JsonDebugInfoDialog
                        v-model="eventDialogInfoIndex"
                        :structure="debugStructures.cisco"
                        :items="eventItems"
                    />
                    <v-card class="mt-4">
                        <v-card-title><translate>Live-events</translate></v-card-title>
                        <v-data-table
                            :headers="debugHeaders"
                            :items="eventItems"

                            sort-by="ts_created"
                            sort-desc
                        >
                            <template v-slot:item.action="{ item }">
                                <v-btn
                                    icon
                                    @click="eventDialogInfoIndex = item.index"
                                >
                                    <v-icon>mdi-information</v-icon>
                                </v-btn>
                            </template>
                        </v-data-table>
                    </v-card>
                    <!-- provision log -->
                    <JsonDebugInfoDialog
                        v-model="provisionDialogInfoIndex"
                        :structure="debugStructures.cisco_provision"
                        :items="provisionItems"
                    />
                    <v-card class="mt-4">
                        <v-card-title><translate>Provisionering-events</translate></v-card-title>
                        <v-data-table
                            :headers="debugHeaders"
                            :items="provisionItems"

                            sort-by="ts_created"
                            sort-desc
                        >
                            <template v-slot:item.action="{ item }">
                                <v-btn
                                    icon
                                    @click="provisionDialogInfoIndex = item.index"
                                >
                                    <v-icon>mdi-information</v-icon>
                                </v-btn>
                            </template>
                        </v-data-table>
                    </v-card>
                    <!-- error log -->
                    <JsonDebugInfoDialog
                        v-model="errorDialogInfoIndex"
                        :structure="debugStructures.cisco_error"
                        :items="errorItems"
                    />
                    <v-card class="mt-4">
                        <v-card-title><translate>Error-events</translate></v-card-title>
                        <v-data-table
                            :headers="errorHeaders"
                            :items="errorItems"

                            sort-by="ts_created"
                            sort-desc
                        >
                            <template v-slot:item.action="{ item }">
                                <v-btn
                                    icon
                                    @click="errorDialogInfoIndex = item.index"
                                >
                                    <v-icon>mdi-information</v-icon>
                                </v-btn>
                            </template>
                        </v-data-table>
                    </v-card>
                    <!-- calls -->
                    <v-card class="mt-4">
                        <v-card-title><translate>Samtal</translate></v-card-title>
                        <v-data-table
                            :headers="callsHeaders"
                            :items="calls"
                            sort-by="ts_start"
                            sort-desc
                        />
                    </v-card>
                </v-col>
            </v-row>
        </template>
    </Page>
</template>

<script>
import { addDays, endOfDay, parseISO, startOfDay } from 'date-fns'
import { $gettext } from '@/vue/helpers/translate'
import { globalEmit } from '@/vue/helpers/events'
import { formatISO, timestamp } from '@/vue/helpers/datetime'

import Page from '@/vue/views/layout/Page'

import VBtnConfirm from '@/vue/components/VBtnConfirm'
import EndpointHeadCount from '../../../../components/epm/endpoint/EndpointHeadCountGraph'
import SipSelector from '../../../../components/epm/endpoint/SipAddressPicker'
import EndpointTaskGrid from '@/vue/components/epm/endpoint/EndpointTaskGrid'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import JsonDebugInfoDialog from '@/vue/components/debug_views/JsonDebugInfoDialog'
import {debugViewStructure} from '@/vue/store/modules/debug_views/consts'

export default {
    components: {
        JsonDebugInfoDialog,
        EndpointTaskGrid,
        Page,
        SipSelector,
        EndpointHeadCount,
        VBtnConfirm,
    },
    mixins: [SingleEndpointMixin],
    // eslint-disable-next-line max-lines-per-function
    data() {
        const endpoint = this.endpoint || {}
        return {
            editDialog: false,
            status: endpoint.status || { status: endpoint.status_code, upgrade: {} },
            reloadInterval: null,
            statusLoaded: false,
            dialNumber: '',
            callControlLoading: false,
            callControlError: '',
            error: '',
            loading: false,
            meetings: [],
            provisionDialogInfoIndex: null,
            provisionItems: [],
            eventDialogInfoIndex: null,
            eventItems: [],
            errorDialogInfoIndex: null,
            errorItems: [],
            debugStructures: debugViewStructure(this.$store.state.site),
            calls: [],
            calendars: [],
            debugHeaders: [
                { text: 'IP', value: 'ip' },
                { text: $gettext('Event'), value: 'event' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: '', value: 'action', align: 'end' },
            ],
            callsHeaders: [
                { text: $gettext('Start'), value: 'ts_start' },
                { text: $gettext('Stopp'), value: 'ts_stop' },
                { text: $gettext('Motpart'), value: 'remote' },
            ],
            errorHeaders: [
                { text: $gettext('Event'), value: 'title' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: '', value: 'action', align: 'end' },
            ],
            calendarHeaders: [
                { text: $gettext('E-postadress'), value: 'username' },
                { text: $gettext('Senaste synk'), value: 'ts_last_sync' },
            ]
        }
    },
    computed: {
        upgradeStatus() {
            return this.status && this.status.upgrade && this.status.upgrade.status ? this.status.upgrade : {}
        },
        calendarEnd() {
            return addDays(new Date(), 1)
        },
        lastTime() {
            if (new Date().getHours() > 13) return '24:00'
            return '17:00'
        },
        yesterday() {
            return startOfDay(addDays(new Date(), -1))
        },
    },
    watch: {
        endpoint() {
            if (this.status.status === undefined) {
                this.status = this.endpoint.status || { status: this.endpoint.status_code }
            }
        },
    },
    mounted() {
        this.startReload()
        globalEmit(this, 'loading', false)
        this.error = ''
    },
    destroyed() {
        clearInterval(this.reloadInterval)
    },
    methods: {
        async callControl(action, argument = '') {
            this.callControlLoading = true
            try {
                const response = await this.$store.dispatch('endpoint/callControl', {
                    endpointId: this.id,
                    action,
                    argument,
                })
                if (response.status) this.status = response.status
                this.callControlLoading = false
                this.callControlError = ''
            } catch (e) {
                this.callControlLoading = false
                this.callControlError = e.toString()
            }
        },
        async updateStatus() {
            return await this.$store
                .dispatch('endpoint/getStatus', this.id)
                .then(status => {
                    this.status = status || {}
                    this.statusLoaded = true
                })
        },
        async loadBookings() {
            const response = await this.$store.dispatch('meeting/search', {
                endpoint: this.endpoint.id,
                include_external: 1,
                ts_start: formatISO(startOfDay(new Date())),
                ts_stop: formatISO(endOfDay(addDays(new Date(), 3))),
            })
            this.meetings = response.results.map(meeting => ({
                name: meeting.title,
                start: parseISO(meeting.ts_start),
                end: parseISO(meeting.ts_stop),
                timed: true,
                url: meeting.details_url,
            }))
        },
        async loadDebug() {
            const [provision, event, error] = await Promise.all([
                this.$store.api().get('debug/cisco_provision/', { params: { endpoint: this.endpoint.id } }),
                this.$store.api().get('debug/cisco/', { params: { endpoint: this.endpoint.id } }),
                this.$store.api().get('debug/error_log/', { params: { endpoint: this.endpoint.id } }),
            ])
            const addTimeAndIndex = (event, i) => ({...event, ts_created: timestamp(event.ts_created), index: i })
            this.provisionItems = provision.results.map(addTimeAndIndex)
            this.eventItems = event.results.map(addTimeAndIndex)
            this.errorItems = error.results.map(addTimeAndIndex)
        },
        async loadCalls() {
            const calls = await this.$store.dispatch('endpoint/getCalls', this.endpoint.id) || []
            this.calls = calls.map(call => ({
                ...call,
                ts_start: timestamp(call.ts_start), // TODO move to datatable
                ts_stop: timestamp(call.ts_stop),
            }))
        },
        async loadCalendars() {
            this.calendars = await this.$store.dispatch('calendar/getCalendars', { endpoint: this.endpoint.id })
        },
        loadAll() {
            if (this.loading) return

            this.loading = true
            return Promise.all([
                this.updateStatus(),
                this.loadBookings(),
                this.loadDebug(),
                this.loadCalls(),
                this.loadCalendars(),
            ]).then(() => {
                this.loading = false
            }).catch(() => {
                this.loading = false
            })
        },
        startReload() {
            if (this.reloadInterval) clearInterval(this.reloadInterval)
            this.reloadInterval = setInterval(() => {
                this.loadAll()
            }, 3000)

            // Stop hammer server after 5 min
            setTimeout(() => {
                clearInterval(this.reloadInterval)
                this.reloadInterval = null
                globalEmit(this, 'loading', false)
            }, 5 * 60 * 1000)
        },
    },
}
</script>

