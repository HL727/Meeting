<template>
    <Page
        icon="mdi-door-closed"
        :title="$ngettext('Mötesrum', 'Mötesrum', 2)"
        :actions="pageActions"
    >
        <template
            v-if="!isPexip"
            v-slot:tabs
        >
            <CoSpacesTabs />
        </template>
        <template v-slot:search>
            <v-form @submit.prevent="searchDebounce(true)">
                <div class="d-flex align-center">
                    <v-text-field
                        v-model="search"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök mötesrum') + '...'"
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
                :title="$gettext('Visa mötesrum för')"
                :loading="loading"
                return-object
                only-clusters
                @filter="setProvider"
            />
            <VBtnFilter
                v-if="enableOrganization"
                :disabled="loading || !!provider.id"
                :filters="filterList"
                class="mx-4"
                @click="filterDialog = true"
                @removeFilter="removeFilter"
            />

            <form @submit="exportLoading = true">
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
                    name="type"
                    :value="activeFilters.type"
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
                    small
                    outlined
                    color="primary"
                    type="submit"
                    :disabled="loading || !!provider.id"
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
            <ErrorMessage :error="error" />
            <ErrorMessage
                :error="bulkError"
                :timeout="3000"
            />

            <v-data-table
                v-model="selected"
                :class="{'footer-left': selected.length}"
                :loading="loading"
                :items="cospaces"
                multiple
                :disable-sort="pagination.itemsPerPage !== -1"
                :options.sync="pagination"
                :headers="headers"
                :show-select="!provider.id"
                :server-items-length="pagination.itemsPerPage === -1 ? -1 : page.count || -1"
                @update:page="setPage"
            >
                <template v-slot:item.name="{ item }">
                    <router-link
                        :to="{
                            name: item.isPexip ? 'pexip_cospaces_details' : 'cospaces_details',
                            params: { id: item.id },
                            query: item.customerId ? { customer: item.customerId } : null
                        }"
                    >
                        {{ item.name || '-- empty --' }}
                    </router-link>
                </template>
                <template v-slot:item.actions="{ item }">
                    <v-btn
                        icon
                        @click="editId=item.id"
                    >
                        <v-icon>mdi-pencil</v-icon>
                    </v-btn>
                </template>
            </v-data-table>

            <TableActionDialog
                :count="selected.length"
                :title="$gettext('Val för samtliga valda mötesrum')"
            >
                <template v-if="provider.id === 0">
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
                            <p><i><translate>Fungerar endast för rum med e-postadress, alt. ha en användare som har e-postadress.</translate></i></p>
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

                <v-card
                    class="mb-4"
                    outlined
                >
                    <v-card-text>
                        <TenantPicker
                            v-model="moveToTenant"
                            :label="$gettext('Flytta till tenant')"
                            :tenant-field="isPexip ? 'pexip_tenant_id' : 'acano_tenant_id'"
                            :provider-id="providerId"
                            hide-details
                            clearable
                        />
                        <v-alert
                            v-model="setTenantSuccess"
                            dense
                            dismissible
                            type="success"
                        >
                            <translate>Flyttade</translate>
                        </v-alert>
                        <v-btn
                            :disabled="!moveToTenant"
                            depressed
                            small
                            color="primary"
                            class="mt-4 d-block"
                            @click="setCustomer"
                        >
                            <translate>Flytta</translate>
                        </v-btn>
                    </v-card-text>
                </v-card>
                <v-card
                    class="mb-4"
                    outlined
                >
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

                <v-card outlined>
                    <v-card-text>
                        <v-btn-confirm
                            color="error"
                            depressed
                            small
                            block
                            @click="remove"
                        >
                            <translate>Ta bort alla valda</translate>
                        </v-btn-confirm>
                    </v-card-text>
                </v-card>
            </TableActionDialog>

            <v-dialog
                v-model="addBulkDialog"
                scrollable
                :max-width="1500"
            >
                <PexipCoSpacesBulkForm
                    v-if="isPexip"
                    @complete="loadData"
                />
                <CoSpacesBulkForm
                    v-if="!isPexip"
                    @complete="loadData"
                />
            </v-dialog>

            <v-dialog
                v-model="addDialog"
                scrollable
                max-width="620"
            >
                <PexipCoSpacesForm
                    v-if="isPexip"
                    @created="loadData"
                    @useBulk="activateBulk"
                    @cancel="addDialog = false"
                />
                <CoSpaceForm
                    v-if="!isPexip"
                    @created="loadData"
                    @useBulk="activateBulk"
                    @cancel="addDialog = false"
                />
            </v-dialog>

            <v-dialog
                :value="!!editId"
                scrollable
                max-width="620"
                @input="editId = null"
            >
                <PexipCoSpacesForm
                    v-if="isPexip"
                    :id="editId"
                    @created="loadData"
                    @cancel="editId = null"
                />
                <CoSpaceForm
                    v-if="!isPexip"
                    :id="editId"
                    :button-text="$gettext('Uppdatera')"
                    @created="loadData"
                    @cancel="editId = null"
                />
            </v-dialog>

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
                                    Rum
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
                scrollable
                max-width="320"
            >
                <v-card>
                    <v-card-title><translate>Filtrera</translate></v-card-title>
                    <v-divider />
                    <v-card-text class="pt-4">
                        <p class="overline mb-0">
                            <translate>Organisationsenhet</translate>
                        </p>

                        <OrganizationPicker
                            v-model="filters.organizationUnit"
                            input-name="organization_unit"
                            :label="$gettext('Organisationsenhet')"
                        />

                        <template v-if="isPexip">
                            <p class="overline mb-0">
                                <translate>Mötestyp</translate>
                            </p>

                            <v-radio-group v-model="filters.type">
                                <v-radio
                                    :value="0"
                                    :label="$gettext('Alla')"
                                />
                                <v-radio
                                    v-for="(meetingLabel, meetingType) in pexipCospaceFilterTypes"
                                    :key="meetingType"
                                    :label="meetingLabel"
                                    :value="meetingType"
                                />
                            </v-radio-group>
                        </template>
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
import { pexipCospaceTypes, pexipCospaceFilterTypes } from '@/vue/store/modules/cospace/consts'

import Page from '@/vue/views/layout/Page'

import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'
import VBtnConfirm from '@/vue/components/VBtnConfirm'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'
import VBtnFilterProvider from '@/vue/components/filtering/VBtnFilterProvider'
import TableActionDialog from '@/vue/components/TableActionDialog'
import TenantPicker from '@/vue/components/tenant/TenantPicker'
import CoSpacesTabs from '@/vue/components/cospace/CoSpacesTabs'
import CoSpacesBulkForm from '@/vue/components/cospace/CoSpacesBulkForm'
import PexipCoSpacesBulkForm from '@/vue/components/cospace/PexipCoSpacesBulkForm'
import PexipCoSpacesForm from '@/vue/components/cospace/PexipCoSpacesForm'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import CoSpaceForm from '@/vue/components/cospace/CoSpaceForm'

import PageSearchMixin from '@/vue/views/mixins/PageSearchMixin'

export default {
    name: 'CoSpaceList',
    components: {
        Page,
        CoSpaceForm,
        ErrorMessage,
        CoSpacesTabs,
        TenantPicker,
        VBtnConfirm,
        VBtnFilter,
        VBtnFilterProvider,
        TableActionDialog,
        OrganizationPicker,
        CoSpacesBulkForm,
        PexipCoSpacesForm,
        PexipCoSpacesBulkForm,
    },
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
            type: 0,
            ...(pageHistory.filters || {})
        }

        return {
            pexipCospaceFilterTypes,
            page: { count: pageHistory.count || null },
            internalOffset: {},
            pagination: { ...initialPagination },
            search: pageHistory.search ||
                (this.$route.query.cospace_id || '').replace(itemListSearchPrefix, ''),
            selected: [],
            sendingInvite: false,
            inviteSent: [],
            inviteSentDialog: false,
            bulk: false,
            moveToTenant: undefined,
            setTenantSuccess: false,
            moveToOrgUnit: null,
            setOrgUnitSuccess: false,
            addDialog: false,
            addBulkDialog: false,
            editId: null,
            bulkError: null,
            filterDialog: false,
            filters: { ...initialFilters },
            activeFilters: { ...initialFilters },
            provider: {
                id: this.$route.query.provider ? parseInt(this.$route.query.provider) : 0,
                ...(pageHistory.provider || {})
            },
            error: null,
            exportLoading: false,
            firstLoad: false,
        }
    },
    computed: {
        pageActions() {
            return [
                {
                    icon: 'mdi-plus',
                    click: () => this.activateSingle(),
                    disabled: !!this.provider.id
                },
                {
                    icon: 'mdi-layers-plus',
                    click: () => this.activateBulk(),
                    disabled: !!this.provider.id
                },
                {
                    type: 'refresh',
                    click: () => this.searchDebounce()
                }
            ]
        },
        filterList() {
            const filtering = []

            if (this.selectedOrganization) {
                filtering.push({
                    title: 'OU',
                    key: 'organizationUnit',
                    value: this.selectedOrganization.name
                })
            }

            if (this.activeFilters.type) {
                filtering.push({
                    title: $gettext('Typ'),
                    key: 'type',
                    value: this.pexipCospaceFilterTypes[this.activeFilters.type]
                })
            }

            return filtering
        },
        organizations() {
            return this.$store.getters['organization/all']
        },
        selectedOrganization() {
            return this.organizations.find(o => o.id === this.activeFilters.organizationUnit)
        },
        isPexip() {
            if (this.provider.id) {
                return this.provider.type === 'pexip'
            }

            return this.$store.state.site.isPexip
        },
        enableOrganization() {
            return this.$store.state.site.enableOrganization
        },
        cospaces() {
            const tenantMap = {}
            const tenantProviderMap = {}

            this.customers.forEach(c => {
                const tenantId = c.acano_tenant_id ? c.acano_tenant_id : c.pexip_tenant_id
                if (tenantId) {
                    tenantMap[tenantId] = c
                }
                else {
                    tenantProviderMap[c.provider] = c
                }
            })

            return (this.page.results || []).map(cospace => {
                const serviceTypeLabel = this.isPexip ? (pexipCospaceTypes[cospace.service_type] || cospace.service_type)  : ''
                if (cospace.tenant === undefined) {
                    return { ...cospace, isPexip: this.isPexip, serviceTypeLabel }
                }

                const customer = !cospace.tenant
                    ? tenantProviderMap[this.provider.id] || {}
                    : tenantMap[cospace.tenant] || {}

                return {
                    ...cospace,
                    isPexip: customer.type === 'pexip',
                    customerName: customer.title,
                    customerId: customer.id,
                    serviceTypeLabel
                }
            })
        },
        customerId() {
            return this.$store.state.site.customerId
        },
        providerId() {
            return this.$store.state.site.providerId
        },
        customers() {
            return Object.values(this.$store.state.site.customers)
        },
        multiTenant() {
            const customerId = this.customerId
            return this.cospaces.some(cospace => cospace.customerId && cospace.customerId !== customerId)
        },
        headers() {
            const headers = [
                { text: $gettext('Namn'), value: 'name' },
                { text: $gettext('URI'), value: 'uri' },
                { text: $gettext('Call ID'), value: 'call_id' },
            ]

            if (this.customers.length > 1 && this.multiTenant) {
                headers.push({ text: this.$ngettext('Kund', 'Kunder', 1), value: 'customerName' })
            }

            if (this.isPexip) {
                headers.push({ text: $gettext('Typ'), value: 'serviceTypeLabel' })
            }

            if (this.$vuetify.breakpoint.mdAndUp) {
                headers.push({ text: '', value: 'actions', align: 'end' })
            }

            return headers
        }
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
        'pagination.itemsPerPage': function() {
            if (this.firstLoad) this.searchDebounce()
        },
        search() {
            if (this.firstLoad) {
                this.searchDebounce(true)
            }
        },
    },
    mounted() {
        this.$nextTick(() => {
            // fix for not having watch values trigger new searches before first load
            this.firstLoad = true

            this.loadData()
        })
    },
    methods: {
        setPage() {
            this.searchDebounce()
        },
        setProvider() {
            this.searchDebounce(true)
        },
        addOrgUnitQuery(id) {
            location.href = replaceQuery(null, { organization_unit: id })
        },
        removeFilter({ filter }) {
            this.filters[filter.key] = null

            this.applyFilters()
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
            this.setLoading(true)
            this.error = null
            this.addDialog = false
            this.editId = null

            const { search, internalOffset } = this
            const { page } = this.pagination

            let offset = (this.pagination.page - 1) * this.pagination.itemsPerPage
            // For two step server side filter
            if (internalOffset[page]) offset = internalOffset[page]
            else if (internalOffset[page - 1]) offset = internalOffset[page - 1]

            if (this.provider.id) {
                this.activeFilters = {}
            }

            const response = await this.$store.dispatch('cospace/search', {
                search,
                offset,
                limit: this.pagination.itemsPerPage,
                organization_unit: this.activeFilters.organizationUnit || null,
                provider: this.provider.id || '',
                type: this.activeFilters.type || ''
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
        setOrgUnit() {
            this.bulkError = null
            this.setOrgUnitSuccess = false
            return this.$store.dispatch('cospace/setOrganizationUnit', {
                unitId: this.moveToOrgUnit,
                cospaceIds: this.selected.map(c => c.id),
            }).catch(e => {
                this.bulkError = e
            }).then(() => {
                this.setOrgUnitSuccess = true
                this.loadData()
            })
        },
        setCustomer() {
            this.bulkError = null
            this.setTenantSuccess = false
            return this.$store.dispatch('cospace/setCustomer', {
                tenantId: this.moveToTenant,
                cospaceIds: this.selected.map(c => c.id),
            }).catch(e => {
                this.bulkError = e
            }).then(() => {
                this.setTenantSuccess = true
                this.loadData()
            })
        },
        async sendInvites() {
            this.sendingInvite = true
            this.bulkError = null
            this.inviteSent = []

            await Promise.all(this.selected.map(cospace => {
                return this.$store.dispatch('cospace/sendInvite', { cospaceId: cospace.id }).then(r => {
                    this.inviteSent.push({...cospace, valid: true, email: r.email})
                }).catch(r => {
                    this.inviteSent.push({...cospace, valid:false, error: r})
                    this.bulkError = r
                })
            }))

            this.sendingInvite = false
            this.inviteSentDialog = true
        },
        remove() {
            this.error = null
            this.$store.dispatch(
                'cospace/remove',
                this.selected.map(c => c.id)
            ).then(() => {
                this.loadData()
                this.selected = []
            }).catch(e => {
                this.loadData()
                this.error = e.errors || e.error
                this.selected = []
            })
        },
        activateBulk() {
            this.addDialog = false
            this.addBulkDialog = true
        },
        activateSingle() {
            this.addBulkDialog = false
            this.addDialog = true
        },
    },
}
</script>

<style lang="scss">
.v-data-table.footer-left .v-data-footer {
    justify-content: start;
}
</style>
