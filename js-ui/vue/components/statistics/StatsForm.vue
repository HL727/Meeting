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
            <v-select
                v-if="enableTenants && tenantChoices.length"
                v-model="form.tenant"
                :error-messages="errors.tenant ? errors.tenant : []"
                :rules="rules.tenant"
                :items="tenantChoices"
                item-text="1"
                item-value="0"
                clearable
                :label="$gettext('Tenant')"
            />
            <template v-if="!onlyEpm">
                <v-text-field
                    v-if="$store.state.site.enableGroups"
                    v-model="form.ou"
                    :error-messages="errors.ou ? errors.ou : []"
                    :rules="rules.ou"
                    clearable
                    :label="$gettext('Grupp')"
                />

                <v-text-field
                    v-model="form.cospace"
                    :error-messages="errors.cospace ? errors.cospace : []"
                    :rules="rules.cospace"
                    clearable
                    :label="$ngettext('Mötesrum', 'Mötesrum', 1)"
                />
            </template>

            <div v-if="!initialData || !initialData.endpoints">
                <SipAddressPicker
                    v-if="!onlyEpm"
                    v-model="form.member"
                    :error-messages="errors.member ? errors.member : []"
                    :rules="rules.member"
                    :label="$gettext('Deltagare')"
                />
                <EndpointPicker
                    v-if="onlyEpm"
                    v-model="form.endpoints"
                    :error-messages="errors.endpoints ? errors.endpoints : []"
                    :rules="rules.endpoints"
                    :label="$gettext('Endpoint')"
                />

                <OrganizationPicker
                    v-if="$store.state.site.enableOrganization || onlyEpm"
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

                <v-checkbox
                    v-if="allowDebug && forceDebug === null"
                    v-model="form.debug"
                    :error-messages="errors.debug ? errors.debug : []"
                    value="1"
                    :rules="rules.debug"
                    :label="$gettext('Debug-info')"
                />
            </div>

            <slot name="fields" />

            <template v-if="!hideActions">
                <v-btn
                    :disabled="!formValid"
                    :loading="formLoading"
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
import { setQuery } from '@/vue/helpers/url'
import { idMap } from '@/vue/helpers/store'
import { format } from 'date-fns'

import VDatetimePicker from '@/vue/components/datetime/DateTimePicker'
import SipAddressPicker from '@/vue/components/epm/endpoint/SipAddressPicker'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import EndpointPicker from '@/vue/components/epm/endpoint/EndpointPicker'
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

const initialData = () => ({
    ts_start: new Date(new Date() - 30 * 60 * 60 * 24 * 1000),
    ts_stop: new Date(),
    ou: '',
    tenant: '',
    cospace: '',
    member: '',
    server: '',
    organization: null,
    debug: false,
    endpoints: [],
    protocol: null,
    only_gateway: false,
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

    result.server = parseInt(result.server || 0, 10)
    result.protocol = (result.protocol !== null) ? parseInt(result.protocol || 0, 10) : null
    result.organization = result.organization ? parseInt(result.organization, 10) : null
    result.debug = result.debug === true || result.debug === '1' || result.debug === 'true'
    result.only_gateway = result.only_gateway === true || result.only_gateway === '1' || result.only_gateway === 'true'

    return result
}

export default {
    components: { EndpointPicker, ErrorMessage, SipAddressPicker, OrganizationPicker, VDatetimePicker },
    props: {
        initialData: { type: Object, required: false, default() { return {} } },
        buttonText: { type: String, default: $gettext('Filtrera') },
        tsStart: { type: [String, Date], required: false, default: null },
        tsStop: { type: [String, Date], required: false, default: null },
        value: { type: Object, required: false, default: null },
        onlyEpm: Boolean,
        enableTenants: Boolean,
        extraData: { type: Object, default() { return {} } },
        hideActions: { type: Boolean, default: false },
        disableQueryChange: { type: Boolean },
        autoload: { type: Boolean },
        forceDebug: { type: Boolean, default: null },
    },
    data() {
        return {
            loading: false,
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
                server: [v => !!v || $gettext('Värdet måste fyllas i')],
            },
            choices: {
                server: [],
                tenant: [],
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
        serverMap() {
            return idMap(this.choices.server)
        },
        tenantChoices() {
            const server = this.serverMap[this.form.server] || {}
            return server.tenants || []
        },
        allowDebug() {
            if (this.$store.state.site.perms.staff) return true

            if (this.onlyEpm) {
                return !!this.$store.state.endpoint.settings.enable_user_debug_statistics
            }
            return false
        }
    },
    watch: {
        ...resetErrors(
            'ts_start',
            'ts_stop',
            'ou',
            'tenant',
            'cospace',
            'member',
            'server',
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
        forceDebug(newValue) {
            if (newValue !== null) this.form.debug = newValue
        },
    },
    created() {
        this.loading = true

        this.$emit('input', this.form)
        return this.loadInitialData()
    },
    methods: {
        loadInitialData() {
            const params = {}
            if (this.enableTenants) {
                params.multitenant = true
            }
            const settings = this.$store
                .dispatch(this.onlyEpm ? 'stats/getEPMStatsSettings' : 'stats/getStatsSettings', params)
                .then(d => {
                    this.choices = { ...this.choices, ...d.choices }
                    this.$emit('choices', this.choices)

                    this.initDefaultChoiceValues()
                    this.$emit('input', this.form)
                })
                .then(() => {
                    const { ts_start, ts_stop, server } = this.$route.query
                    if ((ts_start && ts_stop && server) || this.autoload) {
                        // eslint-disable-next-line promise/no-nesting
                        return this.getStats(false)
                            .then(() => (this.loading = false))
                            .catch(() => (this.loading = false))
                    } else {
                        this.loading = false
                    }
                })
            if (this.onlyEpm) return Promise.all([this.$store.dispatch('endpoint/getSettings'), settings])
            return settings
        },
        serializeForm() {
            const dateString = d => (d && d.getYear ? format(d, 'yyyy-MM-dd HH:mm') : d || '')

            const params = {
                ...this.form,
                ...this.extraData,
                ts_start: dateString(this.form.ts_start),
                ts_stop: dateString(this.form.ts_stop),
                server: this.form.server ? this.form.server : '',
            }
            if (!params.endpoints || !params.endpoints.length) delete params.endpoints

            if (this.onlyEpm) {
                delete params.member
            } else {
                delete params.endpoints
            }
            if (this.enableTenants) {
                params.multitenant = true
            }

            return params
        },
        getDebugStats() {
            const params = this.serializeForm()
            if (this.onlyEpm) params.url = 'room_statistics/debug/'

            return this.$store
                .dispatch('stats/getStatsDebug', params)
                .then(f => {
                    this.updateStatsData(f)
                })
                .catch(e => {
                    this.error = e
                    this.$emit('error', e)
                })
        },
        convertKeysToDeprecatedIndex(statsData) {
            for (const k in statsData.summary || {}) {
                if (!k.match(/_total$/)) continue
                const cur = statsData.summary[k]
                cur[0] = cur.duration
                cur[1] = cur.guest_duration
                cur[2] = cur.participant_count
                cur[3] = cur.call_count
                cur[4] = cur.related_id
            }
            return statsData
        },
        getStats(changeUrl = true) {

            this.error = ''
            this.formLoading = true
            const params = this.serializeForm()
            if (this.onlyEpm) params.url = 'room_statistics/'

            if (changeUrl && !this.disableQueryChange) {
                const newUrl = setQuery(this.$route.fullPath, { ...params, url: undefined }, true)
                this.lastUrl = newUrl
                if (setQuery(this.$route.fullPath, null, true) !== this.lastUrl) this.$router.push(newUrl)
            }

            this.$emit('statsLoading:start', params)

            const promise = params.debug ? this.getDebugStats() : this.getCallStats(params)

            return promise.then(response => {
                this.formLoading = false
                this.$emit('statsLoading:done', params, response)
                return response
            }).catch(e => {
                this.formLoading = false
                throw e
            })
        },
        updateStatsData(newData) {
            this.statsData = Object.freeze({
                ...this.statsData,
                errors: null,
                debug: this.form.debug,
                ...newData,
            })
            if (this.statsData.loaded) {
                this.$emit('statsLoaded', this.statsData)
            }
        },
        getCallStats(params) {

            return this.$store
                .dispatch('stats/getStats', params)
                .then(f => {
                    this.errors = f.errors ? { ...f.errors } : {}
                    this.error = null
                    this.updateStatsData(this.convertKeysToDeprecatedIndex(f))
                    return f
                })
                .catch(e => {
                    this.$emit('error', e)
                    if (e.errors) {
                        this.errors = e.errors
                    } else {
                        this.error = e
                    }
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
            this.initDefaultChoiceValues()
        },
        initDefaultChoiceValues() {
            if (!this.form.tenant && this.choices.tenant.length) this.form.tenant = this.choices.tenant[0][0]
            if (!this.form.server && this.choices.server.length) this.form.server = this.choices.server[0].id
        }
    },
}
</script>
