<template>
    <div>
        <PageSearchFilter>
            <template v-slot:search>
                <div>
                    <v-btn
                        color="primary"
                        outlined
                        exact
                        :to="{ name: 'endpoint_configuration', params: { id: endpoint.id } }"
                    >
                        <v-icon left>
                            mdi-arrow-left
                        </v-icon>
                        <translate>Tillbaka</translate>
                    </v-btn>
                </div>
            </template>
            <template v-slot:filter>
                <v-btn
                    small
                    color="primary"
                    :disabled="!activeConfiguration.length"
                    :loading="resultLoading"
                    @click="apply"
                >
                    <v-icon left>
                        mdi-check
                    </v-icon>
                    <translate>Applicera</translate>
                </v-btn>
                <v-btn
                    color="primary"
                    small
                    class="ml-4"
                    :disabled="!activeConfiguration.length"
                    @click.prevent="templateDialog = true"
                >
                    <v-icon left>
                        mdi-content-save
                    </v-icon>
                    <translate>Spara mall</translate>
                </v-btn>
                <v-btn
                    v-if="activeConfiguration.length"
                    dark
                    small
                    class="ml-4"
                    color="error"
                    @click="clearActiveConfiguration"
                >
                    <v-icon left>
                        mdi-close
                    </v-icon>
                    <translate>Rensa</translate>
                </v-btn>
            </template>
        </PageSearchFilter>
        <v-divider />

        <v-progress-linear
            :active="loading"
            indeterminate
            absolute
            top
        />

        <div v-if="!loading">
            <v-tabs
                :vertical="$vuetify.breakpoint.mdAndUp"
                background-color="grey lighten-4"
            >
                <v-tab
                    key="settings"
                    class="text-left justify-start"
                >
                    <translate>Granska</translate>
                </v-tab>
                <v-tab
                    key="endpoints"
                    class="text-left justify-start"
                >
                    <translate>Välj system</translate>
                </v-tab>
                <v-tab-item key="settings">
                    <v-dialog
                        :value="!!editSetting"
                        max-width="420"
                        scrollable
                        @input="editSetting = null"
                    >
                        <v-card>
                            <v-card-title><translate>Redigera</translate></v-card-title>
                            <v-divider />
                            <v-card-text>
                                <ConfigurationWrapper
                                    v-if="editSetting"
                                    :setting="editSetting.setting || editSetting"
                                />
                            </v-card-text>
                            <v-divider />
                            <v-card-actions>
                                <v-spacer />
                                <v-btn
                                    v-close-dialog
                                    text
                                    color="red"
                                >
                                    <translate>Stäng</translate>
                                    <v-icon
                                        right
                                        dark
                                    >
                                        mdi-close
                                    </v-icon>
                                </v-btn>
                            </v-card-actions>
                        </v-card>
                    </v-dialog>

                    <v-simple-table>
                        <thead>
                            <tr>
                                <th v-translate>
                                    Inställning
                                </th>
                                <th v-translate>
                                    Värde
                                </th>
                                <th />
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="config in activeConfiguration"
                                :key="config.key"
                            >
                                <td>
                                    {{ config.path.join(' > ') }}
                                </td>
                                <td>
                                    <small>
                                        {{ config.value }}
                                    </small>
                                </td>
                                <td width="1">
                                    <div class="d-flex justify-end">
                                        <v-btn
                                            icon
                                            @click="editSetting = config"
                                        >
                                            <v-icon>mdi-pencil</v-icon>
                                        </v-btn>
                                        <v-btn
                                            icon
                                            @click="removeSetting(config)"
                                        >
                                            <v-icon>mdi-delete</v-icon>
                                        </v-btn>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                </v-tab-item>

                <v-tab-item
                    key="endpoints"
                    class="pl-6"
                >
                    <EndpointGrid
                        v-model="checked"
                        :endpoints="endpoints"
                        checkbox
                    />
                </v-tab-item>
            </v-tabs>
        </div>

        <EndpointProvisionResult
            ref="provisionDialog"
            v-model="resultDialog"
            :endpoints="endpointIds"
            @update:loading="resultLoading = $event"
            @update:error="error = $event"
        />

        <SaveTemplateDialog
            v-model="templateDialog"
            :configuration="activeConfiguration"
            :endpoint="endpoint"
        />
    </div>
</template>

<script>
import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import EndpointGrid from '@/vue/components/epm/endpoint/EndpointGrid'
import ConfigurationWrapper from '@/vue/components/epm/endpoint/ConfigurationWrapper'
import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'
import SaveTemplateDialog from '@/vue/components/epm/endpoint/SaveTemplateDialog'
import EndpointProvisionResult from '@/vue/views/epm/endpoint/single/EndpointProvisionResult'

export default {
    name: 'EndpointConfigurationApply',
    components: {
        EndpointProvisionResult,
        SaveTemplateDialog,
        ConfigurationWrapper,
        EndpointGrid,
        PageSearchFilter,
    },
    mixins: [SingleEndpointMixin],
    data() {
        return {
            loading: false,
            editSetting: null,

            templateDialog: false,
            checked: [parseInt(this.id)],

            resultDialog: null,
            errors: null,
            resultLoading: false,
        }
    },
    computed: {
        configuration() {
            return this.$store.state.endpoint.configuration[this.id]?.data || []
        },
        activeConfiguration() {
            return Object.values(this.$store.state.endpoint.activeConfiguration)
        },
        rootElements() {
            return Object.values(this.$store.state.endpoint.activeConfiguration).map(
                config => config.setting.path[0]
            )
        },
        endpointIds() {
            if (this.checked.length >= 1) {
                return this.checked
            }
            return [this.id]
        }
    },
    methods: {
        settingObjects(nodes) {
            return nodes.map(node => {
                const [title, options, children, setting] = node
                return { title, options, children, setting, orig: node }
            })
        },
        removeSetting(setting) {
            this.$store
                .commit('endpoint/removeActiveConfiguration', setting)
        },
        clearActiveConfiguration() {
            this.$store.commit('endpoint/clearActiveConfiguration')
            this.$router.push({ name: 'endpoint_configuration', params: { id: this.endpoint.id } })
        },
        apply() {
            const settings = this.activeConfiguration.map(config => ({
                key: config.path,
                value: config.value,
            }))
            this.$refs.provisionDialog.apply({configuration: settings})
        },
    }
}
</script>
