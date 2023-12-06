<template>
    <div style="width:100%;">
        <v-expansion-panel class="grey lighten-4">
            <v-expansion-panel-header>
                <div class="shrink mr-4">
                    <v-progress-circular
                        v-if="loading"
                        size="24"
                        width="2"
                        indeterminate
                        color="primary"
                    />
                    <v-icon
                        v-else
                        :color="iconColor"
                    >
                        {{ icon }}
                    </v-icon>
                </div>

                <div>
                    <strong class="d-block mb-2">{{ title }}</strong>

                    <div
                        v-if="loading"
                        v-translate
                    >
                        Laddar...
                    </div>
                    <div v-else-if="server.error">
                        <i v-translate>Fel vid kontakt</i>
                    </div>
                    <div v-else>
                        <i><translate>Version</translate>: {{ server.version }}</i>
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
                class="white px-0"
            >
                <v-divider />
                <v-simple-table>
                    <tbody>
                        <tr>
                            <th v-translate>
                                Produkt
                            </th>
                            <td class="text-right">
                                {{ server.product_name }}
                            </td>
                        </tr>
                        <tr v-if="server.release">
                            <th
                                v-translate
                                class="text-left"
                            >
                                Version
                            </th>
                            <td class="text-right">
                                {{ server.version }} build ({{ server.release.substr(0, 6) }})
                            </td>
                        </tr>
                        <tr>
                            <th
                                v-translate
                                class="text-left"
                            >
                                Licensstatus
                            </th>
                            <td class="text-right">
                                <span :class="licenseStatusColor">{{ licenseStatusText }}</span>
                            </td>
                        </tr>
                        <slot name="extraRows" />
                    </tbody>
                </v-simple-table>
            </v-expansion-panel-content>
        </v-expansion-panel>

        <template v-if="allWarnings.length && !loading">
            <v-alert
                v-for="(warning, i) in allWarnings"
                :key="`warning${i}`"
                :type="warning.type || 'warning'"
                :icon="warning.icon || 'mdi-alert-outline'"
                class="mb-0 mt-2 pl-6"
                dense
                text
            >
                <small>{{ warning.message }}</small>
            </v-alert>
        </template>
    </div>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

export default {
    props: {
        title: { type: String, required: true },
        server: {
            type: Object,
            required: true,
        },
        loading: Boolean,
        licenseStatus: { type: String, default: '' },
        licenseIcon: { type: String, default: '' },
        licenseColor: { type: String, default: '' },
        warnings: { type: Array, default() { return [] } }
    },
    computed: {
        license() {
            return this.$store.getters['site/license']
        },
        licenseWarnings() {
            const warnings = (this.license.warnings || []).map(w => { return { message: w } })

            if (this.licenseStatusBase === 0) {
                warnings.push({
                    message: $gettext('Er licens är inte längre giltig.'),
                    type: 'error',
                    icon: 'mdi-alert-circle'
                })
            }

            return warnings
        },
        licenseStatusBase() {
            return this.license.status.base.active
        },
        licenseStatusText() {
            if (this.licenseStatusBase === 0) {
                return $gettext('Ogiltig')
            }

            if (this.licenseStatus) {
                return this.licenseStatus
            }

            if (this.licenseStatusBase === 1) {
                return $gettext('Löpt ut')
            }

            return $gettext('Giltig')
        },
        licenseStatusColor() {
            let color = 'success'

            if (this.licenseStatusBase === 0) {
                color = 'error'
            }
            else if (this.licenseColor) {
                color = this.licenseColor
            }
            else if (this.licenseStatusBase === 1) {
                color = 'warning'
            }

            return `${color}--text`
        },
        allWarnings() {
            const serverWarnings = this.server.warnings && this.server.warnings.length ? this.server.warnings : []
            return [
                ...serverWarnings.map(w => { return {...w, type: 'warning'} }),
                ...this.licenseWarnings,
                ...this.warnings
            ]
        },
        hasWarnings() {
            return this.allWarnings.some(w => (!w.type || ['warning', 'error'].includes(w.type)))
        },
        iconColor() {
            if (this.server.error || this.licenseStatusBase === 0) {
                return 'error'
            }

            if (this.licenseColor) {
                return this.licenseColor
            }

            if (this.hasWarnings || this.licenseStatusBase === 1) {
                return 'warning'
            }

            return 'success'
        },
        icon() {
            if (this.server.error || this.licenseStatusBase === 0) {
                return 'mdi-alert-circle'
            }

            if (this.licenseIcon) {
                return this.licenseIcon
            }

            if (this.hasWarnings || this.licenseStatusBase === 1) {
                return 'mdi-alert-outline'
            }

            return 'mdi-check-circle'
        },
    },
}
</script>
