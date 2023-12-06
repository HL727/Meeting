<template>
    <Page
        :title="displayName"
        icon="mdi-account"
        :actions="[
            { type: 'api', url: apiUrl },
            { type: 'refresh', click: () => loadData() },
        ]"
    >
        <template v-slot:content>
            <div style="position: relative">
                <v-progress-linear
                    :active="loading"
                    indeterminate
                    absolute
                    top
                />
            </div>

            <v-alert
                v-if="error"
                type="error"
                class="my-4"
            >
                {{ error }}
            </v-alert>

            <v-row>
                <v-col
                    cols="12"
                    md="7"
                >
                    <v-skeleton-loader
                        v-if="loading"
                        :loading="loading"
                        type="list-item, list-item, list-item"
                        class="mt-4"
                    />
                    <v-simple-table v-else>
                        <tbody>
                            <tr>
                                <th v-translate>
                                    Namn
                                </th>
                                <td>{{ displayName }}</td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    E-post
                                </th>
                                <td>{{ user.email }}</td>
                            </tr>
                            <tr>
                                <th v-translate>
                                    Beskrivning
                                </th>
                                <td>{{ user.description || '' }}</td>
                            </tr>

                            <tr v-if="customers.length > 1">
                                <th v-translate>
                                    Kund
                                </th>
                                <td>
                                    <TenantPicker
                                        tenant-field="pexip_tenant_id"
                                        :value="user.tenant"
                                        :provider-id="$store.state.site.providerId"
                                        @input="setTenant($event)"
                                    />
                                </td>
                            </tr>

                            <tr v-if="enableOrganization">
                                <th v-translate>
                                    Organisationsenhet
                                </th>
                                <td>
                                    <OrganizationPicker
                                        :value="user.organization_unit"
                                        @input="setOrganizationUnit($event)"
                                    />
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                </v-col>
                <v-col
                    cols="12"
                    md="5"
                >
                    <h3 class="overline my-4">
                        {{ $ngettext('Mötesrum', 'Mötesrum', 2) }}
                    </h3>
                    <v-skeleton-loader
                        v-if="loading"
                        :loading="loading"
                        type="image"
                        height="100"
                    />
                    <v-card v-else-if="user.cospaces && user.cospaces.length">
                        <v-list-item
                            v-for="cospace in user.cospaces"
                            :key="'cospace' + cospace.id"
                            :two-line="!!cospace.call_id"
                            :to="{ name: 'pexip_cospaces_details', params: { id: cospace.id } }"
                        >
                            <v-icon class="align-self-center mr-4">
                                mdi-door-closed
                            </v-icon>
                            <v-list-item-content>
                                <v-list-item-title>
                                    {{ cospace.name }}
                                </v-list-item-title>
                                <v-list-item-subtitle v-if="cospace.call_id">
                                    {{ cospace.call_id }}
                                </v-list-item-subtitle>
                            </v-list-item-content>
                        </v-list-item>
                    </v-card>
                    <v-alert
                        v-else
                        type="info"
                        outlined
                    >
                        <translate>Användaren har just nu inga mötesrum</translate>
                    </v-alert>
                </v-col>
            </v-row>
        </template>
    </Page>
</template>

<script>
import Page from '@/vue/views/layout/Page'

import TenantPicker from '@/vue/components/tenant/TenantPicker'
import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'

export default {
    name: 'PexipUserDetails',
    components: { Page, OrganizationPicker, TenantPicker },
    mixins: [PageSearchMixin],
    props: {
        id: {
            type: Number,
            required: true,
        }
    },
    data() {
        return {
            removeDialog: false,
            editDialog: false,
            userData: {},
            error: '',
        }
    },
    computed: {
        enableOrganization() {
            return this.$store.state.site.enableOrganization
        },
        apiUrl() {
            return `configuration/v1/end_user/${this.user.id}/`
        },
        displayName() {
            if (!this.user.id) return ''
            return this.user.display_name || `${this.user.first_name || ''} ${this.user.last_name || ''}`
        },
        user() {
            if (this.userData) {
                return this.userData
            }
            return {
                cospaces: [],
            }
        },
        customers() {
            return Object.values(this.$store.state.site.customers)
        }
    },
    mounted() {
        this.loadData()
    },
    methods: {
        loadData() {
            this.setLoading(true)
            this.editDialog = false
            this.$store.dispatch('user/get', this.id).then((user) => {
                this.setLoading(false)
                this.userData = {
                    ...user,
                    loaded: true,
                }
            }).catch(e => {
                this.setLoading(false)
                this.error = e.toString()
            })
        },
        setTenant(tenantId) {
            return this.$store.dispatch('user/pexip/update', { id: this.id, tenant: tenantId })
        },
        setOrganizationUnit(unitId) {
            return this.$store.dispatch('user/setOrganizationUnit', { userIds: [this.id], unitId: unitId })
        }
    }
}
</script>
