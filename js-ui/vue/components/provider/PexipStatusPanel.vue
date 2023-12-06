<template>
    <v-expansion-panel>
        <v-expansion-panel-header>
            <v-icon :color="iconColor">
                {{ icon }}
            </v-icon>

            <div>
                <strong class="d-block mb-2">{{ provider.name || provider.web_host }}</strong>

                <div
                    v-if="loading"
                    v-translate
                >
                    Laddar...
                </div>
                <div v-else-if="provider.error">
                    <i v-translate>Fel vid kontakt</i>
                </div>
                <div v-if="uptimeText">
                    <i><translate>Uptime</translate>: {{ uptimeText }}</i>
                </div>
                <div v-else-if="provider.worker_nodes && provider.worker_nodes.length">
                    <i>{{ provider.worker_nodes ? provider.worker_nodes.length : '-' }} noder</i>
                </div>
            </div>


            <v-progress-linear
                :active="loading"
                :indeterminate="loading"
                absolute
                bottom
                color="primary"
            />
        </v-expansion-panel-header>
        <v-expansion-panel-content
            v-if="!loading"
            class="px-0"
        >
            <v-divider />
            <div v-if="provider.error">
                <translate>Fel vid anslutning</translate>: <span class="text-danger">{{ provider.error }}</span>
            </div>
            <div v-else>
                <v-simple-table>
                    <tbody>
                        <tr v-if="provider.calls_url || provider.call_count">
                            <td class="text-left">
                                <router-link
                                    :to="`/calls/?provider=${provider.id || ''}`"
                                >
                                    <translate>Aktiva samtal</translate>
                                </router-link>
                            </td>
                            <td class="text-right">
                                {{ provider.call_count }}
                            </td>
                        </tr>

                        <tr v-if="provider.calls_url || provider.call_count">
                            <td
                                v-translate
                                class="text-left"
                            >
                                Deltagare
                            </td>
                            <td class="text-right">
                                {{ provider.call_leg_count }}
                            </td>
                        </tr>
                        <tr v-if="provider.licenses.audio">
                            <td
                                v-translate
                                class="text-left"
                            >
                                Licenser ljud
                            </td>
                            <td class="text-right">
                                {{ provider.licenses.audio.current }} / {{ provider.licenses.audio.total }}
                            </td>
                        </tr>
                        <tr v-if="provider.licenses.ports">
                            <td
                                v-translate
                                class="text-left"
                            >
                                Licenser portar
                            </td>
                            <td class="text-right">
                                {{ provider.licenses.ports.current }} / {{ provider.licenses.ports.total }}
                            </td>
                        </tr>
                        <tr v-if="provider.licenses.systems">
                            <td
                                v-translate
                                class="text-left"
                            >
                                Licenser system
                            </td>
                            <td class="text-right">
                                {{ provider.licenses.systems.current }} / {{ provider.licenses.systems.total }}
                            </td>
                        </tr>

                        <tr
                            v-for="alarm in provider.alarms || []"
                            :key="alarm.id"
                        >
                            <td class="text-left">
                                <v-icon>mdi-alert-circle</v-icon> <translate>Varning!</translate> <span :title="alarm.details">{{ alarm.name }}</span>
                                <div>
                                    <span v-if="alarm.instance">{{ alarm.instance }}
                                        <span v-if="alarm.node"> ({{ alarm.node }})</span>
                                    </span>
                                    <span v-else-if="alarm.node">{{ alarm.node }}</span>
                                </div>
                            </td>
                            <td class="text-right">
                                {{ alarm.timesince }}
                            </td>
                        </tr>
                    </tbody>
                </v-simple-table>
            </div>
        </v-expansion-panel-content>
    </v-expansion-panel>
</template>

<script>
import { $gettext, $gettextInterpolate } from '@/vue/helpers/translate'

export default {
    name: 'PexipStatusPanel',
    props: {
        provider: {
            type: Object,
            required: true,
        },
        counter: {
            type: Number,
            default: 1,
        },
    },
    data() {
        return {
            workerHeaders: [
                {
                    text: $gettext('Nod'),
                    value: 'name',
                },
                {
                    text: $gettext('Load'),
                    value: 'media_load',
                },
                {
                    text: $gettext('Tokens'),
                    value: 'media_tokens_used',
                },
                {
                    text: $gettext('Location'),
                    value: 'system_location',
                },
                {
                    text: $gettext('Uptime'),
                    value: 'uptime_text',
                },
            ]
        }
    },
    computed: {
        loading() {
            return !this.provider || (!this.provider.name && !this.provider.web_host && !this.provider.error)
        },
        iconColor() {
            if (this.loading) {
                return 'primary'
            }
            if (this.provider.alarms && this.provider.alarms.length) {
                return 'yellow'
            }
            if (this.provider.error) {
                return 'red'
            }

            return 'green'
        },
        icon() {
            if (this.loading) {
                return 'mdi-loading'
            }
            if (this.provider.error) {
                return 'mdi-alert-circle'
            }

            return 'mdi-check-circle'
        },
        uptimeText() {
            if (!this.provider.worker_nodes) return ''

            const uptimes = this.provider.worker_nodes.map(vm => vm.uptime_text).filter(s => !!s)

            if (uptimes.length > 2) {
                return uptimes.slice(0, 1).join(', ') + $gettextInterpolate($gettext(' + %{ length } till'), { length: uptimes.length - 2 })
            }

            return uptimes.join(', ')
        }
    },
}
</script>
