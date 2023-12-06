<template>
    <Page
        icon="mdi-google-classroom"
        :title="callName"
        search-width=""
        :actions="[
            { type: 'refresh', click: () => fetchData() },
        ]"
        :loading="loading.data"
    >
        <template
            v-if="!callCompleted && call.support_control"
            v-slot:actions
        >
            <v-list-item-icon class="ma-0 align-self-center">
                <v-tooltip bottom>
                    <template v-slot:activator="{ on }">
                        <v-btn
                            v-if="isAcano"
                            :loading="loading.setVideoAll"
                            :color="toggle.video ? 'error' : 'success'"
                            outlined
                            small
                            fab
                            class="ml-2 disabled"
                            v-on="on"
                            @click="toggleVideoAll"
                        >
                            <v-icon v-if="!toggle.video">
                                mdi-video
                            </v-icon>
                            <v-icon v-else>
                                mdi-video-off
                            </v-icon>
                        </v-btn>
                    </template>
                    <span><translate>Video på/av för samtliga deltagare</translate></span>
                </v-tooltip>
            </v-list-item-icon>
            <v-list-item-icon class="ma-0 align-self-center">
                <v-tooltip bottom>
                    <template v-slot:activator="{ on }">
                        <v-btn
                            :loading="loading.setAudioAll"
                            :color="toggle.audio ? 'error' : 'success'"
                            outlined
                            small
                            fab
                            class="ml-2"
                            v-on="on"
                            @click="toggleAudioAll"
                        >
                            <v-icon v-if="!toggle.audio">
                                mdi-microphone
                            </v-icon>
                            <v-icon v-else>
                                mdi-microphone-off
                            </v-icon>
                        </v-btn>
                    </template>
                    <span><translate>Mikrofon på/av för samtliga deltagare</translate></span>
                </v-tooltip>
            </v-list-item-icon>

            <v-divider
                vertical
                class="ml-4 mr-2"
            />
            <v-list-item-icon class="ma-0 align-self-center">
                <v-tooltip bottom>
                    <template v-slot:activator="{ on }">
                        <v-btn
                            color="primary"
                            small
                            fab
                            class="ml-2"
                            v-on="on"
                            @click="addParticipantForm = true"
                        >
                            <v-icon>mdi-account-plus</v-icon>
                        </v-btn>
                    </template>
                    <span><translate>Ring upp deltagare</translate></span>
                </v-tooltip>
            </v-list-item-icon>

            <v-list-item-icon
                class="ma-0 align-self-center"
            >
                <v-tooltip bottom>
                    <template v-slot:activator="{ on }">
                        <v-btn
                            color="error"
                            outlined
                            small
                            fab
                            class="ml-2"
                            v-on="on"
                            @click="hangup"
                        >
                            <v-icon>
                                mdi-phone
                            </v-icon>
                        </v-btn>
                    </template>
                    <span><translate>Lägg på</translate></span>
                </v-tooltip>
            </v-list-item-icon>

            <v-divider
                vertical
                class="ml-4 mr-2"
            />
        </template>

        <template
            v-if="!callCompleted"
            v-slot:search
        >
            <div
                class="d-flex align-center"
                style="max-width:100%;"
            >
                <ClipboardInput
                    v-if="call.cospace_data && call.cospace_data.web_url"
                    class="mr-4"
                    style="width:20rem;max-width:100%;"
                    :label="$gettext('Webb')"
                    :value="call.cospace_data && call.cospace_data.web_url ? call.cospace_data.web_url : ''"
                    outlined
                    dense
                    open-external
                />
                <ClipboardInput
                    v-if="callFrom"
                    class="mr-4"
                    style="width:20rem;max-width:100%;"
                    :label="$gettext('SIP')"
                    :value="callFrom"
                    :external-value="`sip:${callFrom}`"
                    outlined
                    dense
                    open-external
                />
            </div>
        </template>

        <template
            v-if="call.cospace_data && call.cospace_data.id && !callCompleted"
            v-slot:filter
        >
            <v-list-item-icon
                class="ma-0 align-self-center"
            >
                <v-btn
                    color="primary"
                    class="ml-2"
                    small
                    :disabled="loading.data"
                    :to="{
                        name: isPexip ? 'pexip_cospaces_details' : 'cospaces_details',
                        params: { id: call.cospace_data.id }
                    }"
                >
                    <v-icon
                        left
                        dark
                    >
                        mdi-door-closed
                    </v-icon>
                    {{ $ngettext('Mötesrum', 'Mötesrum', 1) }}
                </v-btn>
            </v-list-item-icon>

            <v-list-item-icon
                class="ma-0 align-self-center"
            >
                <v-btn
                    color="primary"
                    class="ml-2"
                    small
                    :disabled="loading.data"
                    :to="{name: 'cospaces_invite', params: {id: call.cospace_data.id }}"
                >
                    <v-icon
                        left
                        dark
                    >
                        mdi-email-outline
                    </v-icon>
                    <translate>Inbjudan</translate>
                </v-btn>
            </v-list-item-icon>
        </template>

        <template
            v-if="!callCompleted"
            v-slot:content
        >
            <ErrorMessage :error="error" />

            <CallParticipantsGrid
                :loading="loading.data"
                :all-participants-loading="loading.setVideoAll || loading.setAudioAll"
                :call="call"
                :participants="participants"
                :provider="provider"
                @error="error = $event"
            />

            <v-dialog
                v-model="addParticipantForm"
                scrollable
                :max-width="400"
            >
                <DialParticipantForm
                    :call="call"
                    :call-from="callFrom"
                    :call-from-choices="aliasUris"
                />
            </v-dialog>
        </template>
        <template
            v-else
            v-slot:content
        >
            <v-alert
                type="info"
                class="mt-4"
            >
                <translate>Samtalet har avslutats</translate>
            </v-alert>
        </template>
    </Page>
</template>

<script>
import Page from '@/vue/views/layout/Page'

import DialParticipantForm from '@/vue/components/call/DialParticipantForm'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import CallParticipantsGrid from '@/vue/components/call/CallParticipantsGrid'
import ClipboardInput from '@/vue/components/ClipboardInput'

export default {
    name: 'PexipCallControl',
    components: { Page, ClipboardInput, CallParticipantsGrid, ErrorMessage, DialParticipantForm },
    props: {
        id: { type: [String, Number], required: true },
    },
    data() {
        return {
            loading: {
                data: true,
                background: true,
                setVideoAll: false,
                setAudioAll: false
            },
            updateInterval: null,
            addParticipantForm: false,
            calls: {},
            callName: null,
            error: null,
            callCompleted: false,
            toggle: {
                video: false,
                audio: false
            }
        }
    },
    computed: {
        isPexip() {
            return this.$store.state.site.isPexip
        },
        isAcano() {
            return !this.isPexip
        },
        call() {
            return this.$store.state.call.calls[this.id] || {}
        },
        settings() {
            return this.$store.state.site
        },
        participants() {
            return (this.$store.getters['call/callParticipants'] || {})[this.id]
        },
        cospace() {
            return this.call.cospace || this.$route.query.cospace
        },
        aliasUris() {
            const cospace = this.call.cospace_data
            if (!cospace || !cospace.aliases) return []
            return cospace.aliases.map(a => a.alias)
        },
        provider() {
            return this.$route.query.provider || undefined
        },
        callFrom() {
            if (this.call.cospace_data && this.call.cospace_data.sip_uri) {
                return this.call.cospace_data.sip_uri
            }

            if (this.participants && this.participants.length) {
                return this.participants.filter(l => !l.is_streaming && l.local)[0]?.local || ''
            }

            return ''
        }
    },
    watch: {
        'call.name'(newValue) {
            if (newValue) {
                this.callName = newValue
            }
        }
    },
    mounted() {
        this.callName = this.call.name
        this.restartFetchInterval()

        return Promise.all([
            this.fetchCall(),
            this.fetchData(),
        ])
    },
    destroyed() {
        clearInterval(this.updateInterval)
    },
    methods: {
        toggleAudioAll() {
            this.toggle.audio = !this.toggle.audio
            this.loading.setAudioAll = true

            return this.$store
                .dispatch('call/muteAudioForAllParticipants', {
                    callId: this.id,
                    value: this.toggle.audio,
                })
                .then(() => {
                    this.loading.setAudioAll = false
                    return this.fetchData()
                })
                .catch(e => {
                    this.loading.setAudioAll = false
                    this.error = e
                })
        },
        toggleVideoAll() {
            this.toggle.video = !this.toggle.video
            this.loading.setVideoAll = true

            return this.$store
                .dispatch('call/muteVideoForAllParticipants', {
                    callId: this.id,
                    value: this.toggle.video,
                })
                .then(() => {
                    this.loading.setVideoAll = false
                    return this.fetchData()
                })
                .catch(e => {
                    this.loading.setVideoAll = false
                    this.error = e
                })
        },
        restartFetchInterval() {
            clearInterval(this.updateInterval)
            this.updateInterval = setInterval(() => {
                return this.fetchData(true)
            }, 3000)
        },
        fetchData(loop=false) {
            if (!loop) {
                this.loading.data = true
                this.restartFetchInterval()
            }

            if (loop && this.loading.background) return
            this.loading.background = true

            return Promise.all([
                this.fetchCall(true),
                this.$store.dispatch('call/getCallParticipants', {
                    callId: this.id,
                    cospace: this.cospace,
                    provider: this.provider,
                }),
            ])
                .then(() => {
                    this.loading.data = false
                    this.loading.background = false
                    this.error = null
                })
                .catch(e => {
                    this.loading.data = false
                    this.loading.background = false
                    this.error = e
                })
        },
        fetchCall(compact=false) {
            return this.$store
                .dispatch(compact ? 'call/getCallStatus' : 'call/getCallData', {
                    callId: this.id,
                    cospace: this.cospace,
                    provider: this.provider,
                })
                .then(() => (this.error = null))
                .catch(e => {
                    this.error = e
                    if (e.status === 404) {
                        this.callCompleted = true
                        clearInterval(this.updateInterval)
                    }
                })
        },
        hangup() {
            this.$store.dispatch('call/hangup', {
                callId: this.id,
                cospace: this.cospace,
                provider: this.provider,
            })
        },
    },
}
</script>
