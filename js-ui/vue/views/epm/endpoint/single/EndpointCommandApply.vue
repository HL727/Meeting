<template>
    <div>
        <PageSearchFilter>
            <template v-slot:search>
                <div>
                    <v-btn
                        color="primary"
                        outlined
                        exact
                        :to="{ name: 'endpoint_commands', params: { id: endpoint.id } }"
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
                    :disabled="!commandQueue.length"
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
                    :disabled="!commandQueue.length"
                    @click.prevent="templateDialog = true"
                >
                    <v-icon left>
                        mdi-content-save
                    </v-icon>
                    <translate>Spara mall</translate>
                </v-btn>

                <v-btn
                    v-if="commandQueue.length"
                    dark
                    small
                    color="error"
                    class="ml-4"
                    @click="$store.commit('endpoint/clearCommandQueue')"
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
                    key="command"
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
                <v-tab-item key="command">
                    <v-dialog
                        :value="editCommandIndex !== null"
                        max-width="420"
                        scrollable
                        @input="editCommandIndex = null"
                    >
                        <v-card>
                            <v-card-title><translate>Redigera</translate></v-card-title>
                            <v-divider />
                            <v-card-text>
                                <CommandWrapper
                                    v-if="editCommand"
                                    :endpoint-id="id"
                                    is-root
                                    single
                                    :command="editCommand.command"
                                    :initial-arguments="editCommand.arguments"
                                    :body-value="editCommand.body"
                                    @updatedArguments="updatedCommand = $event"
                                />
                            </v-card-text>
                            <v-divider />
                            <v-card-actions>
                                <v-btn
                                    :disabled="!updatedCommand"
                                    color="primary"
                                    @click="updateCommand(updatedCommand, editCommandIndex)"
                                >
                                    <translate>Uppdatera</translate>
                                </v-btn>
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
                                    Kommando
                                </th>
                                <th v-translate>
                                    Argument
                                </th>
                                <th />
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="(command, index) in commandQueue"
                                :key="command.key"
                            >
                                <td>
                                    <v-chip
                                        small
                                        class="mr-2"
                                    >
                                        {{ index + 1 }}
                                    </v-chip>
                                    {{ command.command.path.join(' > ') }}
                                </td>
                                <td>
                                    <small>
                                        <span
                                            v-for="(value, key, i) in command.arguments"
                                            :key="'command' + i"
                                        >
                                            {{ key }}: {{ value }}
                                        </span>
                                        <span v-if="command.body">{{ command.body.substr(0, 10) }}...</span>
                                    </small>
                                </td>
                                <td width="1">
                                    <div class="d-flex justify-end">
                                        <v-btn
                                            v-if="command.hasArguments"
                                            icon
                                            @click="editCommandIndex = index"
                                        >
                                            <v-icon>mdi-pencil</v-icon>
                                        </v-btn>
                                        <v-btn
                                            icon
                                            @click="removeCommand(index)"
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
        <SaveTemplateDialog
            v-model="templateDialog"
            :commands="commandQueue"
            max-width="320"
            :endpoint="endpoint"
        />

        <EndpointProvisionResult
            ref="provisionDialog"
            v-model="resultDialog"
            :endpoints="checked"
            @update:loading="resultLoading = $event"
            @update:error="error = $event"
        />

        <ErrorMessage :error="errors" />
    </div>
</template>

<script>
import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import EndpointGrid from '@/vue/components/epm/endpoint/EndpointGrid'
import CommandWrapper from '@/vue/components/epm/endpoint/CommandWrapper'
import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import SaveTemplateDialog from '@/vue/components/epm/endpoint/SaveTemplateDialog'
import EndpointProvisionResult from '@/vue/views/epm/endpoint/single/EndpointProvisionResult'

export default {
    name: 'EndpointCommandsApply',
    components: {
        EndpointProvisionResult,
        SaveTemplateDialog,
        ErrorMessage,
        CommandWrapper,
        EndpointGrid,
        PageSearchFilter,
    },
    mixins: [SingleEndpointMixin],
    data() {
        return {
            loading: false,
            editCommandIndex: null,
            updatedCommand: null,

            templateDialog: false,
            checked: [parseInt(this.id)],

            resultLoading: false,
            provisionId: null,
            resultDialog: null,
            errors: null
        }
    },
    computed: {
        commandQueue() {
            return Object.values(this.$store.state.endpoint.commandQueue).map(command => {
                return {
                    ...command,
                    hasArguments: Object.keys(command.arguments).length > 0
                }
            })
        },
        editCommand() {
            return this.editCommandIndex !== null ? this.commandQueue[this.editCommandIndex] : null
        },
        provisionEndpointId() {
            if (this.checked.length > 1) {
                return null
            }

            return this.checked.length > 0 ? this.checked[0] : this.id
        }
    },
    watch: {
        editCommandIndex(newValue) {
            if (newValue === null) {
                this.updatedCommand = null
            }
        }
    },
    methods: {
        settingObjects(nodes) {
            return nodes.map(node => {
                const [title, options, children, setting] = node
                return { title, options, children, setting, orig: node }
            })
        },
        serializeCommands() {
            return this.commandQueue.map(command => ({
                command: command.command.path,
                arguments: command.arguments,
                body: command.body,
            }))
        },
        updateCommand(command, index) {
            this.$store
                .commit('endpoint/queueUpdateCommand', {
                    index: index,
                    command: {
                        command: command.command,
                        arguments: command.args,
                        body: command.body
                    }
                })

            this.editCommandIndex = null
        },
        removeCommand(index) {
            this.$store
                .commit('endpoint/queueRemoveCommand', index)
        },
        apply() {
            const commands = this.serializeCommands()
            this.$refs.provisionDialog.apply({commands: commands})
        },
    },
}
</script>
