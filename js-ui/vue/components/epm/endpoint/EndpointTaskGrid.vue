<template>
    <div>
        <PageSearchFilter :filter-style="filterStyle">
            <template v-slot:search>
                <v-form @submit.prevent="newSearch">
                    <div class="d-flex align-center">
                        <v-text-field
                            v-model="form.search"
                            hide-details
                            prepend-inner-icon="mdi-magnify"
                            :placeholder="$gettext('Sök system') + '...'"
                            outlined
                            dense
                            class="mr-4"
                        />
                        <v-btn
                            color="primary"
                            :loading="loading"
                            class="mr-md-4"
                            @click="newSearch"
                        >
                            <v-icon>mdi-refresh</v-icon>
                        </v-btn>
                    </div>
                </v-form>
            </template>
            <template v-slot:filter>
                <VBtnFilter
                    :filters="activeFilters"
                    :disabled="loading"
                    :show-remove-all="true"
                    @click="filterDialog = true"
                    @removeFilter="removeFilter($event)"
                    @removeAllFilters="removeAllFilters"
                />
            </template>
        </PageSearchFilter>

        <ErrorMessage :error="error" />

        <v-alert
            v-if="endpoint && endpoint.connection_type === 0"
            type="info"
        >
            <translate>Systemet använder passiv anslutning. Kön kommer att bearbetas nästa gång systemet kontaktar servern</translate>
            <br>
            <translate>Senaste kontakt</translate>:
            <span v-if="endpoint.status.ts_last_provision">
                {{ endpoint.status.ts_last_provision|since }}
            </span>
            <translate v-else>
                Aldrig
            </translate>
        </v-alert>

        <v-data-table
            :loading="loading"
            :items="filteredTasks"
            :headers="headers"
            :search="form.search"
            sort-by="id"
            sort-desc
        >
            <template v-slot:item.endpoint_title="{ item }">
                <span v-if="!item.endpoint">
                    {{ item.endpoint_title || '-- empty --' }}
                </span>
                <a
                    v-else
                    v-router-link="{ name: 'endpoint_details', params: { id: item.endpoint } }"
                    href="#"
                >{{
                    item.endpoint_title || '-- empty --'
                }}</a>
            </template>
            <template v-slot:item.status="{ item }">
                <template v-if="item.status == 10">
                    <v-icon>
                        mdi-check
                    </v-icon>
                    <v-tooltip
                        v-if="item.error"
                        bottom
                    >
                        <template v-slot:activator="{ on, attrs }">
                            <v-icon
                                v-bind="attrs"
                                v-on="on"
                            >
                                mdi-alert
                            </v-icon>
                        </template>
                        <pre style="overflow: auto;">{{ item.error || $gettext('Ett fel har uppstått, se informationsvyn för ytterligare detaljer') }}</pre>
                    </v-tooltip>
                </template>
                <template v-else>
                    <span
                        v-if="item.status >= 0 && item.status < 10"
                    >
                        <v-icon v-if="item.ts_schedule_attempt">mdi-clock</v-icon>
                        <v-progress-circular
                            v-else
                            indeterminate
                            size="20"
                            width="2"
                        />
                    </span>

                    <v-tooltip
                        v-if="item.tries > 0 || item.status < 0"
                        bottom
                    >
                        <template v-slot:activator="{ on, attrs }">
                            <span
                                v-bind="attrs"
                                v-on="on"
                            >
                                <span v-if="item.tries > 0">({{ item.tries }})</span>

                                <v-icon v-if="item.status == -1">mdi-cancel</v-icon>
                                <v-icon v-else-if="item.status == -10">mdi-alert</v-icon>
                            </span>
                        </template>
                        <pre style="overflow: auto;">{{ item.error || $gettext('Ett fel har uppstått, se informationsvyn för ytterligare detaljer') }}</pre>
                    </v-tooltip>
                </template>
            </template>
            <template v-slot:item.buttons="{ item }">
                <v-btn
                    v-if="item.status < 0 || item.status > 5"
                    icon
                    @click="retry(item)"
                >
                    <v-icon>mdi-refresh</v-icon>
                </v-btn>
                <v-btn
                    v-if="item.status >= 0 && item.status <= 5 && item.status != -1"
                    icon
                    @click="cancel(item)"
                >
                    <v-icon>mdi-cancel</v-icon>
                </v-btn>
                <v-btn
                    icon
                    @click="displayInfo(item)"
                >
                    <v-icon>mdi-information</v-icon>
                </v-btn>
            </template>
            <template v-slot:item.ts_created="{ item }">
                {{ item.ts_created|timestamp }}
            </template>
        </v-data-table>

        <v-dialog
            v-model="filterDialog"
            scrollable
            max-width="420"
        >
            <v-card>
                <v-card-title>
                    <translate>Filtrera</translate>
                </v-card-title>
                <v-divider />
                <v-card-text>
                    <v-select
                        v-model="filterForm.status"
                        :items="endpointTaskStatusChoices"
                        item-text="title"
                        item-value="id"
                        clearable
                        :label="$gettext('Status')"
                    />
                    <v-select
                        v-model="filterForm.action"
                        :items="endpointTaskTypeChoices"
                        item-text="title"
                        item-value="id"
                        clearable
                        :label="$gettext('Typ')"
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

        <v-dialog
            :value="!!info"
            scrollable
            :max-width="640"
            @input="info = null"
        >
            <v-card v-if="info">
                <v-card-title>
                    <translate>Detaljer</translate>
                </v-card-title>
                <v-divider />
                <v-card-text>
                    <v-simple-table
                        dense
                        class="mb-4"
                    >
                        <template v-slot:default>
                            <thead>
                                <tr>
                                    <th class="text-left">
                                        <translate>Typ</translate>
                                    </th>
                                    <th class="text-left">
                                        <translate>Skapad</translate>
                                    </th>
                                    <th class="text-left">
                                        <translate>Slutförd</translate>
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td><strong>{{ info.action }}</strong></td>
                                    <td>{{ info.ts_created|timestamp }}</td>
                                    <td>
                                        <span v-if="info.ts_completed">{{ info.ts_completed|timestamp }}</span>
                                        <span
                                            v-else
                                            class="red--text"
                                        ><translate>Inte klar</translate></span>
                                    </td>
                                </tr>
                            </tbody>
                        </template>
                    </v-simple-table>

                    <v-expansion-panels
                        :value="expandedInfo"
                        multiple
                    >
                        <v-expansion-panel v-if="info.error">
                            <v-expansion-panel-header><translate>Fellogg</translate></v-expansion-panel-header>
                            <v-expansion-panel-content>
                                <pre style="overflow: auto;">{{ info.error }}</pre>
                            </v-expansion-panel-content>
                        </v-expansion-panel>
                        <v-expansion-panel v-if="info.result">
                            <v-expansion-panel-header><translate>Resultat</translate></v-expansion-panel-header>
                            <v-expansion-panel-content>
                                <pre style="overflow: auto;">{{ info.result }}</pre>
                            </v-expansion-panel-content>
                        </v-expansion-panel>
                        <v-expansion-panel v-if="info.provision_content">
                            <v-expansion-panel-header><translate>Request</translate></v-expansion-panel-header>
                            <v-expansion-panel-content>
                                <pre style="overflow: auto;">{{ info.provision_content }}</pre>
                            </v-expansion-panel-content>
                        </v-expansion-panel>
                    </v-expansion-panels>
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
    </div>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'
import { endpointTaskTypeNames, endpointTaskTypeChoices, endpointTaskStatusNames, endpointTaskStatusChoices } from '@/vue/store/modules/endpoint/consts'

import ErrorMessage from '@/vue/components/base/ErrorMessage'
import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'
import {now} from '@/vue/helpers/datetime'

export default {
    name: 'EndpointTaskGrid',
    components: { ErrorMessage, PageSearchFilter, VBtnFilter },
    props: {
        endpointId: { type: Number, required: false, default: null },
        provisionId: { type: Number, required: false, default: null },
        changedSince: { type: Date, required: false, default: undefined },
        latest: { type: Boolean },
        hidden: { type: Boolean },
    },
    data() {
        return {
            endpointTaskTypeNames,
            endpointTaskTypeChoices,
            endpointTaskStatusNames,
            endpointTaskStatusChoices,
            loading: true,
            interval: null,
            headers: [
                { text: $gettext('Åtgärd'), value: 'provision' },
                { text: 'ID', value: 'id' },
                ...(this.endpointId ? [] : [{ text: $gettext('System'), value: 'endpoint_title' }]),
                { text: $gettext('Typ'), value: 'action_label' },
                { text: $gettext('Användare'), value: 'user' },
                { text: $gettext('Status'), value: 'status' },
                { text: $gettext('Skapades'), value: 'ts_created' },
                { text: '', value: 'buttons', align: 'end' },
            ],
            error: null,
            info: null,
            expandedInfo: [0],
            form: {
                search: null,
                status: null,
                action: null
            },
            filterDialog: false,
            lastLoaded: null,
            filterForm: {
                status: null,
                action: null
            },
            searchTimeout: null
        }
    },
    computed: {
        activeFilters() {
            const filters = []

            if (this.form.status !== null) {
                filters.push({
                    type: 'status',
                    title: $gettext('Status'),
                    value: this.endpointTaskStatusNames[this.form.status]
                })
            }
            if (this.form.action) {
                filters.push({
                    type: 'action',
                    title: $gettext('Typ'),
                    value: this.endpointTaskTypeNames[this.form.action]
                })
            }

            return filters
        },
        endpoint() {
            return this.$store.state.endpoint.endpoints[this.endpointId]
        },
        filters() {
            return {
                endpoint: this.endpointId || null,
                provision: this.provisionId || null,
                status: this.form.status !== null ? this.form.status : null,
                action: this.form.action || null
            }
        },
        filterStyle() {
            return this.$vuetify.breakpoint.mdAndUp ?
                { maxWidth: '75%', paddingLeft: '2rem' } : null
        },
        tasks() {
            return Object.values(this.$store.state.endpoint.tasks).map(t => {
                return {
                    ...t,
                    'action_label': endpointTaskTypeNames[t.action] || t.action
                }
            })
        },
        filteredTasks() {
            const tasks = this.tasks
            const filters = Object.entries(this.filters).filter(f => f[1] !== null)

            if (!filters.length) return tasks

            return tasks.filter(task => {
                return filters.every(f => task[f[0]] == f[1])
            })
        },
    },
    watch: {
        endpointId(newValue) {
            if (newValue && !this.loading) this.searchDebounce(true)
        },
        provisionId(newValue) {
            if (newValue && !this.loading) this.searchDebounce(true)
        },
        hidden(newValue) {
            if (!newValue) this.searchDebounce()
        },
        'form.search'() {
            this.searchDebounce()
        },
    },
    mounted() {
        this.loadData()

        // creation can be a bit delayed
        if (this.endpointId || this.provisionId) {
            setTimeout(() => {
                this.searchDebounce()
            }, 2000)
        }
        this.interval = setInterval(() => {
            this.searchDebounce()
        }, 15000)
    },
    destroyed() {
        clearInterval(this.interval)
    },
    methods: {
        newSearch() {
            this.lastLoaded = null
            return this.searchDebounce()
        },
        searchDebounce() {
            clearTimeout(this.searchTimeout)

            return new Promise(resolve => {
                this.searchTimeout = setTimeout(() => {
                    if (this.loading) {
                        resolve(this.searchDebounce())
                    }
                    else {
                        resolve(this.loadData())
                    }
                }, 300)
            })
        },
        applyFilters() {
            this.form = { ...this.form, ...this.filterForm }
            this.filterDialog = false
            return this.searchDebounce()
        },
        removeAllFilters() {
            this.filterForm.status = null
            this.filterForm.action = null
            this.applyFilters()
        },
        removeFilter({ filter }) {
            this.$set(this.filterForm, filter.type, null)
            this.applyFilters()
        },
        retry(task) {
            return this.$store.dispatch('endpoint/retryTask', task.id)
        },
        cancel(task) {
            return this.$store.dispatch('endpoint/cancelTask', task.id)
        },
        loadData(force=false) {
            if (this.hidden && !force) return
            this.loading = true
            this.$emit('loading')

            return this.$store.dispatch('endpoint/getTasks', {
                endpointId: this.endpointId,
                provisionId: this.provisionId,
                orderBy: this.latest ? 'change' : undefined,
                status: this.form.status !== null ? this.form.status : undefined,
                action: this.form.action,
                search: this.form.search,
                changedSince: this.status !== null ? null : this.lastLoaded,
            })
                .then(() => {
                    this.$emit('refreshed')
                    this.loading = false
                    this.error = null
                    this.lastLoaded = now()
                }).catch(e => {
                    this.$emit('refreshed')
                    this.loading = false
                    this.error = e
                })
        },
        displayInfo(item) {
            return this.$store.dispatch('endpoint/getTask', item.id).then(info => {
                this.expandedInfo = [0]
                this.info = info
            }).catch(e => this.error = e)
        }
    },
}
</script>
