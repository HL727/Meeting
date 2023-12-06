<template>
    <div>
        <v-data-table
            :loading="loading"
            :items="activeParticipants"
            :headers="headers"
            :items-per-page="100"
            multiple
            disable-sort
        >
            <template v-slot:item.indicators="{ item }">
                <div class="d-flex">
                    <v-icon>mdi-account</v-icon>
                    <v-icon v-if="item.is_presenting">
                        mdi-play
                    </v-icon>
                    <v-icon v-if="item.is_secure">
                        mdi-shield
                    </v-icon>
                </div>
            </template>
            <template v-slot:item.name="{ item }">
                <div class="py-2">
                    <span
                        v-if="!item.name"
                        class="grey--text"
                    ><translate>Inget namn</translate></span>
                    <strong v-else>{{ item.name }}</strong>
                    <br>
                    {{ item.remote }}
                </div>
            </template>
            <template v-slot:item.ts_start="{ item }">
                {{ item.ts_start|duration }}
            </template>
            <template v-slot:item.layout="{ item }">
                <v-select
                    style="max-width: 15rem;"
                    :items="callLayoutChoices"
                    :label="$gettext('Layout')"
                    item-text="title"
                    item-value="id"
                    @change="item"
                />
            </template>
            <template v-slot:item.actions="{ item }">
                <div class="d-flex justify-end">
                    <v-progress-circular
                        size="30"
                        :indeterminate="item.loading"
                        :style="{ opacity: item.loading ? 1 : 0 }"
                        color="primary"
                    />

                    <v-tooltip
                        v-if="call.support_control"
                        bottom
                    >
                        <template v-slot:activator="{ on }">
                            <v-btn
                                :disabled="item.loading"
                                :color="item.is_moderator ? 'amber' : ''"
                                x-small
                                fab
                                class="ml-2"
                                v-on="on"
                                @click="setModerator(item, !item.is_moderator)"
                            >
                                <v-icon v-if="item.is_moderator">
                                    mdi-account-star
                                </v-icon>
                                <v-icon v-else>
                                    mdi-star-off
                                </v-icon>
                            </v-btn>
                        </template>
                        <span><translate>Värd</translate></span>
                    </v-tooltip>

                    <v-tooltip
                        v-if="call.support_control"
                        bottom
                    >
                        <template v-slot:activator="{ on }">
                            <!-- TODO: fix for muting video -->
                            <v-btn
                                v-if="isAcano"
                                :disabled="item.loading"
                                :color="item.video_muted ? '' : 'success'"
                                x-small
                                fab
                                class="ml-2"
                                v-on="on"
                                @click="setParticipantVideoMute(item, !item.video_muted)"
                            >
                                <v-icon v-if="!item.audio_muted">
                                    mdi-video
                                </v-icon>
                                <v-icon v-else>
                                    mdi-video-off
                                </v-icon>
                            </v-btn>
                        </template>
                        <span><translate>Video på/av</translate></span>
                    </v-tooltip>

                    <v-tooltip
                        v-if="call.support_control"
                        bottom
                    >
                        <template v-slot:activator="{ on }">
                            <v-btn
                                :disabled="item.loading"
                                :color="item.audio_muted ? '' : 'success'"
                                x-small
                                fab
                                class="ml-2"
                                v-on="on"
                                @click="setParticipantAudioMute(item, !item.audio_muted)"
                            >
                                <v-icon v-if="!item.audio_muted">
                                    mdi-microphone
                                </v-icon>
                                <v-icon v-else>
                                    mdi-microphone-off
                                </v-icon>
                            </v-btn>
                        </template>
                        <span><translate>Mikrofon på/av</translate></span>
                    </v-tooltip>

                    <v-tooltip bottom>
                        <template v-slot:activator="{ on }">
                            <v-btn
                                :disabled="item.loading"
                                color="error"
                                x-small
                                fab
                                class="ml-2"
                                v-on="on"
                                @click="hangupParticipant(item)"
                            >
                                <v-icon>mdi-close</v-icon>
                            </v-btn>
                        </template>
                        <span><translate>Ta bort deltagaren från samtalet</translate></span>
                    </v-tooltip>

                    <v-tooltip bottom>
                        <template v-slot:activator="{ on }">
                            <v-btn
                                :disabled="item.loading"
                                color="primary"
                                outlined
                                x-small
                                fab
                                class="ml-2"
                                v-on="on"
                                @click="callInformationItem = item"
                            >
                                <v-icon>mdi-information</v-icon>
                            </v-btn>
                        </template>
                        <span><translate>Samtalsinformation</translate></span>
                    </v-tooltip>
                </div>
            </template>
        </v-data-table>

        <CallParticipantDetailsDialog v-model="callInformationItem" />
    </div>
</template>
<script>
import { translate } from 'vue-gettext'
const $gettext = translate.gettext

import { since } from '@/vue/helpers/datetime'

import { callLayoutChoices } from '@/vue/store/modules/call/consts'

import CallParticipantDetailsDialog from '@/vue/components/call/CallParticipantDetailsDialog'

export default {
    name: 'CallParticipantsGrid',
    components: { CallParticipantDetailsDialog },
    props: {
        loading: Boolean,
        participants: { type: Array, default() { return [] }},
        provider: { type: [Number, String], default: '' },
        call: { type: [Object], default: () => ({}) },
        allParticipantsLoading: Boolean,
    },
    data() {
        return {
            page: {},
            pagination: { page: 1, itemsPerPage: 10 },
            callLayoutChoices,
            error: null,
            loadingParticipants: {},
            callInformationItem: null,
            participantOverrides: {},
        }
    },
    computed: {
        callInformation() {
            if (!this.callInformationItem) return []

            return Object.entries(this.callInformationItem)
                .filter(i => i[0] !== 'loading')
                .map(i => ({ key: i[0], title: i[1] }))
        },
        isPexip() {
            return this.$store.state.site.isPexip
        },
        isAcano() {
            return !this.isPexip
        },
        headers() {
            const tableHeaders = [
                { text: '', value: 'indicators', align: 'start', width: 16 },
                { text: $gettext('Deltagare'), value: 'name' },
                { text: $gettext('Längd'), value: 'ts_start' },
            ]

            if (this.isAcano) {
                tableHeaders.push({ text: $gettext('Layout'), value: 'layout' })
            }

            tableHeaders.push({ text: '', align: 'end', value: 'actions' })

            return tableHeaders
        },
        activeParticipants() {
            return (this.participants || []).map(part => {
                return {
                    ...part,
                    duration: since(part.ts_start || part.start_time),
                    loading: this.loadingParticipants[part.id] || this.allParticipantsLoading,
                    ...this.participantOverrides[part.id],
                }
            })
        }
    },
    watch: {
        error(newValue) {
            if (newValue) {
                this.$emit('error', newValue)
            }
        }
    },
    methods: {
        /** State is not updated live on pexip api operations.
         * Fake state a while to give the server time to notify */
        overrideParticipantState(participant, values) {
            this.participantOverrides[participant.id] = {
                ...this.participantOverrides[participant.id],
                ...values,
            }
            // TODO wait for next update after timeout
            setTimeout(() => {
                Object.entries(values).forEach(([k, v]) => {
                    if (!this.participantOverrides[participant.id]) return
                    if (this.participantOverrides[participant.id][k] === v) delete this.participantOverrides[participant.id][k]
                })
            }, 5000)
        },
        hangupParticipant(participant) {
            this.loadingParticipants[participant.id] = true

            return this.$store.dispatch('call/hangupParticipant', {
                callId: this.id,
                id: participant.id,
                provider: this.provider,
            }).then(() => {
                this.loadingParticipants[participant.id] = false
            }).catch(e => this.error = e)
        },
        setParticipantAudioMute(participant, newValue) {
            this.loadingParticipants[participant.id] = true
            this.overrideParticipantState(participant, { audio_muted: newValue })

            return this.$store.dispatch('call/muteAudioParticipant', {
                callId: this.id,
                id: participant.id,
                value: newValue,
                provider: this.provider,
            }).then(() => {
                this.loadingParticipants[participant.id] = false
            }).catch(e => this.error = e)
        },
        setParticipantVideoMute(participant, newValue) {
            // TODO: fix for CMS

            this.loadingParticipants[participant.id] = true
            this.overrideParticipantState(participant, { video_muted: newValue })

            return this.$store.dispatch('call/muteVideoParticipant', {
                callId: this.id,
                id: participant.id,
                value: newValue,
                provider: this.provider,
            }).then(() => {
                this.loadingParticipants[participant.id] = false
            }).catch(e => this.error = e)
        },
        setModerator(participant, newValue) {
            this.loadingParticipants[participant.id] = true
            this.overrideParticipantState(participant, { is_moderator: newValue })

            return this.$store.dispatch('call/makeParticipantModerator', {
                callId: this.id,
                id: participant.id,
                value: newValue,
                provider: this.provider,
            }).then(() => {
                this.loadingParticipants[participant.id] = false
            }).catch(e => this.error = e)
        },
    },
}
</script>
