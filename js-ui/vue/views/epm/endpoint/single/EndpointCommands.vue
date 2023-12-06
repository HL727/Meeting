<template>
    <div>
        <PageSearchFilter :sticky="commandQueue.length > 0">
            <template v-slot:search>
                <v-text-field
                    v-model="text_filter"
                    hide-details
                    prepend-inner-icon="mdi-magnify"
                    :placeholder="$gettext('Sök commands') + '...'"
                    outlined
                    dense
                />
            </template>
            <template v-slot:filter>
                <CommandQueue
                    :queue="commandQueueWithPath"
                />

                <v-btn
                    v-if="commandQueue.length"
                    dark
                    small
                    color="primary"
                    class="mr-4"
                    :to="{ name: 'endpoint_command_apply', params: { id: endpoint.id } }"
                >
                    <v-icon left>
                        mdi-eye
                    </v-icon>
                    <translate>Granska</translate>
                </v-btn>
                <v-btn
                    v-if="commandQueue.length"
                    dark
                    small
                    color="error"
                    @click="$store.commit('endpoint/clearCommandQueue')"
                >
                    <v-icon left>
                        mdi-close
                    </v-icon>
                    <span><translate>Rensa</translate></span>
                </v-btn>
                <v-btn
                    v-if="!commandQueue.length"
                    color="primary"
                    small
                    @click="templateDialog = true"
                >
                    <v-icon left>
                        mdi-content-save-move
                    </v-icon>
                    <translate>Ladda mall</translate>
                </v-btn>
            </template>
        </PageSearchFilter>
        <v-divider />

        <TabLoaderIndicator v-if="loading" />
        <div v-else>
            <v-card
                v-if="error"
                class="my-4"
            >
                <v-card-text>
                    <v-alert type="error">
                        <strong><translate>Ett fel uppstod.</translate></strong><br>
                        <span
                            v-if="endpoint.has_direct_connection"
                            v-translate
                        >Kontrollera din anslutning och försök igen</span>
                        <span
                            v-else
                            v-translate
                        >Aktiv anslutning saknas, och ingen cachad data hittades</span>
                    </v-alert>

                    <UploadCommandsFileData
                        v-if="endpoint"
                        :endpoint="endpoint"
                        @done="loadData"
                        @error="error = $event"
                    />

                    <v-textarea
                        readonly
                        light
                        class="mt-4"
                        :label="$gettext('Felinformation')"
                        :value="error"
                        rows="2"
                    />
                </v-card-text>
            </v-card>
            <v-tabs
                :vertical="$vuetify.breakpoint.mdAndUp"
                background-color="grey lighten-4"
            >
                <v-tab
                    v-for="node in commandObjects(commands)"
                    :key="node.title"
                    class="text-left justify-start"
                >
                    {{ node.title }}
                </v-tab>
                <v-tab-item
                    v-for="node in commandObjects(commands)"
                    :key="node.title + 'item'"
                >
                    <v-card flat>
                        <v-card-title>{{ node.title }}</v-card-title>
                        <v-card-text>
                            <CommandTree
                                :endpoint-id="endpoint.id"
                                :is-root="true"
                                :parent="node"
                                :tree="node.command ? [node.orig] : node.children"
                                :filter="filter"
                            />
                        </v-card-text>
                    </v-card>
                </v-tab-item>
            </v-tabs>
        </div>
        <EndpointTemplatePicker
            v-model="templateDialog"
            require-commands
            @cancel="templateDialog = false"
            @load="loadTemplate"
        />
    </div>
</template>

<script>
import {GlobalEventBus} from '@/vue/helpers/events'

import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'
import TabLoaderIndicator from '@/vue/views/epm/endpoint/single/TabLoaderIndicator'

import CommandTree from '@/vue/components/epm/endpoint/CommandTree'
import CommandQueue from '@/vue/components/epm/endpoint/CommandQueue'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import EndpointTemplatePicker from '@/vue/components/epm/EndpointTemplatePicker'
import UploadCommandsFileData from '@/vue/components/epm/endpoint/single/UploadCommandsFileData'

export default {
    components: {
        UploadCommandsFileData,
        EndpointTemplatePicker,
        TabLoaderIndicator,
        CommandTree,
        CommandQueue,
        PageSearchFilter,
    },
    mixins: [SingleEndpointMixin],
    data() {
        return {
            emitter: new GlobalEventBus(this),
            loading: true,
            error: '',
            text_filter: '',
            templateDialog: null,

        }
    },
    computed: {
        commandData() {
            return this.$store.state.endpoint.commands[this.id]
        },
        commands() {
            return this.$store.state.endpoint.commands[this.id]?.data || []
        },
        commandQueue() {
            return this.$store.state.endpoint.commandQueue || []
        },
        commandQueueWithPath() {
            return this.commandQueue.map(command => ({ ...command, displayPath: command.command.path.join(' ') }))
        }
    },
    mounted() {
        this.emitter.on('refresh', () => this.loadData())
        this.loadData()
    },
    methods: {
        commandObjects(nodes) {
            const filtered = !this.text_filter
                ? nodes
                : nodes.filter(
                    node =>
                        JSON.stringify(node)
                            .toLowerCase()
                            .indexOf(this.text_filter.toLowerCase()) != -1
                )

            return filtered.map(node => {
                const [title, options, children, command] = node
                return { title, options, children, command, orig: node }
            })
        },
        loadTemplate(templates) {
            const template = (templates.length ? templates[0] : templates)
            const commands = template.commands.map(command => {
                let commandMeta = null
                this.commands.map(c => {
                    if (c[3] && c[3].path.join('/') === command.command.join('/')) commandMeta = c
                })
                return {...command, command: { path: command.command }, ...commandMeta}
            })
            this.$store.commit('endpoint/setCommandQueue', commands)
            this.templateDialog = false
        },
        loadData() {
            this.loading = true
            this.error = ''
            this.$store.dispatch('endpoint/getCommands', this.id).then(() => {
                this.loading = false
                this.emitter.emit('loading', false)
            }).catch(e => {
                this.loading = false
                this.error = e
                this.emitter.emit('loading', false)
            })
        },

    }
}
</script>
