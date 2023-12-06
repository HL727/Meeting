<template>
    <v-form
        v-if="!initalLoading"
        ref="form"
        v-model="formValid"
        @submit.prevent="submit"
    >
        <v-card>
            <v-card-title>
                <translate>Testa regler</translate>
            </v-card-title>
            <v-divider />
            <v-tabs v-model="tab">
                <v-tab><translate>Nytt test</translate></v-tab>
                <v-tab :disabled="!hasResult">
                    <translate>Resultat</translate>
                </v-tab>
            </v-tabs>
            <v-divider />
            <v-card-text>
                <template v-if="tab === 0">
                    <div v-if="initalLoading">
                        <v-progress-circular indeterminate />
                    </div>

                    <v-text-field
                        v-model="form.local_alias"
                        :rules="formRules.required"
                        clearable
                        :label="$gettext('Destination alias')"
                        persistent-hint
                    />

                    <v-text-field
                        v-model="form.remote_alias"
                        clearable
                        :label="$gettext('Source alias address')"
                    />

                    <v-radio-group
                        v-model="form.call_direction"
                        row
                    >
                        <v-radio
                            value="dial_in"
                            :label="$gettext('Incoming')"
                        />
                        <v-radio
                            value="dial_out"
                            :label="$gettext('Outgoing')"
                        />
                    </v-radio-group>

                    <template v-if="form.call_direction == 'dial_in'">
                        <v-select
                            v-model="form.location"
                            :label="$gettext('Call being handled in location')"
                            clearable
                            :items="sourceLocations"
                            item-text="name"
                            item-value="name"
                        />
                        <v-checkbox
                            v-model="form.registered"
                            :label="$gettext('Registered device')"
                        />
                        <v-select
                            v-model="form.protocol"
                            :label="$gettext('Source location type')"
                            clearable
                            :items="protocols"
                            item-value="key"
                        />
                    </template>
                </template>
                <template v-if="tab === 1 && result">
                    <v-card
                        v-if="result.conference"
                        class="mb-3"
                    >
                        <v-card-text>
                            <v-icon color="orange">
                                mdi-alert
                            </v-icon>
                            <translate>Ditt test gav först en träff på följande mötesrum</translate>:

                            <v-divider class="my-4" />
                            <div>
                                <strong v-translate>Mötesrumsnamn</strong><br>
                                <router-link :to="{ name: 'pexip_cospaces_details', params: { id: result.conference.id } }">
                                    {{ result.conference.name }}
                                </router-link>
                            </div>
                        </v-card-text>
                    </v-card>
                    <v-data-table
                        :items="result.rules"
                        :headers="headers"
                        sort-by="priority"
                    >
                        <template v-slot:item.priority="{ item }">
                            <v-avatar
                                left
                                class="blue-grey lighten-5"
                                size="32"
                            >
                                {{ item.priority }}
                            </v-avatar>
                        </template>
                        <template v-slot:item.name="{ item }">
                            <router-link
                                to="#"
                                @click.native.prevent="$emit('update:editRule', item.id)"
                            >
                                {{ item.name }}
                            </router-link>
                        </template>
                    </v-data-table>
                </template>
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-btn
                    v-if="tab === 0"
                    :loading="loading"
                    color="primary"
                    type="submit"
                >
                    <translate>Skicka test</translate>
                </v-btn>

                <v-spacer />

                <v-btn
                    v-close-dialog
                    class="ml-2"
                    text
                    color="red"
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
import { $gettext } from '@/vue/helpers/translate'

export default {
    props: {
        provider: { type: Number, required: false, default: undefined },
    },
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            tab: 0,
            loading: false,
            result: null,
            hasResult: false,
            formValid: false,
            error: null,
            initialLoading: false,
            form: {
                local_alias: '',
                remote_alias: 'sip:1234@example.org',
                call_direction: 'dial_in',
                protocol: 'sip',
                is_registered: false,
                location: '',
            },
            formRules: {
                required: [v => !!v || $gettext('Värdet måste fyllas i')]
            },
            protocols: [
                {
                    key: 'webrtc',
                    text: 'Infinity Connect (WebRTC / RTMP)'
                },
                {
                    key: 'sip',
                    text: $gettext('SIP')
                },
                {
                    key: 'mssip',
                    text: 'Lync / Skype for Business (MS-SIP)'
                },
                {
                    key: 'h323',
                    text: $gettext('H.323')
                },
            ],
            headers: [
                { value: 'priority', text: $gettext('Prio'), width: 80  },
                { value: 'name', text: $gettext('Namn') },
            ],
        }
    },
    computed: {
        relatedObjects() {
            return this.$store.state.policy_rule.related
        },
        sourceLocations() {
            return Object.values(this.relatedObjects.system_location || {})
        },
    },
    created() {
        this.initialLoading = true
        return this.$store.dispatch('policy_rule/getRelatedObjects', { provider: this.provider }).then(() => {
            this.initialLoading = false
        }).catch(e => this.error = e)
    },
    methods: {
        submit() {
            if (!this.$refs.form.validate()) return

            this.loading = true

            return this.$store.dispatch('policy_rule/trace', { provider: this.provider, ...this.form }).then(data => {
                this.result = data
                this.hasResult = true
                this.loading = false
                this.tab = 1
            })
        },
    },
}
</script>
