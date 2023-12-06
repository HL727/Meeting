<template>
    <div>
        <PageSearchFilter :sticky="activeConfiguration.length > 0">
            <template v-slot:search>
                <v-text-field
                    v-model="text_filter"
                    hide-details
                    prepend-inner-icon="mdi-magnify"
                    :placeholder="$gettext('Sök configuration') + '...'"
                    outlined
                    dense
                />
            </template>
            <template v-slot:filter>
                <CommandQueue
                    :queue="activeConfigurationWithPath"
                    :label="$gettext('Valda konfigurationer')"
                />

                <template v-if="activeConfiguration.length">
                    <v-btn
                        dark
                        small
                        color="primary"
                        class="mr-4"
                        :to="{ name: 'endpoint_configuration_apply', params: { id: endpoint.id } }"
                    >
                        <v-icon left>
                            mdi-eye
                        </v-icon>
                        <translate>Granska</translate>
                    </v-btn>
                    <v-btn
                        dark
                        small
                        color="error"
                        @click="$store.commit('endpoint/clearActiveConfiguration')"
                    >
                        <v-icon left>
                            mdi-close
                        </v-icon>
                        <translate>Rensa</translate>
                    </v-btn>
                </template>
                <template v-else>
                    <v-btn
                        dark
                        small
                        outlined
                        color="primary"
                        class="mr-4"
                        :loading="loadingSelectAll"
                        @click="selectAll"
                    >
                        <v-icon left>
                            mdi-check
                        </v-icon>
                        <translate>Markera allt</translate>
                    </v-btn>

                    <v-btn
                        color="primary"
                        small
                        @click="templateDialog = true"
                    >
                        <v-icon left>
                            mdi-content-save-move
                        </v-icon>
                        <span><translate>Ladda mall</translate></span>
                    </v-btn>
                </template>
            </template>
        </PageSearchFilter>
        <v-divider />

        <TabLoaderIndicator v-if="loading" />

        <div v-show="!loading">
            <v-alert
                v-if="!loading && configurationData.age > 60"
                type="info"
                class="mb-3"
            >
                <translate>Tid sedan informationen uppdaterades:</translate> {{ configurationData.age|duration }}
            </v-alert>
            <EndpointConfigurationForm
                :id="id"
                ref="configurationForm"
                :filter="text_filter"
                @loaded="loaded"
            />
        </div>

        <EndpointTemplatePicker
            v-model="templateDialog"
            require-settings
            @cancel="templateDialog = false"
            @load="loadTemplate"
        />
    </div>
</template>

<script>
import {GlobalEventBus} from '@/vue/helpers/events'

import {
    filterInternalSettings,
    flattenConfigurationTree,
    populateSettingsData,
} from '@/vue/store/modules/endpoint/helpers'

import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'
import TabLoaderIndicator from '@/vue/views/epm/endpoint/single/TabLoaderIndicator'

import EndpointConfigurationForm from '@/vue/components/epm/endpoint/EndpointConfigurationForm'
import CommandQueue from '@/vue/components/epm/endpoint/CommandQueue'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import EndpointTemplatePicker from '@/vue/components/epm/EndpointTemplatePicker'

export default {
    components: {
        EndpointTemplatePicker,
        PageSearchFilter,
        TabLoaderIndicator,
        EndpointConfigurationForm,
        CommandQueue
    },
    mixins: [SingleEndpointMixin],
    data() {
        return {
            emitter: new GlobalEventBus(this),
            loading: true,
            templateDialog: false,
            text_filter: '',
            loadingSelectAll: false
        }
    },
    computed: {
        activeConfiguration() {
            return Object.values(this.$store.state.endpoint.activeConfiguration)
        },
        activeConfigurationWithPath() {
            return this.activeConfiguration.map(config => ({ ...config, displayPath: config.path.join(' > ') }) )
        },
        configurationData() {
            return this.$store.state.endpoint.configuration[this.id] || {}
        },
    },
    mounted() {
        this.emitter.on('refresh', () => {
            this.loading = true
            this.$refs['configurationForm'].loadData()
        })
    },
    methods: {
        selectAll() {
            this.loadingSelectAll = true
            return this.getConfiguration()
                .then(configuration => {
                    this.loadingSelectAll = false

                    const settings = filterInternalSettings(flattenConfigurationTree(configuration)).map(s => ({
                        ...s,
                        setting: s,
                    }))

                    this.$router.push({ name: 'endpoint_configuration_apply', params: { id: this.id } })
                    this.$nextTick(() => {
                        this.$store.commit('endpoint/setActiveConfiguration', settings)
                    })
                })
                .catch(e => {
                    this.loadingSelectAll = false
                    this.error = e
                })
        },
        loaded() {
            this.loading = false
            this.emitter.emit('loading', false)
        },
        loadTemplate(template) {
            return this.getConfiguration()
                .then(configuration => {
                    this.$store.commit(
                        'endpoint/setActiveConfiguration',
                        populateSettingsData(
                            (template.length ? template[0] : template).settings,
                            configuration
                        )
                    )
                })
                .catch(e => this.error = e)
                .then(() => this.templateDialog = false)
        },
        getConfiguration() {
            const existing = this.$store.state.endpoint.configuration[this.id]?.data
            return existing
                ? Promise.resolve(existing)
                : this.$store
                    .dispatch('endpoint/getConfiguration', this.id)
                    .then(() => this.$store.state.endpoint.configuration[this.id]?.data)
        },
    }
}
</script>
