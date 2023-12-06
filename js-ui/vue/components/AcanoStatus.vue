<template>
    <v-expansion-panel :readonly="provider.is_service_node && iconColor == 'green'">
        <v-expansion-panel-header :hide-actions="provider.is_service_node">
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
                <template v-else-if="provider.is_service_node">
                    <i><translate>Uptime</translate>: {{ provider.timesince }}</i> <span v-if="provider.softwareVersion">v</span>{{ provider.softwareVersion }}
                </template>
                <div v-else>
                    <i><translate>Uptime</translate>: {{ provider.timesince }}</i>
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
                <v-simple-table v-if="provider.softwareVersion">
                    <tbody>
                        <tr>
                            <th
                                v-translate
                                class="text-left"
                            >
                                Version
                            </th>
                            <td class="text-right">
                                {{ provider.softwareVersion }}
                            </td>
                        </tr>

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

                        <tr
                            v-for="alarm in provider.alarms || []"
                            :key="alarm.type"
                        >
                            <td class="text-left">
                                <v-icon>mdi-alert-circle</v-icon> <translate>Varning!</translate> {{ alarm.type }}
                                <span v-if="alarm.extra">{{ alarm.extra }}</span>
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
export default {
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
    },
}
</script>
