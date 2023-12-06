<template>
    <div>
        <div v-if="loading">
            <v-progress-circular indeterminate />
        </div>
        <v-form
            v-if="!loading"
            ref="form"
            v-model="formValid"
            @submit.prevent="submit"
        >
            <v-datetime-picker
                v-if="!tsStart && !tsStop"
                v-model="form.ts_start"
                :error-messages="errors.ts_start ? errors.ts_start : []"
                :label="$gettext('Starttid') + ' (*)'"
            />
            <v-datetime-picker
                v-if="!tsStart && !tsStop"
                v-model="form.ts_stop"
                :error-messages="errors.ts_stop ? errors.ts_stop : []"
                :label="$gettext('Sluttid') + ' (*)'"
            />
            <TenantPicker
                v-if="enableTenants"
                v-model="form.customer"
                item-value="id"
                clearable
                :label="$gettext('Tenant')"
            />

            <div v-if="!initialData || !initialData.endpoints">
                <EndpointPicker
                    v-model="form.endpoints"
                    :error-messages="errors.endpoints ? errors.endpoints : []"
                    :rules="rules.endpoints"
                    :label="$gettext('Endpoint')"
                    only-head-count
                />
                <OrganizationPicker
                    v-if="$store.state.site.enableOrganization"
                    v-model="form.organization"
                    :label="$gettext('Organisationsenhet')"
                    :input-attrs="{
                        disabled: form.endpoints.length > 0,
                        hint: form.endpoints.length > 0 ? $gettext('Organisationsenhet går inte att kombinera med valda system.') : '',
                        persistentHint: form.endpoints.length > 0
                    }"
                    hide-add-new
                    clearable
                />
            </div>

            <v-text-field
                v-model="form.only_hours"
                :label="$gettext('Inkludera tider')"
            />
            <v-text-field
                v-model="form.only_days"
                :label="$gettext('Inkludera veckodagar')"
            />
            <v-checkbox
                v-model="form.as_percent"
                :label="$gettext('Visa som procent av rumskapacitet')"
            />
            <v-checkbox
                v-model="form.ignore_empty"
                :label="$gettext('Hoppa över tomma rum')"
            />
            <v-checkbox
                v-if="!form.ignore_empty"
                v-model="form.fill_gaps"
                :label="$gettext('Fyll i saknad data med 0-värden')"
            />

            <template v-if="!hideActions">
                <v-btn
                    :disabled="!formValid"
                    :loading="loading"
                    color="primary"
                    type="submit"
                >
                    {{ buttonText }}
                </v-btn>
                <v-btn @click="reset()">
                    <translate>Rensa</translate>
                </v-btn>
            </template>

            <ErrorMessage :error="error" />
        </v-form>
    </div>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'
function resetErrors(...fields) {
    const result = {}
    fields.forEach(
        f =>
            (result['form.' + f] = function() {
                this.$set(this.errors, f, null)
            })
    )
    return result
}
import VDatetimePicker from '@/vue/components/datetime/DateTimePicker'
import { setQuery } from '@/vue/helpers/url'
import { format } from 'date-fns'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import EndpointPicker from '@/vue/components/epm/endpoint/EndpointPicker'
import TenantPicker from '@/vue/components/tenant/TenantPicker'

const initialData = () => ({
    ts_start: new Date(new Date() - 30 * 60 * 60 * 24 * 1000),
    ts_stop: new Date(),
    ou: '',
    customer: null,
    member: '',
    organization: null,
    debug: '',
    endpoints: [],
})

/** update all keys with non-empty values */
function updateMergedValues(result, ...objects) {
    objects.forEach(params => {
        Object.entries(params || {}).forEach(([key, value]) => {
            if (value === null || value === undefined) return
            if (value === '' && typeof result[key] != 'string') return  // '' are only ok for string values

            if (key in result) result[key] = value
        })
    })
    return result
}

function parseFormValues(...args) {
    const result = updateMergedValues(initialData(), ...args)

    result.customer = (result.customer !== null) ? parseInt(result.customer || 0, 10) : null
    result.organization = result.organization ? parseInt(result.organization, 10) : null
    return result
}

export default {
    components: { TenantPicker, EndpointPicker, ErrorMessage, OrganizationPicker, VDatetimePicker },
    props: {
        initialData: { type: Object, required: false, default() { return {} } },
        buttonText: { type: String, default: $gettext('Filtrera') },
        tsStart: { type: [String, Date], required: false, default: null },
        tsStop: { type: [String, Date], required: false, default: null },
        value: { type: Object, required: false, default: null },
        autoload: { type: Boolean },
        disableQueryChange: { type: Boolean },
        enableTenants: Boolean,
        extraData: { type: Object, default() { return {} } },
        hideActions: { type: Boolean, default: false }
    },
    data() {
        return {
            loading: true,
            error: '',
            formLoading: false,
            formValid: false,
            form: parseFormValues(
                {
                    ts_start: this.tsStart,
                    ts_stop: this.tsStop,
                },
                this.initialData,
                this.value,
                this.$route && this.$route.query
            ),
            rules: {
                ts_start: [v => !!v || $gettext('Värdet måste fyllas i')],
                ts_stop: [v => !!v || $gettext('Värdet måste fyllas i')],
            },
            errors: {},
            lastUrl: '',
            statsData: {},
        }
    },
    computed: {
        endpoints() {
            return Object.values(this.$store.state.endpoint.endpoints)
        },
    },
    watch: {
        ...resetErrors(
            'ts_start',
            'ts_stop',
            'ou',
            'customer',
            'cospace',
            'member',
            'organization',
            'debug'
        ),
        tsStart(newValue) {
            if (newValue) this.form.ts_start = newValue
        },
        tsStop(newValue) {
            if (newValue) this.form.ts_stop = newValue
        },
        form: {
            handler(newValue) {
                this.$emit('input', newValue)
            },
            deep: true,
        },
        'form.endpoints'(newValue) {
            if (newValue && newValue.length) {
                this.form.organization = null
            }
        },
        value: {
            handler(newValue) {
                if (Object.keys(newValue).length) {
                    Object.assign(this.form, newValue)
                }
            },
            deep: true,
        },
        loading() {
            this.$emit('loading', this.loading || this.formLoading)
        },
        formLoading() {
            this.$emit('loading', this.loading || this.formLoading)
        },
        '$route.fullPath'() {
            this.reloadIfPathChange()
        },
    },
    created() {
        this.$emit('input', this.form)

        const params = {}
        if (this.enableTenants) {
            params.multitenant = true
        }

        if (this.$route.query.load || this.autoload) {
            return this.getStats(false)
                .then(() => (this.loading = false))
                .catch(() => (this.loading = false))
        }
        else {
            this.loading = false
        }
    },
    methods: {
        serializeForm() {
            const dateString = d => (d && d.getYear ? format(d, 'yyyy-MM-dd HH:mm') : d || '')

            const params = {
                ...this.form,
                ...this.extraData,
                customer: this.form.customer || undefined,
                ts_start: dateString(this.form.ts_start),
                ts_stop: dateString(this.form.ts_stop),
            }
            if (!params.endpoints || !params.endpoints.length) delete params.endpoints

            if (this.enableTenants) {
                params.multitenant = true
            }

            return params
        },
        getStats(changeUrl = true) {
            this.error = ''
            this.formLoading = true
            const params = this.serializeForm()

            if (changeUrl && !this.disableQueryChange) {
                const newUrl = setQuery(this.$route.fullPath, { ...params, url: undefined }, true)
                this.lastUrl = newUrl
                if (setQuery(this.$route.fullPath, null, true) !== this.lastUrl) this.$router.push(newUrl)
            }

            return this.getHeadCountStats(params).then(data => {
                this.formLoading = false
                this.updateStatsData(data)
                return data
            })
        },
        updateStatsData(newData) {
            this.statsData = Object.freeze({
                ...this.statsData,
                errors: null,
                ...newData,
            })
            if (this.statsData.loaded) {
                this.$emit('statsLoaded', this.statsData)
            }
        },
        getHeadCountStats(params) {
            return this.$store
                .dispatch('stats/getHeadCountStats', params)
                .then(f => {
                    this.updateStatsData(f)
                })
                .catch(e => {
                    this.error = e
                    this.$emit('error', e)
                })
        },
        reloadIfPathChange() {
            if (this.lastUrl == setQuery(this.$route.fullPath, null, true)) return // same path

            this.lastUrl = this.$route.fullPath

            if (this.lastUrl == setQuery(this.$route.fullPath, {}, true)) {
                // root
                this.form = { ...this.initialData }
                return
            }

            this.form = parseFormValues(this.form, this.$route.query)
            this.submit()
        },
        submit() {
            if (this.$refs.form && !this.$refs.form.validate()) return
            return this.getStats()
        },
        reset() {
            this.form = parseFormValues()
        },
    },
}
</script>
