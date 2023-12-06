<template>
    <v-expansion-panel>
        <v-expansion-panel-header>
            <v-icon :color="iconColor">
                {{ icon }}
            </v-icon>
            <div>
                <strong class="d-block mb-2">{{ provider.title }}</strong>
                <div
                    v-if="loading"
                    v-translate
                >
                    Laddar...
                </div>
                <div v-else-if="provider.error">
                    <i v-translate>Fel vid kontakt</i>
                </div>
                <div v-else>
                    <i><translate>Uptime</translate>: {{ provider.uptime }}</i>
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
            <v-text-field
                v-if="provider.error && provider.error !== true"
                class="mr-2 ml-2"
                readonly
                :value="provider.error"
                append-icon="mdi-content-copy"
                @click:append="$refs.copySnackbar.copy(provider.error)"
            />
            <v-divider v-if="!provider.error" />
            <v-simple-table v-if="provider.software_version">
                <tbody>
                    <tr>
                        <th
                            v-translate
                            class="text-left"
                        >
                            Version
                        </th>
                        <td class="text-right">
                            {{ provider.software_version }}
                        </td>
                    </tr>
                </tbody>
            </v-simple-table>
            <v-simple-table v-if="provider.licenses && provider.licenses.peers">
                <thead>
                    <tr>
                        <th
                            v-translate
                            class="text-left"
                            colspan="2"
                        >
                            Licensanvändning
                        </th>
                    </tr>
                </thead>
                <tbody>
                    <tr
                        v-for="peer in provider.licenses.peers"
                        :key="peer.peer"
                    >
                        <td class="text-left">
                            {{ peer.peer }}
                        </td>
                        <td class="text-right py-3">
                            <div
                                v-for="license in peer.records"
                                :key="license.licence_type"
                            >
                                <strong>{{ license.license_type }}</strong> {{ license.inuse }} ({{
                                    license.usage_percent | floatformat
                                }}%, max {{ license.max_percent | floatformat }}%)
                            </div>
                        </td>
                    </tr>
                </tbody>
            </v-simple-table>
            <v-simple-table v-if="provider.protocols">
                <template v-slot:default>
                    <thead>
                        <tr>
                            <th
                                v-translate
                                class="text-left"
                                colspan="2"
                            >
                                Aktiva samtal
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for="(calls, protocol) in provider.protocols"
                            :key="protocol"
                        >
                            <td class="text-left">
                                {{ protocol }}
                            </td>
                            <td class="text-right">
                                {{ calls }}
                            </td>
                        </tr>
                        <tr v-if="provider.calls_url">
                            <td colspan="2">
                                <v-btn
                                    color="orange"
                                    small
                                    depressed
                                    :href="provider.calls_url"
                                >
                                    <translate :translate-params="{count: provider.count}">
                                        Visa %{count} samtal
                                    </translate>
                                </v-btn>
                            </td>
                        </tr>
                    </tbody>
                </template>
            </v-simple-table>
            <v-simple-table v-if="provider.alarms && provider.alarms.total_count">
                <template v-slot:default>
                    <thead>
                        <tr>
                            <th
                                v-translate
                                class="text-left"
                                colspan="2"
                            >
                                Varningar
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td
                                v-translate
                                class="text-left"
                            >
                                Varningar
                            </td>
                            <td class="text-right">
                                {{ provider.alarms.total_count }}
                            </td>
                        </tr>
                        <tr>
                            <td
                                v-translate
                                class="text-left"
                            >
                                Ohanterade
                            </td>
                            <td class="text-right">
                                {{ provider.alarms.unacknowledged_count }}
                            </td>
                        </tr>
                    </tbody>
                </template>
            </v-simple-table>
        </v-expansion-panel-content>

        <ClipboardSnackbar ref="copySnackbar" />
    </v-expansion-panel>
</template>

<script>
import ClipboardSnackbar from '@/vue/components/ClipboardSnackbar'

export default {
    components: { ClipboardSnackbar },
    filters: {
        floatformat(value) {
            return parseFloat(value || 0)
                .toString()
                .replace(/\.(.).*/, '.$1')
        },
    },
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
            return !this.provider || (!this.provider.uptime && !this.provider.error)
        },
        iconColor() {
            if (this.loading) {
                return 'primary'
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
