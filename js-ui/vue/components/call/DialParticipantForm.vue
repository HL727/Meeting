<template>
    <v-form @submit.prevent="dial">
        <v-card>
            <v-card-title>
                <span v-if="hasCall"><translate>Ring upp deltagare</translate></span>
                <span v-else><translate>Starta nytt möte</translate></span>
            </v-card-title>
            <v-divider />
            <v-card-text>
                <template v-if="isPexip">
                    <v-combobox
                        v-if="callFromChoices.length"
                        v-model="form.local"
                        :items="callFromChoices"
                    />
                    <CoSpacePicker
                        v-else
                        v-model="form.local"
                        :label="$gettext('Välj mötesrum')"
                        item-value="sip_uri"
                        item-search="sip_uri"
                    />
                    <SipAddressPicker
                        v-model="form.remote"
                        :label="$gettext('Ring till address')"
                    />

                    <v-checkbox
                        v-model="form.moderator"
                        :label="$gettext('Moderator')"
                    />

                    <v-select
                        v-if="isAdmin"
                        v-model="form.system_location"
                        :label="$gettext('Systemplats')"
                        :items="locationChoices"
                    />

                    <v-checkbox
                        v-model="form.automatic_routing"
                        :label="$gettext('Automatisk routing')"
                    />

                    <v-select
                        v-if="!form.automatic_routing"
                        v-model="form.protocol"
                        :label="$gettext('Protokoll')"
                        :items="protocolChoices"
                        item-text="title"
                        item-value="key"
                    />

                    <v-select
                        v-model="form.call_type"
                        :label="$gettext('Video and audio')"
                        :items="pexipCallModeChoices"
                        item-text="title"
                        item-value="id"
                    />
                    <v-text-field
                        v-if="form.call_type == 'streaming'"
                        v-model="form.remote_presentation"
                        :label="$gettext('Separat adress för presentation')"
                    />
                </template>
                <template v-else>
                    <CoSpacePicker
                        v-if="!hasCall"
                        v-model="form.local"
                        :label="$gettext('Välj mötesrum')"
                        item-value="id"
                    />
                    <v-text-field
                        v-model="form.remote"
                        :label="$gettext('Ring till address')"
                    />
                    <v-select
                        v-model="form.layout"
                        :label="$gettext('Layout')"
                        :items="callLayoutChoices"
                        item-text="title"
                        item-value="id"
                    />
                </template>

                <ErrorMessage :error="error" />
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-btn
                    :loading="loading"
                    color="primary"
                    type="submit"
                >
                    <span v-if="hasCall"><translate>Ring upp</translate></span>
                    <span v-else><translate>Starta möte</translate></span>
                </v-btn>
                <v-spacer />
                <v-btn
                    v-if="showCancel"
                    v-close-dialog
                    text
                    color="red"
                    @click.prevent="$emit('cancel')"
                >
                    <translate>Avbryt</translate>
                    <v-icon
                        right
                        dark
                    >
                        mdi-close
                    </v-icon>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-form>
</template>
<script>
import { closeDialog } from '@/vue/helpers/dialog'
import { pexipCallModeChoices, callLayoutChoices } from '@/vue/store/modules/call/consts'

import ErrorMessage from '@/vue/components/base/ErrorMessage'
import CoSpacePicker from '@/vue/components/cospace/CoSpacePicker'
import SipAddressPicker from '@/vue/components/epm/endpoint/SipAddressPicker'

export default {
    name: 'DialParticipantForm',
    components: { SipAddressPicker, CoSpacePicker, ErrorMessage },
    props: {
        call: { type: Object, default() { return {} } },
        callFrom: { type: String, default: '' },
        callFromChoices: { type: Array, default: () => [] },
        showCancel: Boolean,
    },
    data() {
        return {
            loading: false,
            callLayoutChoices,
            pexipCallModeChoices,
            locationChoices: [],
            form: {
                moderator: true,
                layout: 'automatic',
                call_type: 'video',
                remote: '',
                remote_presentation: '',
                local: this.callFrom || (this.callFromChoices.length ? this.callFromChoices[0] : ''),
                system_location: '',
                automatic_routing: true,
                protocol: 'sip',
            },
            error: null,
            protocolChoices: [
                { key: 'h323', title: 'H.323' },
                { key: 'mssip', title: 'Lync / Skype for business (MS-SIP)' },
                { key: 'sip', title: 'SIP' },
                { key: 'rtmp', title: 'RTMP' },
                { key: 'gms', title: 'Google Meet' },
                { key: 'teams', title: 'Microsoft Teams' },
            ],
        }
    },
    computed: {
        hasCall() {
            return Object.keys(this.call).length > 0
        },
        isAdmin() {
            const settings = this.$store.getters['settings']
            return settings.perms.admin
        },
        isPexip() {
            return this.$store.state.site.isPexip
        },
    },
    watch: {
        callFrom(newValue) {
            this.form.local = newValue
        }
    },
    mounted() {
        if (this.isPexip && this.isAdmin) {
            this.loadSystemLocations()
        }
    },
    methods: {
        dial() {
            this.loading = true
            this.error = null

            const data = { ...this.form }

            data.role = data.moderator ? 'moderator' : 'guest'
            if (this.form.call_type !== 'streaming') this.form.remote_presentation = undefined

            return this.$store.dispatch('call/dial', {
                callId: this.call ? this.call.id : null,
                data: data
            }).then(() => {
                this.loading = false
                closeDialog(this)
                this.$emit('complete')
            }).catch(e => {
                this.loading = false
                this.error = e
            })
        },
        loadSystemLocations() {
            return this.$store.api().get('provider/related_policy_objects/').then(response => {
                this.locationChoices = response.system_location.map(location => location.name)

                if (this.form.system_location) return

                if (this.hasCall && this.call.legs) {
                    this.form.system_location = this.call.legs[0].system_location
                } else if (this.locationChoices.length) {
                    this.form.system_location = this.locationChoices[0]
                }
            })
        }
    }
}
</script>
