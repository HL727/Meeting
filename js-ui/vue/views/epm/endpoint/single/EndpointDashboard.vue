<template>
    <div>
        <div style="position:relative;">
            <v-progress-linear
                :active="loading"
                indeterminate
                absolute
                top
            />
        </div>
        <v-card
            flat
            tile
            light
            class="px-4 overflow-hidden"
        >
            <v-row>
                <v-col
                    cols="12"
                    sm="6"
                    md="8"
                    class="pb-0 pb-sm-3"
                >
                    <v-form
                        class="d-flex align-center my-4"
                        @submit.prevent="callControl('dial', dialNumber)"
                    >
                        <SipSelector
                            v-model="dialNumber"
                            :error-messages="callControlError"
                            outlined
                            dense
                            hide-details
                            class="mr-4"
                            :disabled="!callControlEnabled"
                        />
                        <v-btn
                            :disabled="!callControlEnabled"
                            type="submit"
                            color="primary"
                        >
                            <translate>Ring upp</translate>
                        </v-btn>
                    </v-form>
                    <v-divider class="d-sm-none" />
                </v-col>
                <v-col
                    cols="12"
                    sm="6"
                    md="4"
                    class="d-flex align-center pt-0 pt-sm-3"
                >
                    <v-divider
                        vertical
                        class="mr-4 ml-1 d-none d-sm-block"
                    />
                    <div class="d-flex flex-grow-1 py-3 py-sm-0">
                        <v-btn
                            v-if="status.muted"
                            :title="$gettext('Unmute')"
                            icon
                            outlined
                            color="primary"
                            :disabled="!callControlEnabled"
                            @click="callControl('mute', 'false')"
                        >
                            <v-icon>mdi-microphone</v-icon>
                        </v-btn>
                        <v-btn
                            v-if="!status.muted"
                            :title="$gettext('Mute')"
                            icon
                            outlined
                            :disabled="!callControlEnabled"
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
                            :disabled="!callControlEnabled || status.muted"
                            hide-details
                            @change="callControl('volume', $event)"
                        />
                    </div>
                    <v-divider
                        vertical
                        class="mx-4"
                    />
                    <div>
                        <v-btn-confirm
                            :disabled="!callControlEnabled"
                            :title="$gettext('Reboot')"
                            color="error"
                            outlined
                            icon
                            @click="callControl('reboot')"
                        >
                            <v-icon>mdi-power</v-icon>
                        </v-btn-confirm>
                    </div>
                </v-col>
            </v-row>
        </v-card>
        <v-divider />
        <v-card
            flat
            tile
            class="grey lighten-5"
        >
            <v-card-text>
                <v-card class="mb-5">
                    <v-card-text v-if="!endpoint.id && endpointsLoading">
                        <v-skeleton-loader
                            type="image"
                            height="95"
                        />
                    </v-card-text>
                    <v-card-text
                        v-else
                        class="d-md-flex align-center"
                    >
                        <div>
                            <span class="text-h5">
                                {{ endpoint.product_name || $gettext('Okänd modell') }}
                                <template v-if="endpoint.ip">
                                    (<a
                                        target="_blank"
                                        :href="'https://' + endpoint.ip + '/'"
                                    >{{ endpoint.ip }}</a>)
                                </template>
                            </span>

                            <div class="d-flex align-center mt-2">
                                <EndpointStatus
                                    class="d-flex align-center"
                                    :endpoint="endpoint"
                                    text
                                />
                                <span
                                    v-if="status.uptime"
                                    class="ml-5"
                                >
                                    <strong>{{ $gettext('Drifttid') }}</strong>:
                                    {{ status.uptime|secondDuration }}
                                </span>
                                <span
                                    v-if="!status.uptime && endpoint.status && endpoint.status.ts_last_online"
                                    class="ml-5"
                                >
                                    <strong>{{ $gettext('Senast online') }}</strong>:
                                    {{ endpoint.status.ts_last_online|since }}
                                </span>
                                <span
                                    v-if="endpoint.status && endpoint.status.ts_last_check"
                                    class="ml-5"
                                >
                                    <strong>{{ $gettext('Senast uppdaterad') }}</strong>:
                                    {{ endpoint.status.ts_last_check|since }}
                                </span>
                            </div>
                        </div>
                        <div
                            class="d-flex ml-auto mt-4 mt-md-0"
                            style="flex-wrap: wrap;"
                        >
                            <div
                                v-if="endpoint.has_head_count"
                                class="extra-circle mr-5 my-2"
                            >
                                <v-icon
                                    class="extra-circle__icon"
                                    small
                                >
                                    mdi-seat
                                </v-icon>
                                <div class="text-h6 extra-circle__title">
                                    {{ endpoint.room_capacity || '?' }}
                                </div>
                                <small>{{ $gettext('Stolar') }}</small>
                            </div>
                            <div
                                v-if="endpoint.has_head_count"
                                class="extra-circle mr-5 my-2"
                                :class="{'extra-circle--blue': endpoint.status.head_count > 0}"
                            >
                                <v-icon
                                    class="extra-circle__icon"
                                    small
                                >
                                    mdi-account
                                </v-icon>
                                <div class="text-h6 extra-circle__title">
                                    <v-tooltip
                                        v-if="endpoint.status.head_count === -1"
                                        bottom
                                    >
                                        <template v-slot:activator="{ on }">
                                            <v-icon v-on="on">
                                                mdi-help
                                            </v-icon>
                                        </template>
                                        <translate>Ingen data från sensor - systemet är i standby eller inställningen för personräknare utanför samtal är inte aktiverad</translate>
                                    </v-tooltip>
                                    <span v-else>
                                        {{ endpoint.status.head_count || 0 }}
                                    </span>
                                </div>
                                <small>{{ $gettext('Personer') }}</small>
                            </div>
                            <div
                                v-if="hasCalendar"
                                class="extra-circle mr-5 my-2"
                                :class="{'extra-circle--green': activeMeetingDetails && endpoint.status.active_meeting }"
                            >
                                <v-icon
                                    class="extra-circle__icon"
                                    small
                                >
                                    {{ activeMeetingDetails && endpoint.status.active_meeting ? 'mdi-calendar' : 'mdi-calendar-blank' }}
                                </v-icon>
                                <v-icon>
                                    {{ activeMeetingDetails && endpoint.status.active_meeting ? 'mdi-check' : 'mdi-close' }}
                                </v-icon>
                                <small>{{ $gettext('Bokning') }}</small>
                            </div>
                        </div>
                    </v-card-text>
                </v-card>

                <v-divider class="my-5" />

                <v-row>
                    <v-col md="6">
                        <v-alert
                            v-if="statusLoaded && !status.has_direct_connection"
                            type="info"
                            class="mb-4"
                        >
                            <translate>Aktiv anslutning saknas.</translate>
                        </v-alert>

                        <v-expand-transition>
                            <v-alert
                                v-if="status.incoming"
                                color="info"
                                dense
                                text
                                icon="mdi-phone-in-talk"
                                prominent
                                class="mb-4"
                            >
                                <v-row align="center">
                                    <v-col class="grow">
                                        <translate>Inkommande samtal</translate>: {{ status.incoming }}
                                    </v-col>
                                    <v-col class="shrink d-flex">
                                        <v-btn
                                            color="primary"
                                            class="mr-4"
                                            @click="callControl('answer')"
                                        >
                                            <v-icon left>
                                                mdi-phone
                                            </v-icon>
                                            <translate>Svara</translate>
                                        </v-btn>
                                        <v-btn
                                            color="error"
                                            @click="callControl('reject')"
                                        >
                                            <v-icon left>
                                                mdi-phone-hangup
                                            </v-icon>
                                            <translate>Avvisa</translate>
                                        </v-btn>
                                    </v-col>
                                </v-row>
                            </v-alert>
                        </v-expand-transition>

                        <v-expand-transition>
                            <v-alert
                                v-if="status.in_call"
                                color="error"
                                text
                                icon="mdi-phone-in-talk"
                                prominent
                                class="mb-4"
                            >
                                <v-row align="center">
                                    <v-col class="grow">
                                        <div><translate>Samtal</translate>: <strong>{{ status.in_call }}</strong></div>
                                        <translate>Tid</translate>: {{ status.call_duration|secondDuration }}
                                    </v-col>
                                    <v-col class="shrink d-flex">
                                        <v-btn
                                            :loading="callControlLoading"
                                            color="error"
                                            @click="callControl('disconnect')"
                                        >
                                            <v-icon left>
                                                mdi-phone-hangup
                                            </v-icon>
                                            <translate>Lägg på</translate>
                                        </v-btn>
                                    </v-col>
                                </v-row>
                            </v-alert>
                        </v-expand-transition>

                        <v-expand-transition>
                            <v-alert
                                v-if="activeMeetingDetails && endpoint.status.active_meeting"
                                border="top"
                                type="error"
                                colored-border
                                icon="mdi-calendar"
                                class="mb-4 pt-6"
                                elevation="2"
                                prominent
                            >
                                <v-row align="center">
                                    <v-col class="grow">
                                        <translate>Just nu i möte</translate>:
                                        <strong>{{ activeMeetingDetails.title }}</strong>
                                        <div>
                                            {{ activeMeetingDetails.ts_start|timestamp }} -
                                            {{ activeMeetingDetails.ts_stop|timestamp }}
                                        </div>
                                        <template v-if="endpoint.has_head_count">
                                            <v-divider class="my-4" />
                                            <translate>Personer i rummet</translate>:
                                            <strong>{{ endpoint.head_count || 0 }} / {{ endpoint.room_capacity }}</strong>
                                        </template>
                                    </v-col>
                                    <v-col class="shrink d-flex">
                                        <v-btn
                                            color="primary"
                                            :to="activeMeetingDetails.details_url"
                                        >
                                            <translate>Gå till möte</translate>
                                        </v-btn>
                                    </v-col>
                                </v-row>
                            </v-alert>
                        </v-expand-transition>

                        <v-card class="mb-5">
                            <v-card-title class="overline">
                                <translate>Anslutningsinformation</translate>
                            </v-card-title>
                            <v-card-text v-if="!endpoint.id && endpointsLoading">
                                <v-skeleton-loader
                                    type="image"
                                    height="100"
                                />
                            </v-card-text>
                            <template v-else>
                                <v-card-text>
                                    <div class="mb-4">
                                        <ClipboardInput
                                            :label="$gettext('SIP')"
                                            :value="endpoint.sip"
                                        />
                                    </div>
                                    <ClipboardInput
                                        :label="$gettext('E-postadress')"
                                        :value="endpoint.email_address"
                                        :open-external="true"
                                        :external-value="'mailto:' + endpoint.email_address"
                                    />

                                    <div v-if="endpoint.sip_aliases && endpoint.sip_aliases.length">
                                        <p class="mb-0 mt-4">
                                            <translate>E-post/SIP-alias</translate>:
                                        </p>
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
                                    </div>
                                </v-card-text>
                                <v-divider />
                                <v-simple-table>
                                    <tbody>
                                        <tr v-if="connectionType">
                                            <th v-translate>
                                                Anslutning
                                            </th>
                                            <td>{{ connectionType.title }}</td>
                                        </tr>
                                        <tr v-if="endpoint.hostname">
                                            <th v-translate>
                                                Hostname
                                            </th>
                                            <td>
                                                <a
                                                    target="_blank"
                                                    :href="'https://' + endpoint.hostname + '/'"
                                                >{{ endpoint.hostname }}</a>
                                            </td>
                                        </tr>
                                        <tr v-if="endpoint.h323">
                                            <th v-translate>
                                                H323
                                            </th>
                                            <td>{{ endpoint.h323 }}</td>
                                        </tr>
                                        <tr v-if="endpoint.h323_e164">
                                            <th v-translate>
                                                E.164
                                            </th>
                                            <td>{{ endpoint.h323_e164 }}</td>
                                        </tr>
                                    </tbody>
                                </v-simple-table>
                            </template>
                        </v-card>

                        <v-card class="mb-5">
                            <v-card-title class="overline">
                                <translate>Historik</translate>
                            </v-card-title>
                            <v-card-text v-if="loadingStatus || loadingCallHistory">
                                <v-skeleton-loader
                                    type="image"
                                    height="100"
                                />
                            </v-card-text>
                            <v-list v-else-if="callHistory && status.has_direct_connection">
                                <v-hover
                                    v-for="item in callHistory"
                                    :key="item.history_id"
                                    v-slot:default="{ hover }"
                                >
                                    <v-list-item :class="{ 'grey lighten-5': hover }">
                                        <v-list-item-icon>
                                            <v-icon>mdi-phone</v-icon>
                                        </v-list-item-icon>

                                        <v-list-item-content>
                                            <v-list-item-title>{{ item.ts_start|timestamp }} - {{ item.type }}</v-list-item-title>
                                            <v-list-item-subtitle v-if="item.protocol != 'Spark'">
                                                {{ item.number }}
                                            </v-list-item-subtitle>
                                        </v-list-item-content>

                                        <v-fade-transition>
                                            <v-list-item-icon v-if="hover">
                                                <v-btn
                                                    color="primary"
                                                    class="mr-2"
                                                    outlined
                                                    small
                                                    @click.stop="displayCallInfo(item.history_id)"
                                                >
                                                    <translate>Se detaljer</translate>
                                                </v-btn>
                                                <v-btn
                                                    color="primary"
                                                    small
                                                    @click="callControl('dial', item.number)"
                                                >
                                                    <translate>Ring upp</translate>
                                                </v-btn>
                                            </v-list-item-icon>
                                        </v-fade-transition>
                                    </v-list-item>
                                </v-hover>
                            </v-list>
                            <v-card-text v-else>
                                <v-alert
                                    type="info"
                                    outlined
                                >
                                    <translate>Hittar ingen historik.</translate>
                                </v-alert>
                            </v-card-text>
                        </v-card>
                    </v-col>
                    <v-col md="6">
                        <v-alert
                            v-for="error in statusDiagnostics.errors"
                            :key="error.Description"
                            type="error"
                            icon="mdi-alert-octagon-outline"
                        >
                            <v-row align="center">
                                <v-col class="grow">
                                    {{ error.Description }}
                                </v-col>
                                <v-col
                                    v-if="error.References"
                                    class="shrink"
                                >
                                    <v-tooltip bottom>
                                        <template v-slot:activator="{ on, attrs }">
                                            <v-icon
                                                color="white"
                                                v-bind="attrs"
                                                v-on="on"
                                            >
                                                mdi-information
                                            </v-icon>
                                        </template>
                                        <span>{{ error.References }}</span>
                                    </v-tooltip>
                                </v-col>
                            </v-row>
                        </v-alert>

                        <v-card class="mb-5">
                            <v-card-title class="overline">
                                <translate>Systeminformation</translate>
                            </v-card-title>
                            <v-card-text v-if="!endpoint.id && endpointsLoading">
                                <v-skeleton-loader
                                    type="image"
                                    height="100"
                                />
                            </v-card-text>
                            <v-simple-table v-else>
                                <tbody>
                                    <tr>
                                        <th v-translate>
                                            Typ
                                        </th>
                                        <td><EndpointManufacturer :endpoint="endpoint" /></td>
                                    </tr>
                                    <tr>
                                        <th v-translate>
                                            Model
                                        </th>
                                        <td>{{ endpoint.product_name }}</td>
                                    </tr>
                                    <tr>
                                        <th v-translate>
                                            MAC-adress
                                        </th>
                                        <td>{{ endpoint.mac_address }}</td>
                                    </tr>
                                    <tr>
                                        <th v-translate>
                                            Serial
                                        </th>
                                        <td>{{ endpoint.serial_number }}</td>
                                    </tr>
                                    <tr v-if="endpoint.status">
                                        <th v-translate>
                                            Firmware
                                        </th>
                                        <td>
                                            <span class="d-inline-block mr-2">{{ endpoint.status.software_version }}</span>
                                            <span v-if="endpoint.status.software_release">({{ endpoint.status.software_release }})</span>
                                        </td>
                                    </tr>
                                </tbody>
                            </v-simple-table>
                        </v-card>

                        <v-card class="mb-5">
                            <v-card-title class="overline">
                                <translate>Detaljer</translate>
                            </v-card-title>
                            <v-card-text v-if="!endpoint.id && endpointsLoading">
                                <v-skeleton-loader
                                    type="image"
                                    height="100"
                                />
                            </v-card-text>
                            <v-simple-table v-else>
                                <tbody>
                                    <tr>
                                        <th v-translate>
                                            Organisation
                                        </th>
                                        <td>{{ endpoint.organizationPath }}</td>
                                    </tr>
                                    <tr>
                                        <th v-translate>
                                            Plats
                                        </th>
                                        <td>{{ endpoint.location || $gettext('Ingen') }}</td>
                                    </tr>
                                    <tr v-if="endpoint.status && endpoint.status.ts_last_event">
                                        <th v-translate>
                                            Senaste live event
                                        </th>
                                        <td>
                                            {{ endpoint.status.ts_last_event|since }}
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
                                    <tr v-if="upgradeStatus.status">
                                        <th v-translate>
                                            Uppgradering
                                        </th>
                                        <td>
                                            {{ upgradeStatus.status }}
                                            <div v-if="upgradeStatus.message">
                                                ({{ upgradeStatus.message }})
                                            </div>
                                        </td>
                                    </tr>

                                    <tr
                                        v-for="info in statusDiagnostics.info"
                                        :key="info.Description"
                                    >
                                        <th>{{ info.Description }}</th>
                                        <td>
                                            <v-tooltip
                                                v-if="info.References"
                                                bottom
                                            >
                                                <template v-slot:activator="{ on, attrs }">
                                                    <v-icon
                                                        color="grey darken-1"
                                                        v-bind="attrs"
                                                        v-on="on"
                                                    >
                                                        mdi-information
                                                    </v-icon>
                                                </template>
                                                <span>{{ info.References }}</span>
                                            </v-tooltip>
                                        </td>
                                    </tr>
                                </tbody>
                            </v-simple-table>
                            <v-card-text v-if="statusDiagnostics.warnings.length || statusDiagnostics.info.length">
                                <v-alert
                                    v-for="warning in statusDiagnostics.warnings"
                                    :key="warning.Description"
                                    type="warning"
                                    icon="mdi-alert-outline"
                                    dense
                                    text
                                >
                                    <v-row align="center">
                                        <v-col class="grow">
                                            {{ warning.Description }}
                                        </v-col>
                                        <v-col
                                            v-if="warning.References"
                                            class="shrink"
                                        >
                                            <v-tooltip bottom>
                                                <template v-slot:activator="{ on, attrs }">
                                                    <v-icon
                                                        color="grey darken-1"
                                                        v-bind="attrs"
                                                        v-on="on"
                                                    >
                                                        mdi-information
                                                    </v-icon>
                                                </template>
                                                <pre
                                                    v-if="warning.ReferencesData"
                                                    class="d-block"
                                                >{{ JSON.stringify(warning.ReferencesData, null, 2) }}</pre>
                                                <span v-else>{{ warning.References }}</span>
                                            </v-tooltip>
                                        </v-col>
                                    </v-row>
                                </v-alert>
                            </v-card-text>
                        </v-card>

                        <v-card
                            v-if="endpoint.has_head_count"
                            class="mb-5"
                        >
                            <v-card-title class="overline">
                                <translate>Rumsanvändning</translate>
                            </v-card-title>
                            <v-card-text v-if="!headCountGraphLoaded">
                                <v-skeleton-loader
                                    type="image"
                                    height="100"
                                />
                            </v-card-text>
                            <v-card-text v-else-if="!headCountGraph.count">
                                <v-alert
                                    type="info"
                                    outlined
                                >
                                    <translate>Hittar ingen statistik.</translate>
                                </v-alert>
                            </v-card-text>
                            <EndpointHeadCount
                                :id="id"
                                title=""
                                @statsLoaded="setHeadCountGraphData($event)"
                            />
                        </v-card>
                    </v-col>
                </v-row>
            </v-card-text>
        </v-card>
        <v-divider />

        <v-dialog
            v-model="editDialog"
            scrollable
            max-width="800"
            @cancel="getEndpoint"
        >
            <EndpointForm
                :id="id"
                @complete="editDialog = false; editDoneDialog = true"
            />
        </v-dialog>

        <v-dialog
            v-model="editDoneDialog"
            scrollable
            max-width="500"
        >
            <v-card>
                <v-card-title><translate>Ändringarna är sparade i Rooms</translate></v-card-title>
                <v-divider />
                <v-card-text class="pt-6">
                    <translate>Fortsätt till provisioneringsvyn för att skriva ev. ändringar till systemet</translate>
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-btn
                        color="primary"
                        :to="{
                            name: 'endpoint_provision',
                            params: {
                                id: endpoint.id,
                            },
                        }"
                    >
                        <translate>Fortsätt</translate>
                    </v-btn>
                    <v-spacer />
                    <v-btn
                        v-close-dialog
                        text
                        color="red"
                    >
                        <translate>Avbryt</translate>
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <v-dialog
            :value="!!callHistoryInfo"
            scrollable
            max-width="800"
            @input="callHistoryInfo = null"
        >
            <v-card>
                <v-card-title class="headline">
                    <translate>Detaljer</translate>
                </v-card-title>
                <v-divider />
                <v-card-text>
                    <pre>{{ callHistoryInfo }}</pre>
                </v-card-text>
                <v-divider />
                <v-card-actions>
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
    </div>
</template>

<script>
import { secondDuration } from '@/vue/helpers/datetime'
import { GlobalEventBus } from '@/vue/helpers/events'
import { endpointConnectionTypeChoices, endpointStatusChoices } from '@/vue/store/modules/endpoint/consts'

import EndpointForm from '@/vue/components/epm/endpoint/EndpointForm'
import EndpointManufacturer from '@/vue/components/epm/EndpointManufacturer'
import VBtnConfirm from '@/vue/components/VBtnConfirm'
import EndpointHeadCount from '@/vue/components/epm/endpoint/EndpointHeadCountGraph'
import SipSelector from '@/vue/components/epm/endpoint/SipAddressPicker'
import ClipboardInput from '@/vue/components/ClipboardInput'

import * as QS from 'query-string'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'

export default {
    components: {
        SipSelector,
        EndpointHeadCount,
        VBtnConfirm,
        EndpointManufacturer,
        EndpointForm,
        ClipboardInput,
    },
    filters: {
        secondDuration
    },
    mixins: [SingleEndpointMixin],
    data() {
        const endpoint = this.endpoint || {}
        return {
            emitter: new GlobalEventBus(this),
            editDialog: 'edit' in this.$route.query,
            editDoneDialog: false,
            status: endpoint.status || { status: endpoint.status_code, upgrade: {} },
            statusInterval: null,
            statusLoaded: false,
            loading: true,
            loadingCallHistory: false,
            loadingStatus: true,
            dialNumber: '',
            callHistory: null,
            callHistoryInfo: null,
            callControlLoading: false,
            callControlError: '',
            error: '',
            endpointConnectionTypeChoices,
            endpointStatusChoices,
            illustrationCalls: require('@/assets/images/illustrations/calls.svg'),
            activeMeetingDetails: null,
            headCountGraphLoaded: false,
            headCountGraph: {
                count: 1
            }
        }
    },
    computed: {
        hasCalendar() {
            return this.$store.state.site.hasCalendar
        },
        statusCode() {
            return this.endpointStatusChoices.find(s => s.id === this.endpoint.status_code)
        },
        connectionType() {
            return this.endpointConnectionTypeChoices.find(s => s.id === this.endpoint.connection_type)
        },
        callControlEnabled() {
            return this.statusLoaded && this.status.has_direct_connection
        },
        upgradeStatus() {
            return this.status && this.status.upgrade && this.status.upgrade.status ? this.status.upgrade : {}
        },
        statusDiagnostics() {
            const result = {
                errors: [],
                warnings: [],
                info: [],
            }

            if (!this.endpoint.status || !this.endpoint.status.diagnostics) return result

            this.endpoint.status.diagnostics.forEach(s => {
                if (s.References) {
                    try {
                        s.ReferencesData = QS.parse(s.References)
                    } catch (e) { //
                    }
                }
                if (s.Level === 'Info') result.info.push(s)
                else if (['Error', 'Critical'].includes(s.Level)) result.errors.push(s)
                else result.warnings.push(s)
            })

            return result
        }
    },
    watch: {
        endpoint() {
            if (this.status.status === undefined) {
                this.status = this.endpoint.status || { status: this.endpoint.status_code }
            }
        },
        'endpoint.status.active_meeting'() {
            this.updateActiveMeeting()
        },
        'status.in_call'() {
            if (this.status) this.loadCallHistory()
        }
    },
    mounted() {
        this.emitter.on('edit', () => (this.editDialog = true))
        this.emitter.on('delete', () => this.deleteEndpoint())
        this.emitter.on('refresh', () => {
            this.loading = true
            return Promise.all([
                this.getEndpoint(this.id),
                this.loadCallHistory(),
                this.updateStatus(),
            ])
        })

        this.updateActiveMeeting()
    },
    created() {
        this.statusInterval = setInterval(() => {
            this.updateStatus()
        }, 3000)
        this.error = ''
        if (this.status) {
            this.loadCallHistory()
        }
    },
    destroyed() {
        clearInterval(this.statusInterval)
    },
    methods: {
        loadCallHistory() {
            this.loadingCallHistory = true
            return this.$store
                .dispatch('endpoint/getCallHistory', this.id)
                .then(history => {
                    this.loadingCallHistory = false
                    this.callHistory = history
                })
                .catch(e => {
                    this.loadingCallHistory = false
                    this.error = e.toString()
                })
        },
        setHeadCountGraphData(data) {
            this.headCountGraphLoaded = true
            this.headCountGraph = data
        },
        updateActiveMeeting() {
            if (!this.endpoint.status || !this.endpoint.status.active_meeting) {
                this.activeMeetingDetails = null
                return
            }

            this.$store
                .dispatch('endpoint/getActiveMeeting', this.id)
                .then(details => {
                    this.activeMeetingDetails = details
                })
                .catch(() => true)
        },
        deleteEndpoint() {
            return this.$store.dispatch('endpoint/deleteEndpoint', this.id).then(() => {
                this.$router.push({ name: 'epm_list' })
            })
        },
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
        displayCallInfo(historyId) {
            return this.$store
                .dispatch('endpoint/getCallHistoryInfo', { endpointId: this.id, historyId })
                .then(info => {
                    this.callHistoryInfo = info.content
                })
        },
        updateStatus() {
            return this.$store
                .dispatch('endpoint/getStatus', this.id)
                .then(status => {
                    this.status = status || {}
                    this.statusLoaded = true
                    this.loading = false
                    this.loadingStatus = false
                    this.emitter.emit('loading', false)
                })
                .catch(() => true)
        },
    },
}
</script>

<style lang="scss">
.extra-circle {
    border: 2px solid #eee;
    width: 80px;
    height: 80px;
    border-radius: 160px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    position: relative;
}
.extra-circle--blue {
    border-color: lightblue;
}
.extra-circle--blue .extra-circle__icon {
    background: lightblue;
}
.extra-circle--green {
    border-color: lightgreen;
}
.extra-circle--green .extra-circle__icon {
    background: lightgreen;
}
.extra-circle__icon {
    position: absolute!important;
    top: -3px;
    right: -3px;
    background: #aaa;
    color: #fff!important;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 2rem;
}
.extra-circle__title {
    display: flex;
    align-items: center;
    line-height: 1!important;
}
</style>
