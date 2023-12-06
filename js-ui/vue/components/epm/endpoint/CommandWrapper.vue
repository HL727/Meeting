<template>
    <div>
        <div v-show="Object.keys(command.arguments).length > 0 || command.body">
            <v-row :class="single ? 'mt-0' : 'ma-0'">
                <v-col
                    class="pl-4 d-flex align-center"
                    :class="single ? '' : 'py-0'"
                >
                    <div>
                        <span v-if="parent && parent.parent">{{ parent.parent.title }} - </span>
                        <span v-if="parent">{{ parent.title }} - </span>
                        <strong>{{ command.name }}</strong>
                    </div>
                </v-col>
                <v-col
                    v-if="!single"
                    class="text-right flex-grow-0 grey lighten-4 px-4 ml-auto"
                >
                    <span class="text-no-wrap">
                        <div class="d-flex align-center">
                            <v-btn
                                v-if="!commandQueue.length"
                                :disabled="!valid"
                                color="primary"
                                :loading="loading"
                                @click="run"
                            >
                                <translate>Run</translate>
                            </v-btn>

                            <v-btn
                                v-if="!inQueue"
                                color="success"
                                class="ml-2"
                                :disabled="!valid"
                                outlined
                                @click="queueCommand"
                            >
                                <translate>Lägg i kö</translate>
                            </v-btn>
                            <template v-else>

                                <v-chip
                                    color="success"
                                    outlined
                                    class="ml-2"
                                >
                                    <span>
                                        {{ queuedCommands.length }}
                                        <translate>i kö</translate>
                                    </span>
                                </v-chip>
                                <v-btn
                                    color="success"
                                    class="ml-2"
                                    fab
                                    x-small
                                    @click="queueCommand"
                                >
                                    <v-icon>mdi-plus</v-icon>
                                </v-btn>
                            </template>
                        </div>
                    </span>
                </v-col>
            </v-row>
            <v-card-text
                :class="single ? 'pa-0' : 'lighten-4 grey pl-4'"
            >
                <v-form
                    v-model="valid"
                    @submit.prevent="run"
                >
                    <ArgumentInput
                        v-for="(argument, argumentName) in command.arguments"
                        :key="command.name + argumentName"
                        v-model="argumentValues[argumentName]"
                        :argument="argument"
                        :argument-name="argumentName"
                    />
                    <template v-if="command.body">
                        <v-row>
                            <v-col sm="6">
                                <v-checkbox
                                    v-model="loadBodyFromFile"
                                    :label="$gettext('Load data from file')"
                                />
                            </v-col>
                            <v-col sm="6">
                                <v-file-input
                                    v-if="loadBodyFromFile"
                                    @change="fileUpdate"
                                />
                            </v-col>
                        </v-row>
                        <v-textarea
                            v-if="!loadBodyFromFile"
                            v-model="body"
                            :placeholder="`Input ${command.name} data`"
                            clearable
                        />
                    </template>
                </v-form>
            </v-card-text>
            <v-divider v-if="!single" />
        </div>

        <div v-if="Object.keys(command.arguments).length === 0">
            <v-simple-table @keydown.enter="run">
                <tbody>
                    <tr>
                        <td>
                            <span v-if="parent && parent.parent">{{ parent.parent.title }} - </span>
                            <span v-if="parent">{{ parent.title }} - </span>

                            <strong>{{ command.name }}</strong>
                        </td>
                        <td
                            v-if="!single"
                            width="1"
                            class="text-right"
                        >
                            <div class="text-no-wrap">
                                <div class="d-flex align-center">
                                    <v-btn
                                        v-if="!commandQueue.length"
                                        :disabled="!valid"
                                        color="primary"
                                        :loading="loading"
                                        @click="run"
                                    >
                                        <translate>Run</translate>
                                    </v-btn>

                                    <v-btn
                                        v-if="!inQueue"
                                        color="success"
                                        class="ml-2"
                                        :disabled="!valid"
                                        outlined
                                        @click="queueCommand"
                                    >
                                        <translate>Lägg i kö</translate>
                                    </v-btn>
                                    <template v-else>
                                        <v-chip
                                            color="success"
                                            outlined
                                            class="ml-2"
                                        >
                                            <span>
                                                {{ queuedCommands.length }}
                                                <translate>i kö</translate>
                                            </span>
                                        </v-chip>
                                        <v-btn
                                            color="success"
                                            class="ml-2"
                                            fab
                                            x-small
                                            @click="queueCommand"
                                        >
                                            <v-icon>mdi-plus</v-icon>
                                        </v-btn>
                                    </template>
                                </div>
                            </div>
                        </td>
                    </tr>
                </tbody>
            </v-simple-table>
            <v-divider />
        </div>

        <v-dialog
            v-model="dialog"
            scrollable
            max-width="800"
        >
            <v-card>
                <v-card-title>
                    <translate>Result</translate>
                </v-card-title>
                <v-divider />
                <v-card-text class="pt-4">
                    <ErrorMessage :error="result && result.error" />
                    <pre v-if="result && !result.error">{{ result }}</pre>
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-spacer />
                    <v-btn
                        text
                        color="red"
                        @click="dialog = false"
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
    </div>
</template>
<script>
import ArgumentInput from './ArgumentInput'
import { readFile } from '@/vue/helpers/file'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

export default {
    name: 'CommandWrapper',
    components: { ErrorMessage, ArgumentInput },
    props: {
        command: { required: true, type: Object },
        parent: { type: Object, default: null },
        endpointId: { required: true, type: Number },
        isRoot: { type: Boolean, default: false },
        initialArguments: { type: Object, required: false, default: null },
        bodyValue: { type: String, required: false, default: null },
        single: { type: Boolean, default: false },
    },
    data() {
        const args = {} // arguments is javascript keyword
        Object.entries(this.command.arguments).forEach(a => {
            const [k, v] = a
            args[k] = v.value || v.default || undefined
        })
        Object.assign(args, this.initialArguments || {})

        return {
            dialog: false,
            loading: false,
            result: '',
            valid: false,
            body: this.bodyValue,
            loadBodyFromFile: true,
            argumentValues: args
        }
    },
    computed: {
        commandQueue() {
            return this.$store.state.endpoint.commandQueue || []
        },
        inQueue() {
            return !!this.queuedCommands.length
        },
        queuedCommands() {
            return this.commandQueue.filter(c => c.command.path.join(' ') === this.command.path.join(' '))
        }
    },
    watch: {
        argumentValues: {
            deep: true,
            handler() {
                this.$emit('updatedArguments', {
                    command: this.command,
                    args: this.argumentValues,
                    body: this.body,
                })
            }
        }
    },
    methods: {
        queueCommand() {
            if (!this.valid) return

            this.$store
                .dispatch('endpoint/queueCommand', {
                    command: this.command,
                    args: this.argumentValues,
                    body: this.body,
                })
        },
        run() {
            if (this.valid) {
                this.loading = true
                return this.$store
                    .dispatch('endpoint/runCommand', {
                        endpointId: this.endpointId,
                        command: this.command.path,
                        args: this.argumentValues,
                        body: this.body,
                    })
                    .catch(response => ({ response: response.errors }))
                    .then(response => {
                        this.loading = false
                        this.result = response.response
                        this.dialog = true
                    })
            }
        },
        fileUpdate(file) {
            const isBinary = file.name.match(/\.(png|gif|jpeg|jpg|bmp|p12)$/i)

            return readFile(file, !isBinary).then(body => {
                this.body = !isBinary ? body : body.substr(body.indexOf(',') + 1)
                if (!isBinary) {
                    this.loadBodyFromFile = false
                }
            })
        },
    },
}
</script>
