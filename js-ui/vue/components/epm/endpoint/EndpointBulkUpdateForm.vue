<template>
    <v-form
        ref="form"
        v-model="formValid"
        @submit.prevent="delaySubmit"
    >
        <v-card>
            <v-card-title><translate>Uppdatera system</translate></v-card-title>
            <v-divider />
            <v-card-text>
                <v-skeleton-loader
                    v-if="loading"
                    type="image"
                    tile
                />
                <div v-else>
                    <v-list two-line>
                        <v-list-item>
                            <v-list-item-content>
                                <v-checkbox
                                    v-model="form.setPassword"
                                    :label="$gettext('Lösenord')"
                                />
                            </v-list-item-content>
                            <v-list-item-content class="pt-0">
                                <v-checkbox
                                    v-model="form.passwordAuto"
                                    :disabled="!form.setPassword"
                                    :label="$gettext('Använd standardlösenord')"
                                />

                                <v-text-field
                                    v-model="form.password"
                                    :disabled="!form.setPassword || form.passwordAuto"
                                    :rules="form.setPassword && !form.passwordAuto ? rules.notEmpty : []"
                                    type="password"
                                    :label="$gettext('Ange eget lösenord')"
                                />
                            </v-list-item-content>
                        </v-list-item>
                        <v-divider />
                    </v-list>

                    <v-list two-line>
                        <v-list-item>
                            <v-list-item-content>
                                <v-checkbox
                                    v-model="form.setSeats"
                                    :label="$gettext('Antal platser i rum')"
                                />
                            </v-list-item-content>
                            <v-list-item-content>
                                <v-text-field
                                    v-model="form.seats"
                                    :disabled="!form.setSeats"
                                    :rules="form.setSeats ? rules.number : []"
                                    :label="$gettext('Antal')"
                                    width="40"
                                />
                            </v-list-item-content>
                        </v-list-item>
                        <v-divider />
                    </v-list>

                    <v-list two-line>
                        <v-list-item>
                            <v-list-item-content>
                                <v-checkbox
                                    v-model="form.setLocation"
                                    :label="$gettext('Plats')"
                                />
                            </v-list-item-content>
                            <v-list-item-content>
                                <v-combobox
                                    v-model="form.location"
                                    :disabled="!form.setLocation"
                                    :label="$gettext('Plats')"
                                    :items="locations"
                                    :rules="form.setLocation ? rules.notEmpty : []"
                                />
                            </v-list-item-content>
                        </v-list-item>
                        <v-divider />
                    </v-list>

                    <v-list two-line>
                        <v-list-item>
                            <v-list-item-content>
                                <v-checkbox
                                    v-model="form.setOrgUnit"
                                    :label="$gettext('Organisationsenhet')"
                                />
                            </v-list-item-content>
                            <v-list-item-content>
                                <OrganizationPicker v-model="form.orgUnit" />
                            </v-list-item-content>
                        </v-list-item>
                        <v-divider />
                    </v-list>
                </div>
            </v-card-text>
            <v-alert
                v-if="error"
                type="error"
                class="ma-0"
                tile
            >
                {{ error }}
            </v-alert>
            <v-divider />
            <v-card-actions>
                <v-btn
                    :disabled="formEmpty || loading"
                    type="submit"
                    color="primary"
                    :loading="formLoading"
                >
                    <translate>Uppdatera</translate>
                </v-btn>
                <v-spacer />
                <v-btn
                    v-close-dialog
                    text
                    color="red darken-1"
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
import { closeDialog } from '@/vue/helpers/dialog'

export default {
    components: { OrganizationPicker },
    props: {
        endpoints: { type: Array, default: () => [] },
    },
    data() {
        return {
            form: {
                setPassword: false,
                passwordAuto: true,
                password: '',
                setSeats: false,
                seats: null,
                setLocation: '',
                location: '',
                setOrgUnit: false,
                orgUnit: null,
            },
            rules: {
                number: [v => (!isNaN(parseInt(v)) && v !== '') || $gettext('Värdet måste vara ett tal')],
                notEmpty: [v => !!v || $gettext('Värdet måste fyllas i')],
            },
            locations: [],
            formValid: false,
            formLoading: false,
            errors: {},
            error: '',
            loading: true
        }
    },
    computed: {
        formEmpty() {
            if (!this.form.setPassword &&
                !this.form.setSeats &&
                !this.form.setLocation &&
                !this.form.setOrgUnit) {
                return true
            }

            return false
        },
        formData() {
            const result = {
                endpoints: this.endpoints,
            }

            if (this.form.setPassword) {
                const password = this.form.passwordAuto ? '__try__' : this.form.password
                if (password) {
                    result.password = password
                }
            }
            if (this.form.setSeats && this.form.seats !== '') {
                result.room_capacity = this.form.seats
            }
            if (this.form.setLocation) {
                result.location = this.form.location || ''
            }
            if (this.form.setOrgUnit) {
                result.org_unit = this.form.orgUnit || ''
            }
            return result
        }
    },
    mounted() {
        return this.$store.dispatch('endpoint/getFilters').then(filters => {
            this.locations = [...filters.location]
            this.loading = false
        })
    },
    methods: {
        delaySubmit() {
            return new Promise(resolve => setTimeout(() => resolve(this.submit()), 100))
        },
        submit() {
            if (!this.$refs.form.validate()) return

            this.formLoading = true
            this.error = ''
            this.errors = {}

            return this.$store.dispatch('endpoint/updateBulk', this.formData)
                .then(() => {
                    this.formLoading = false
                    this.$emit('update', this.endpoints)
                    closeDialog(this.$vnode)
                })
                .catch(e => {
                    this.formLoading = false
                    if (e.error) {
                        this.error = e.error
                    }
                    if (e.errors) {
                        this.errors = e.errors
                    } else {
                        this.error = e
                    }
                })
        }
    },
}
</script>
