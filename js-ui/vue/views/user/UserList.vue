<template>
    <Page
        icon="mdi-account-multiple"
        :title="$gettext('Användare')"
        :actions="[
            {
                icon: 'mdi-swap-horizontal',
                disabled: !!provider.id,
                loading: syncLoading,
                click: () => syncUsers(),
                hidden: !$store.state.site.perms.staff
            },
            { type: 'refresh', click: () => searchDebounce() }
        ]"
    >
        <template
            v-if="!isPexip"
            v-slot:tabs
        >
            <UserTabs />
        </template>
        <template v-slot:search>
            <v-form @submit.prevent="searchDebounce(true)">
                <div class="d-flex align-center">
                    <v-text-field
                        v-model="search"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök användare') + '...'"
                        outlined
                        dense
                        class="mr-4"
                    />
                    <v-btn
                        color="primary"
                        :loading="loading"
                        class="mr-md-4"
                        @click="searchDebounce"
                    >
                        <v-icon>mdi-refresh</v-icon>
                    </v-btn>
                </div>
            </v-form>
        </template>
        <template v-slot:filter>
            <VBtnFilterProvider
                v-model="provider"
                :title="$gettext('Visa användare för')"
                :loading="loading"
                only-clusters
                return-object
                @filter="setProvider"
            />
            <VBtnFilter
                v-if="enableOrganization"
                :disabled="loading || !!provider.id"
                :filters="filterList"
                class="mx-4"
                @click="filterDialog = true"
                @removeFilter="resetFilters"
            />
            <form
                class="ml-md-auto text-center"
                @submit="buttonLoading = true"
            >
                <input
                    type="hidden"
                    name="export_to_excel"
                    value="1"
                >
                <input
                    type="hidden"
                    name="filter"
                    :value="search"
                >
                <input
                    type="hidden"
                    name="organization_unit"
                    :value="activeFilters.organizationUnit"
                >
                <input
                    type="hidden"
                    name="customer"
                    :value="customerId"
                >
                <v-btn
                    v-if="!isPexip"
                    :disabled="loading || !!provider.id"
                    small
                    outlined
                    color="primary"
                    type="submit"
                    :loading="exportLoading || loading"
                >
                    <span v-if="page.count">
                        <translate :translate-params="{count: page.count}">Exportera %{count} st</translate>
                    </span>
                    <span
                        v-else
                        v-translate
                    >Exportera alla</span>
                </v-btn>
            </form>
        </template>
        <template v-slot:content>
            <ErrorMessage
                v-if="error"
                :error="error"
            />
            <v-alert
                v-else-if="!loading && !users.length && !search && !hasActiveFilter"
                type="info"
                text
                class="mb-3"
            >
                <translate :translate-params="{ platform: isPexip ? 'Pexip' : 'CMS' }">
                    Kunde inte hitta några användare i %{platform}.
                </translate>
                <translate :translate-params="{ platform: isPexip ? 'Pexip' : 'CMS' }">
                    Kontrollera konfigurerade LDAP-källor i %{platform}.
                </translate>
            </v-alert>
            <v-data-table
                v-model="selected"
                :class="{'footer-left': selected.length}"
                :loading="loading"
                :items="users"
                multiple
                :disable-sort="pagination.itemsPerPage !== -1"
                :show-select="!provider.id"
                :options.sync="pagination"
                :headers="headers"
                :server-items-length="pagination.itemsPerPage === -1 ? -1 : page.count || -1"
                @update:page="setPage"
            >
                <template v-slot:[`item.name`]="{ item }">
                    <router-link
                        :to="{
                            name: item.isPexip ? 'pexip_user_details' : 'user_details',
                            params: { id: item.id },
                            query: item.customerId ? { customer: item.customerId } : null
                        }"
                    >
                        {{ item.name || item.jid }}
                    </router-link>
                </template>
            </v-data-table>

            <TableActionDialog
                :count="selected.length"
                :title="$gettext('Val för samtliga valda användare')"
            >
                <ErrorMessage
                    v-if="bulkError"
                    :error="bulkError"
                />

                <template v-if="provider.id === 0 && !isPexip">
                    <v-card
                        class="mb-4"
                        outlined
                    >
                        <v-card-text>
                            <p
                                class="overline mb-3"
                                style="line-height: 1.5"
                            >
                                <translate>Skicka inbjudan</translate>
                            </p>
                            <p><i><translate>Användaren måste ha både e-postadress samt ett personligt videomötesrum.</translate></i></p>
                            <v-btn
                                color="primary"
                                depressed
                                small
                                :loading="sendingInvite"
                                @click="sendInvites"
                            >
                                <translate>Skicka</translate>
                            </v-btn>
                        </v-card-text>
                    </v-card>
                </template>

                <v-card outlined>
                    <v-card-text>
                        <OrganizationPicker
                            v-if="enableOrganization"
                            v-model="moveToOrgUnit"
                            class="d-flex mr-4"
                            :label="$gettext('Flytta till organisationsenhet')"
                            hide-details
                        />
                        <v-alert
                            v-model="setOrgUnitSuccess"
                            dense
                            dismissible
                            type="success"
                        >
                            <translate>Flyttade</translate>
                        </v-alert>
                        <v-btn
                            :disabled="!moveToOrgUnit"
                            depressed
                            small
                            color="primary"
                            class="mt-4 d-block"
                            @click="setOrgUnit"
                        >
                            <translate>Flytta</translate>
                        </v-btn>
                    </v-card-text>
                </v-card>
            </TableActionDialog>

            <v-dialog
                v-model="inviteSentDialog"
                scrollable
                max-width="640"
            >
                <v-card>
                    <v-card-title><translate>Skickade inbjudningar</translate></v-card-title>
                    <v-divider />
                    <v-simple-table>
                        <thead>
                            <tr>
                                <th /><th v-translate>
                                    Användare
                                </th><th v-translate>
                                    Resultat
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="(invite, i) in inviteSent"
                                :key="`invite_${i}`"
                            >
                                <td>
                                    <v-icon v-if="invite.valid">
                                        mdi-check
                                    </v-icon>
                                    <v-icon v-else>
                                        mdi-alert
                                    </v-icon>
                                </td>
                                <td>
                                    {{ invite.name }}
                                </td>
                                <td>
                                    {{ invite.email || invite.error }}
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
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

            <v-dialog
                v-model="filterDialog"
                max-width="320"
            >
                <v-card>
                    <v-card-title><translate>Filtrera</translate></v-card-title>
                    <v-divider />
                    <v-card-text>
                        <OrganizationPicker
                            v-model="filters.organizationUnit"
                            input-name="organization_unit"
                            :label="$gettext('Organisationsenhet')"
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-actions>
                        <v-btn
                            color="primary"
                            @click="applyFilters"
                        >
                            <translate>Tillämpa</translate>
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
        </template>
    </Page>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'
import { replaceQuery } from '@/vue/helpers/url'
import { itemListSearchPrefix } from '@/consts'

import Page from '@/vue/views/layout/Page'

import VBtnFilter from '@/vue/components/filtering/VBtnFilter'
import VBtnFilterProvider from '@/vue/components/filtering/VBtnFilterProvider'
import TableActionDialog from '@/vue/components/TableActionDialog'
import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'
import UserTabs from '@/vue/components/user/UserTabs'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'

export default {
    name: 'UserList',
    components: { ErrorMessage, UserTabs, OrganizationPicker, Page, VBtnFilter, VBtnFilterProvider, TableActionDialog },
    mixins: [PageSearchMixin],
    // eslint-disable-next-line max-lines-per-function
    data() {
        const pageHistory = history.state?.page || {}
        const orgUnit = (this.$route.query.organization_unit || '').replace(itemListSearchPrefix, '')
        const initialPagination = {
            page: 1,
            itemsPerPage: 10,
            ...( pageHistory.pagination || {} )
        }
        const initialFilters = {
            organizationUnit: orgUnit ? parseInt(orgUnit) : null,
            ...(pageHistory.filters || {})
        }

        return {
            page: { count: pageHistory.count || null },
            offset: (initialPagination.page - 1) * initialPagination.itemsPerPage,
            internalOffset: {},
            limit: initialPagination.itemsPerPage,
            pagination: { ...initialPagination },

            search: pageHistory.search ||
                (this.$route.query.user_id || '').replace(itemListSearchPrefix, ''),
            setOrgUnitSuccess: false,
            selected: [],

            syncLoading: false,

            sendingInvite: false,
            inviteSent: [],
            inviteSentDialog: false,

            moveToOrgUnit: null,

            filterDialog: false,
            filters: { ...initialFilters },
            activeFilters: { ...initialFilters },
            provider: {
                id: this.$route.query.provider ? parseInt(this.$route.query.provider) : 0,
                ...(pageHistory.provider || {})
            },

            error: null,
            bulkError: null,

            exportLoading: false,
            firstLoad: true,
        }
    },
    computed: {
        isPexip() {
            if (this.provider.id) {
                return this.provider.type === 'pexip'
            }

            return this.$store.state.site.isPexip
        },
        organizations() {
            return this.$store.getters['organization/all']
        },
        selectedOrganization() {
            return this.organizations.find(o => o.id === this.activeFilters.organizationUnit)
        },
        hasActiveFilter() {
            return Object.values(this.activeFilters).some(v => v !== null)
        },
        filterList() {
            if (!this.selectedOrganization) {
                return []
            }

            return [{
                title: 'OU',
                value: this.selectedOrganization.name
            }]
        },
        enableOrganization() {
            return this.$store.state.site.enableOrganization
        },
        multiTenant() {
            const customerId = this.customerId
            return this.users.some(user => user.tenant !== undefined && user.customerId !== customerId)
        },
        headers() {
            const headers = [
                { text: $gettext('Namn'), value: 'name' },
                { text: $gettext('E-post'), value: 'email' },
            ]
            if (this.customers.length > 1 && this.multiTenant) {
                headers.push({ text: this.$ngettext('Kund', 'Kunder', 1), value: 'customerName' })
            }
            return headers
        },
        users() {
            const tenantMap = {}
            const tenantProviderMap = {}
            const customerMap = this.$store.state.site.customers

            this.customers.forEach(c => {
                const tenantId = c.acano_tenant_id ? c.acano_tenant_id : c.pexip_tenant_id
                if (tenantId) {
                    tenantMap[tenantId] = c
                }
                else {
                    tenantProviderMap[c.provider] = c
                }
            })

            return (this.page.results || []).map(user => {
                const providerId = this.provider.id ? this.provider.id :
                    customerMap[this.customerId].provider

                const customer = !user.tenant
                    ? tenantProviderMap[providerId] || {}
                    : tenantMap[user.tenant] || {}

                return {
                    ...user,
                    isPexip: customer.type === 'pexip',
                    customerName: customer.title,
                    customerId: customer.id,
                }
            })
        },
        customers() {
            return Object.values(this.$store.state.site.customers)
        },
        customerId() {
            return this.$store.state.site.customerId
        },
    },
    watch: {
        exportLoading(newValue) {
            if (newValue) setTimeout(() => this.exportLoading = false, 10 * 1000)
        },
        pagination: {
            deep: true,
            handler() {
                if (!this.firstLoad) this.searchDebounce()
            }
        },
        'pagination.itemsPerPage': function(newValue) {
            this.limit = newValue
            if (!this.firstLoad) this.searchDebounce()
        },
        search() {
            if (!this.firstLoad) {
                this.searchDebounce(true)
            }
        },
    },
    mounted() {
        this.$nextTick(this.loadData)
    },
    methods: {
        setPage() {
            this.offset = (this.pagination.page - 1) * this.limit
            this.searchDebounce()
        },
        setProvider() {
            this.searchDebounce(true)
        },
        addOrgUnitQuery(id) {
            location.href = replaceQuery(null, { organization_unit: id })
        },
        resetFilters() {
            this.activeFilters = {}
            this.searchDebounce(true)
        },
        applyFilters() {
            this.filterDialog = false
            this.activeFilters = { ...this.filters }

            this.searchDebounce(true)
        },
        newSearch() {
            this.internalOffset = {}
            this.loadData()
        },
        // eslint-disable-next-line max-lines-per-function
        async loadData() {
            this.firstLoad = false

            const { search, limit, internalOffset } = this
            const { page } = this.pagination

            let offset = this.offset
            // For two step server side filter
            if (internalOffset[page]) offset = internalOffset[page]
            else if (internalOffset[page - 1]) offset = internalOffset[page - 1]

            this.setLoading(true)
            this.error = null

            if (this.provider.id) {
                this.activeFilters = {}
            }

            const response = await this.$store.dispatch('user/search', {
                search,
                offset,
                limit,
                organization_unit: this.activeFilters.organizationUnit || null,
                provider: this.provider.id || '',
            }).catch(e => {
                this.error = e
            })

            if (response && !response.offset) {
                this.internalOffset = {}
            } else if (response) {
                this.internalOffset = { ...this.internalOffset, [this.pagination.page + 1]: response.offset }
            }
            this.page = response || {}

            history.replaceState({
                ...history.state,
                page: {
                    count: this.page.count,
                    search,
                    filters: { ...this.activeFilters },
                    provider: { ...this.provider },
                    pagination: { ...this.pagination },
                }
            }, '')

            this.setLoading(false)
        },
        syncUsers() {
            this.syncLoading = true

            return this.$store.dispatch('user/sync', this.$store.state.site.providerId)
                .then(() => {
                    this.syncLoading = false
                })
                .catch(r => {
                    this.syncLoading = false
                    this.error = r
                })
        },
        async sendInvites() {
            this.sendingInvite = true
            this.inviteSent = []

            await Promise.all(this.selected.map(user => {
                return this.$store.dispatch('user/sendInvite', { userId: user.id }).then(r => {
                    this.inviteSent.push({...user, valid: true, email: r.email})
                }).catch(r => {
                    this.inviteSent.push({...user, valid:false, email: '', error: r.toString()})
                })
            }))

            this.sendingInvite = false
            this.inviteSentDialog = true
        },
        setOrgUnit() {
            this.bulkError = null
            return this.$store.dispatch('user/setOrganizationUnit', {
                unitId: this.moveToOrgUnit,
                userIds: this.selected.map(c => c.id),
            }).catch(e => {
                this.bulkError = e
            }).then(() => {
                this.setOrgUnitSuccess = true
                this.loadData()
            })
        },
    },
}
</script>

<style lang="scss">
.v-data-table.footer-left .v-data-footer {
    justify-content: start;
}
</style>
