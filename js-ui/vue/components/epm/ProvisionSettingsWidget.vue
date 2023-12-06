<template>
    <v-card class="mb-6">
        <v-card-text>
            <v-form class="mb-4">
                <v-select
                    v-model="manufacturer"
                    :label="$gettext('Modell')"
                    :items="manufacturers"
                />
                <v-simple-table v-if="manufacturer == 'cisco'">
                    <tbody>
                        <tr>
                            <th>
                                Address
                            </th>
                            <td>
                                <v-text-field
                                    :value="provision.host"
                                    readonly
                                    hide-details
                                    append-icon="mdi-content-copy"
                                    @click:append="$refs.copySnackbar.copy(provision.host)"
                                />
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Path
                            </th>
                            <td>
                                <v-text-field
                                    :value="provision.path"
                                    :hint="$gettext('Path')"
                                    hide-details
                                    persistent-hint
                                    append-icon="mdi-content-copy"
                                    @click:append="$refs.copySnackbar.copy(provision.path)"
                                />
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Type
                            </th>
                            <td>
                                TMS
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Protocol
                            </th>
                            <td>
                                HTTPS
                            </td>
                        </tr>
                        <tr>
                            <th>
                                xConfiguration CLI
                            </th>
                            <td>
                                <v-dialog max-width="640">
                                    <template v-slot:activator="{ on }">
                                        <v-btn
                                            small
                                            v-on="on"
                                        >
                                            <translate>Visa</translate>
                                        </v-btn>
                                    </template>
                                    <v-card>
                                        <v-card-title>
                                            <translate>xConfiguration CLI</translate>
                                        </v-card-title>
                                        <v-divider />
                                        <v-card-text>
                                            <v-textarea
                                                hide-details
                                                :value="provision.xcommand"
                                                append-icon="mdi-content-copy"
                                                @click:append="$refs.copySnackbar.copy(provision.xcommand, $event.target)"
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
                            </td>
                        </tr>
                    </tbody>
                </v-simple-table>

                <v-simple-table v-else-if="manufacturer == 'poly_group'">
                    <tbody>
                        <tr>
                            <th>
                                Server Address
                            </th>
                            <td>
                                <v-text-field
                                    :value="provision.host"
                                    readonly
                                    hide-details
                                    append-icon="mdi-content-copy"
                                    @click:append="$refs.copySnackbar.copy(provision.host)"
                                />
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Type
                            </th>
                            <td>
                                RPRM
                            </td>
                        </tr>

                        <tr>
                            <th>
                                Username
                            </th>
                            <td>
                                <v-text-field
                                    :value="provision.key"
                                    hide-details
                                    persistent-hint
                                    append-icon="mdi-content-copy"
                                    @click:append="$refs.copySnackbar.copy(provision.key)"
                                />
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Domain
                            </th>
                            <td>
                                {{ provision.key }}
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Password
                            </th>
                            <td>
                                {{ provision.key }}
                            </td>
                        </tr>
                    </tbody>
                </v-simple-table>
                <v-simple-table v-else-if="manufacturer == 'poly_x'">
                    <tbody>
                        <tr>
                            <th>
                                Server Address
                            </th>
                            <td>
                                <v-text-field
                                    :value="provision.host + provision.polyPath"
                                    readonly
                                    hide-details
                                    append-icon="mdi-content-copy"
                                    @click:append="$refs.copySnackbar.copy(provision.host + provision.polyPath)"
                                />
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Type
                            </th>
                            <td>
                                HTTPS
                            </td>
                        </tr>

                        <tr>
                            <th>
                                Username
                            </th>
                            <td>
                                <v-text-field
                                    :value="provision.key"
                                    hide-details
                                    persistent-hint
                                    append-icon="mdi-content-copy"
                                    @click:append="$refs.copySnackbar.copy(provision.key)"
                                />
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Domain
                            </th>
                            <td>
                                {{ provision.key }}
                            </td>
                        </tr>
                        <tr>
                            <th>
                                Password
                            </th>
                            <td>
                                {{ provision.key }}
                            </td>
                        </tr>
                    </tbody>
                </v-simple-table>
            </v-form>
        </v-card-text>
    </v-card>
</template>
<script>
export default {
    name: 'ProvisionSettingsWidget',
    data() {
        return {
            manufacturer: 'cisco',
            manufacturers: [
                {text: 'Cisco', value: 'cisco'},
                {text: 'Poly HDX + Group', value: 'poly_group'},
                {text: 'Poly Trio + X Series', value: 'poly_x'},
            ]
        }
    },
    computed: {
        provision() {
            const path = this.settings.provision_path || '/tms/' + this.settings.secret_key + '/'
            const polyPath = this.settings.provision_poly_path || '/ep/poly/' + this.settings.secret_key
            const host = this.settings.provision_domain || this.$store.state.site.epmHostname || window.location.host
            return {
                host,
                path,
                polyPath,
                key: this.settings.secret_key,
                xcommand: `
xConfiguration Provisioning Mode: TMS
xConfiguration Provisioning ExternalManager Address: "${ host }"
xConfiguration Provisioning ExternalManager Path: "${ path }"
xConfiguration Provisioning ExternalManager Protocol: HTTPS
`.trim(),
            }
        },
        settings() {
            return this.$store.state.endpoint.settings
        },
    }
}
</script>
