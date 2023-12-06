<template>
    <v-form
        v-if="!loading"
        ref="form"
        v-model="formValid"
        @submit.prevent="submit"
    >
        <v-card>
            <v-progress-linear
                :active="loading"
                indeterminate
                absolute
                top
            />
            <v-card-title class="headline">
                {{ id ? $gettext('Uppdatera mötesrum') : $gettext('Lägg till mötesrum') }}
            </v-card-title>
            <v-divider />
            <v-card-text>
                <v-alert
                    v-if="loadedData.id && (!loadedData.editable_accessmethods || loadedData.auto_generated)"
                    type="warning"
                    icon="mdi-alert"
                    text
                >
                    <translate v-if="loadedData.auto_generated">
                        VARNING: Detta rum är autogenererat, och det är därför inte säkert att det går att redigera.
                    </translate>&nbsp;
                    <translate v-if="!loadedData.editable_accessmethods">
                        Detta rum har flera anslutningsmetoder som inte har fullt stöd för redigering i den här versionen.
                    </translate>&nbsp;
                    <translate>Inställningar kommer att skrivas över.</translate>
                    <div class="mt-3">
                        <v-btn
                            color="primary"
                            small
                            depressed
                            :to="{ name: 'cospaces_edit', params: { id: id }}"
                        >
                            <translate>Gå till förenklad redigering</translate>
                        </v-btn>
                    </div>
                </v-alert>
                <v-text-field
                    v-model="form.name"
                    :error-messages="errors.name ? errors.name : []"
                    :rules="rules.name"
                    clearable
                    :label="$gettext('Namn') + ' (*)'"
                    :counter="256"
                />
                <v-text-field
                    v-model="form.uri"
                    :error-messages="errors.uri ? errors.uri : []"
                    :rules="rules.uri"
                    clearable
                    :label="$gettext('URI')"
                    :counter="256"
                />
                <v-text-field
                    v-if="id"
                    v-model="form.call_id"
                    type="number"
                    :error-messages="errors.call_id ? errors.call_id : []"
                    :rules="rules.call_id"
                    :label="$gettext('Call ID')"
                />

                <v-card
                    v-if="!id"
                    class="mb-4"
                >
                    <v-card-text class="py-1">
                        <v-row
                            dense
                            no-gutters
                        >
                            <v-col>
                                <v-checkbox
                                    v-model="generateCallId"
                                    :label="$gettext('Generera numeriskt rumsnummer')"
                                />
                            </v-col>
                            <v-col cols="4">
                                <v-select
                                    v-if="!id && generateCallId"
                                    v-model="form.call_id_generation_method"
                                    :label="$gettext('Skapa automatiskt numeriskt adress')"
                                    :items="[
                                        { value: 'random', text: $gettext('Slumpa numeriskt ID') },
                                        { value: 'increase', text: $gettext('Nästa numeriska ID i nummerföljd') },
                                    ]"
                                />

                                <v-text-field
                                    v-if="!generateCallId"
                                    v-model="form.call_id"
                                    type="number"
                                    :error-messages="errors.call_id ? errors.call_id : []"
                                    :rules="rules.call_id"
                                    :label="$gettext('Call ID')"
                                />
                            </v-col>
                        </v-row>
                    </v-card-text>
                </v-card>
                <v-card>
                    <v-card-text class="py-1">
                        <v-row
                            dense
                            no-gutters
                        >
                            <v-col>
                                <v-checkbox
                                    v-model="form.enable_passcode"
                                    :error-messages="errors.enable_passcode ? errors.enable_passcode : []"
                                    :rules="rules.enable_passcode"
                                    :label="$gettext('Använd PIN-kod')"
                                />
                            </v-col>
                            <v-col cols="4">
                                <v-text-field
                                    v-if="form.enable_passcode"
                                    v-model="form.passcode"
                                    :error-messages="errors.passcode ? errors.passcode : []"
                                    :rules="rules.passcode"
                                    :label="$gettext('PIN-kod')"
                                />
                            </v-col>
                        </v-row>
                    </v-card-text>
                </v-card>

                <OrganizationPicker
                    v-model="form.organization_unit"
                    :label="$gettext('Organisationsenhet')"
                    :error-messages="errors.organization_unit ? errors.organization_unit : []"
                />

                <UserPicker
                    :search.sync="form.owner_jid"
                    :error-messages="errors.owner_jid ? errors.owner_jid : []"
                    :rules="rules.owner_jid"
                    item-value="jid"
                    item-search="jid"
                    clearable
                    :label="$gettext('Ägare')"
                />
                <v-text-field
                    v-model="form.owner_email"
                    :error-messages="errors.owner_email ? errors.owner_email : []"
                    :rules="rules.owner_email"
                    clearable
                    :label="$gettext('Koppla till e-postadress')"
                    :hint="$gettext('Fylls automatiskt i från ägare')"
                    :counter="256"
                />
                <v-text-field
                    v-if="$store.state.site.enableGroups"
                    v-model="form.group"
                    :error-messages="errors.group ? errors.group : []"
                    :rules="rules.group"
                    clearable
                    :label="$gettext('Koppla till grupp')"
                    :counter="256"
                />
                <v-checkbox
                    v-model="form.force_encryption"
                    :error-messages="errors.force_encryption ? errors.force_encryption : []"
                    :rules="rules.force_encryption"
                    :label="$gettext('Kräv kryptering')"
                    :hint="$gettext('Ev. deltagare utan stöd kommer inte kunna ansluta')"
                />
                <v-checkbox
                    v-model="form.enable_chat"
                    :error-messages="errors.enable_chat ? errors.enable_chat : []"
                    :rules="rules.enable_chat"
                    :label="$gettext('Aktivera chat')"
                />
                <v-card>
                    <v-card-text class="py-1">
                        <v-checkbox
                            v-model="form.lobby"
                            :error-messages="errors.lobby ? errors.lobby : []"
                            :rules="rules.lobby"
                            :label="$gettext('Använd lobby för gästanvändare')"
                            :hint="$gettext('Mötet startar inte förrän en moderator/medlem loggat in')"
                        />

                        <v-text-field
                            v-if="form.lobby"
                            v-model="form.lobby_pin"
                            :error-messages="errors.lobby_pin ? errors.lobby_pin : []"
                            :rules="rules.lobby_pin"
                            :label="$gettext('Separat PIN-kod för moderator')"
                        />
                    </v-card-text>
                </v-card>
                <div class="my-4">
                    <VDatetimePicker
                        v-model="form.ts_auto_remove"
                        :label="$gettext('Radera efter tidpunkt')"
                    />
                </div>
                <ErrorMessage :error="error" />
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-btn
                    :loading="formLoading"
                    color="primary"
                    type="submit"
                >
                    {{ buttonText }}
                </v-btn>
                <v-spacer />
                <v-btn
                    v-close-dialog
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

import VDatetimePicker from '@/vue/components/datetime/DateTimePicker'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'
import UserPicker from '@/vue/components/user/UserPicker'

function getResetErrorWatchers(fields) {
    const result = {}
    Array.from(fields.pop ? fields : arguments).forEach(
        f =>
            (result['form.' + f] = function() {
                this.$set(this.errors, f, null)
            })
    )
    return result
}
function emptyForm(initialData = null) {
    return {
        organization_path: '',
        organization_unit: null,
        name: '',
        uri: '',
        call_id: null,
        enable_passcode: false,
        passcode: parseInt(Math.floor(1000 + Math.random() * 9000)),
        owner_jid: '',
        owner_email: '',
        group: '',
        enable_call_profile: false,
        call_id_generation_method: 'random',
        call_profile: '',
        enable_call_leg_profile: false,
        call_leg_profile: '',
        force_encryption: false,
        enable_chat: true,
        lobby: false,
        lobby_pin: parseInt(Math.floor(1000 + Math.random() * 9000)),
        ts_auto_remove: null,
        ts_auto_remove__date: null,
        ts_auto_remove__time: null,
        ...(initialData || {}),
    }
}
export default {
    components: { UserPicker, OrganizationPicker, ErrorMessage, VDatetimePicker },
    props: {
        id: { type: String, required: false, default: null },
        initialData: { type: Object, required: false, default() { return {} } },
        buttonText: { type: String, default: $gettext('Lägg till') },
    },
    data() {
        return {
            loading: false,
            error: '',
            formLoading: false,
            formValid: false,
            loadedData: {},
            generateCallId: true,
            form: emptyForm(this.initialData),
            rules: this.getRules(),
            choices: this.getChoices(),
            errors: {},
        }
    },
    computed: {},
    watch: {
        ...getResetErrorWatchers(...Object.keys(emptyForm())),
        'form.ts_auto_remove__date': function() { this.updateTsAutoRemove() },
        'form.ts_auto_remove__time': function() { this.updateTsAutoRemove() },
        id() {
            return this.init()
        }
    },
    created() {
        return this.init()
    },
    methods: {
        updateTsAutoRemove() {
            this.form.ts_auto_remove = [this.form.ts_auto_remove__date, this.form.ts_auto_remove__time].join(' ')
        },
        getRules() {
            const required = v => !!v || $gettext('Värdet måste fyllas i')
            const checkInt = v => (!v && v !== 0) || !isNaN(parseInt(v)) || $gettext('Värdet måste vara ett tal')
            return {
                name: [required],
                call_id: [checkInt],
                lobby_pin: [checkInt],
            }
        },
        getChoices() {
            return {}
        },
        serializeForm() {
            const data = {
                ...this.form,
            }
            if (!this.form.lobby) {
                delete data.lobby_pin
            }
            if (this.generateCallId) {
                delete data.call_id
            } else {
                delete data.call_id_generation_method
            }
            if (!this.form.enable_passcode) data.passcode = ''
            return data
        },
        submit() {
            if (!this.$refs.form.validate()) {
                this.error = $gettext('Kontrollera formuläret')
                return
            }
            this.formLoading = true
            this.error = null
            this.errors = {}

            const data = this.serializeForm()

            const action = !this.id
                ? this.$store.dispatch('cospace/create', data)
                : this.$store.dispatch('cospace/update', { id: this.id, ...data })
            return action
                .then(cospace => {
                    if (!this.id) {
                        this.form = emptyForm()
                    }
                    this.formLoading = false
                    this.errors = {}
                    this.$emit('created', cospace)
                })
                .catch(e => {
                    this.formLoading = false
                    if (e.errors) {
                        this.errors = e.errors
                        this.error = e.error || $gettext('Kontrollera formuläret')
                    } else {
                        this.error = e
                    }
                })
        },
        init() {
            this.loading = true
            return Promise.all([
                this.id
                    ? this.$store.dispatch('cospace/get', this.id)
                    : Promise.resolve(this.initialData || {}),
            ]).then(values => {
                this.loadedData = {...values[0] }
                this.form = { ...this.form, ...values[0] }
                this.generateCallId = !values[0].call_id
                this.form.lobby = !!values[0].lobby_pin
                if (this.id) {
                    this.form.passcode = values[0].passcode || values[0].password || ''
                }
                this.form.enable_passcode = !!this.form.passcode
                this.generateCallId = !this.id
                this.loading = false
            })
        },
    },
}
</script>
