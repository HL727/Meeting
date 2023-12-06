<template>
    <v-form
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
                <v-skeleton-loader
                    :loading="loading"
                    tile
                    transition="fade-transition"
                    type="image"
                >
                    <div>
                        <div style="position:relative">
                            <v-text-field
                                v-model="form.name"
                                :error-messages="errors.name ? errors.name : []"
                                :rules="rules.notEmpty"
                                :label="$gettext('Namn')"
                                @keyup="errors.name = null"
                            />
                            <v-text-field
                                v-model="form.description"
                                :error-messages="errors.description ? errors.description : []"
                                :label="$gettext('Beskrivning')"
                                @keyup="errors.description = null"
                            />
                            <v-select
                                v-model="form.service_type"
                                :label="$gettext('Typ av rum')"
                                :items="[
                                    { value: 'conference', text: $ngettext('Mötesrum', 'Mötesrum', 1) },
                                    { value: 'lecture', text: $gettext('Webinar') },
                                    { value: 'test_call', text: $gettext('Test service') },
                                ]"
                            />
                            <!-- TODO add lecture type fields -->
                            <template v-if="['test_call', 'two_stage_dialing'].indexOf(form.service_type) === -1">
                                <v-text-field
                                    v-model="form.pin"
                                    :error-messages="errors.pin ? errors.pin : []"
                                    :label="$gettext('Host pin')"
                                    @keyup="errors.pin = null"
                                />
                                <v-select
                                    v-model="form.host_view"
                                    :items="pexipHostLayoutChoices "
                                    item-text="title"
                                    item-value="id"
                                    :label="$gettext('Moderator-layout')"
                                />

                                <v-card class="mb-4">
                                    <v-card-text class="py-1">
                                        <v-row dense>
                                            <v-col sm="6">
                                                <v-checkbox
                                                    v-model="form.allow_guests"
                                                    :label="$gettext('Gästanslutning')"
                                                />
                                            </v-col>
                                            <v-col>
                                                <v-text-field
                                                    v-if="form.allow_guests"
                                                    v-model="form.guest_pin"
                                                    :error-messages="errors.guest_pin ? errors.guest_pin : []"
                                                    :label="$gettext('Gäst pin')"
                                                    @keyup="errors.guest_pin = null"
                                                />
                                            </v-col>
                                        </v-row>
                                        <v-select
                                            v-if="form.guest_pin"
                                            v-model="form.guest_view"
                                            :items="pexipGuestLayoutChoices"
                                            item-text="title"
                                            item-value="id"
                                            :label="$gettext('Gäst-layout')"
                                        />
                                    </v-card-text>
                                </v-card>
                                <v-text-field
                                    v-model="form.primary_owner_email_address"
                                    :error-messages="errors.primary_owner_email_address ? errors.primary_owner_email_address : []"
                                    :label="$gettext('E-postadress')"
                                    @keyup="errors.primary_owner_email_address = null"
                                />
                            </template>

                            <OrganizationPicker
                                v-model="form.organization_unit"
                                :label="$gettext('Organisationsenhet')"
                            />
                        </div>

                        <p class="overline">
                            <translate>Alias</translate>
                        </p>

                        <v-select
                            v-if="!id"
                            v-model="form.call_id_generation_method"
                            solo
                            :label="$gettext('Skapa automatiskt numeriskt alias')"
                            :items="[
                                {value: 'random', text: $gettext('Slumpa numeriskt ID')},
                                {value: 'increase', text: $gettext('Nästa numeriska ID i nummerföljd')},
                            ]"
                            clearable
                        />

                        <v-card>
                            <v-card-text class="py-1">
                                <div
                                    v-for="(alias, i) in form.aliases"
                                    :key="alias._id"
                                >
                                    <v-divider v-if="i > 0" />
                                    <v-row>
                                        <v-col cols="1">
                                            <v-checkbox
                                                v-model="alias.active"
                                                :disabled="!alias.alias"
                                            />
                                        </v-col>
                                        <v-col>
                                            <v-text-field
                                                v-model="alias.alias"
                                                :error-messages="alias.error ? alias.error : []"
                                                :label="$gettext('Alias')"
                                                @keyup="updateAlias(alias)"
                                            />
                                        </v-col>
                                        <v-col>
                                            <v-text-field
                                                v-model="alias.description"
                                                :label="$gettext('Beskrivning')"
                                            />
                                        </v-col>
                                    </v-row>
                                </div>
                            </v-card-text>
                        </v-card>

                        <v-alert
                            v-if="error"
                            type="error"
                            class="mt-4"
                        >
                            {{ error }}
                        </v-alert>
                    </div>
                </v-skeleton-loader>
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-skeleton-loader
                    :loading="loading"
                    transition="fade-transition"
                    type="button"
                >
                    <v-btn
                        color="primary"
                        dark
                        type="submit"
                        :loading="formLoading"
                    >
                        {{ id ? $gettext('Uppdatera') : $gettext('Lägg till') }}
                    </v-btn>
                </v-skeleton-loader>
                <v-spacer />
                <v-btn
                    color="red"
                    text
                    @click="cancel"
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

import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'
import { pexipGuestLayoutChoices, pexipHostLayoutChoices } from '@/vue/store/modules/cospace/consts'

let aliasInternalId = 0

const emptyData = () => ({
    id: 0,
    service_type: 'conference',
    name: '',
    call_id_generation_method: 'random',
    description: '',
    pin: '',
    allow_guests: false,
    guest_pin: '',
    primary_owner_email_address: '',
    aliases: [],
    organization_unit: null,
    guest_view: 'one_main_seven_pips',
    host_view: 'five_mains_seven_pips',
})

export default {
    components: {
        OrganizationPicker,
    },
    props: {
        id: { type: Number, default: null, required: false },
    },
    data() {
        return {
            loading: true,
            formValid: false,
            formLoading: false,
            errors: {},
            error: '',
            rules: {
                notEmpty: [v => v ? true : 'Värdet måste fyllas i'],
            },
            form: emptyData(),
            pexipGuestLayoutChoices,
            pexipHostLayoutChoices,
        }
    },
    watch: {
        'form.aliases': {
            handler() {
                this.checkAliases()
            },
            deep: true,
        },
        id() {
            this.init()
        },
    },
    mounted() {
        this.init()
    },
    methods: {
        checkAliases() {
            const { aliases } = this.form

            if (!aliases.length || aliases[aliases.length - 1].alias) {
                this.addAlias()
            }
        },
        updateAlias(alias) {
            alias.error = null
            if (alias.alias) alias.active = true
        },
        addAlias() {
            aliasInternalId++
            this.form.aliases.push({
                _id: aliasInternalId,
                active: false,
                id: 0,
                alias: '',
                description: ''
            })
        },
        moveRemovedAliasesLast() {
            this.form.aliases = this.form.aliases.sort((a, b) => {
                return parseInt(!(a.alias && a.active)) - parseInt(!(b.alias && b.active))
            })
        },
        serializeData() {
            const result = {
                ...this.form,
                aliases: this.form.aliases.filter(a => a.alias && a.active),
                organization_unit: this.form.organization_unit || null,
            }
            if (!this.id) delete result.call_id_generation_method
            return result
        },
        init() {
            if (this.id) {
                this.load()
            } else {
                this.addAlias()
                this.loading = false
            }
        },
        submit() {
            this.error = null
            this.errors = {}

            if (!this.$refs.form.validate()) {
                this.error = $gettext('Kontrollera formuläret')
                return
            }
            this.formLoading = true
            this.moveRemovedAliasesLast()
            const data = this.serializeData()

            const action = this.id
                ? this.$store.dispatch('cospace/pexip/update', data)
                : this.$store.dispatch('cospace/pexip/create', data)

            return action
                .then(response => {
                    this.formLoading = false
                    this.form.id = response.id
                    this.form = emptyData()
                    this.addAlias()
                    this.$emit('created')
                })
                .catch(e => {
                    this.formLoading = false
                    this.handleErrors(e)

                })
        },
        handleErrors(response) {
            if (response.errors) {
                this.errors = response.errors
            }
            if (response.error) {
                if (response.error.aliases) {
                    this.form.aliases = this.form.aliases.map((a, index) => {
                        if (response.error.aliases[index] && response.error.aliases[index].error) {
                            return { ...a, error: response.error.aliases[index].error }
                        }
                        return { ...a, id: response.error.aliases[index].id }
                    })

                    this.error = response.error.aliases
                }
                else {
                    this.error = response.error
                }
            }
        },
        load() {
            this.loading = true
            return this.$store.dispatch('cospace/pexip/get', this.id).then((cospace) => {
                const newForm = emptyData()
                for (let k in cospace) {
                    if (k in newForm) newForm[k] = cospace[k]
                }
                this.form = newForm

                this.form.aliases = this.form.aliases.map((a) => {
                    aliasInternalId++
                    return { _id: aliasInternalId, active: true, ...a }
                })
                this.loading = false
            }).catch(e => {
                this.error = e.toString()
                this.loading = false
            })
        },
        cancel() {
            this.form = emptyData()
            this.$emit('cancel')
        }
    }
}
</script>
