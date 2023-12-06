<template>
    <div>
        <EndpointGrid
            v-bind="$props"
            ref="grid"
            :value.sync="value"

            :endpoint-filtering="endpointFiltering"
            :endpoint-mapping="endpointMapping"

            v-on="$listeners"
        >
            <template v-slot:table="{ endpoints, loading, search }">
                <v-data-table
                    :class="{'footer-left': tableFooterLeft}"
                    :headers="peopleCountHeaders"
                    :items="endpoints"
                    :loading="loading"
                    :search="search"
                    :item-class="systemUsageClass"
                >
                    <template v-slot:item.title="{ item }">
                        <span class="d-flex align-center">
                            <v-icon class="mr-2">{{ item.status.type.icon }}</v-icon>
                            <span>
                                <a
                                    v-router-link="{ name: 'endpoint_details', params: { id: item.id } }"
                                    href="#"
                                >{{ item.title || '-- empty --' }}</a>
                                <small class="d-block">{{ item.product_name }}</small>
                            </span>
                        </span>
                    </template>
                </v-data-table>
            </template>
        </EndpointGrid>
    </div>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'
import { peopleStatusNames } from '@/vue/store/modules/endpoint/consts'

import EndpointGrid from '@/vue/components/epm/endpoint/EndpointGrid'

export default {
    components: { EndpointGrid },
    props: {
        checkbox: { type: Boolean, default: false },
        value: { type: Array, default: () => [] },
        single: { type: Boolean, default: false },
        showEmpty: { type: Boolean, default: undefined },
        hideSearch: Boolean,
        search: { type: String, required: false, default: '' },
        tableHeight: { type: Number, default: undefined },
        tableFooterLeft: { type: Boolean, default: false },
        onlyHeadCount: { type: Boolean, default: false },
    },
    data() {
        return {
            peopleCountHeaders: [
                {
                    text: $gettext('Namn'),
                    value: 'title',
                },
                { text: $gettext('Status'), value: 'status_title' },
                { text: $gettext('Personräknare'), value: 'head_count_title' },
            ],
            endpoints: [],
            statusInterval: null,
            totalRequests: 0,
            peopleStatusNames,
        }
    },
    computed: {
        endpointStatus() {
            return this.$store.state.stats.endpointStatus || {}
        },
    },
    mounted() {
        this.getEndpointStatus()
    },
    destroyed() {
        clearInterval(this.statusInterval)
    },
    methods: {
        reloadEndpoints() {
            if (this.$refs.grid) this.$refs.grid.reloadEndpoints()

            this.totalRequests = 0
            this.initStatusIntervall()
        },
        endpointFiltering(e) {
            return e.has_head_count
        },
        endpointMapping(e) {
            const status = this.endpointStatus[e.id] || {}
            let statusTypeKey = 'free'

            if (status.status === 0) {
                statusTypeKey = 'offline'
            }
            else if (status.status < 0) {
                statusTypeKey = 'err'
            }
            else if (status.active_meeting) {
                statusTypeKey = 'ghost'

                if (status.head_count) {
                    statusTypeKey = 'meeting_participants'
                }
            }
            else if (status.head_count) {
                statusTypeKey = 'occupied'
            }
            const statusType = { key: statusTypeKey, ...this.peopleStatusNames[statusTypeKey] }

            return {
                ...e,
                status: {
                    ...e.status,
                    ...status,
                    type: statusType,
                },
                status_title: statusType.title,
                head_count_title: (status.head_count || 0) + ' / ' + (e.room_capacity || '?')
            }
        },
        systemUsageClass(item) {
            if (!item.status || !item.status.type) return null
            return item.status.type.key
        },
        initStatusIntervall() {
            clearTimeout(this.statusInterval)
            this.statusInterval = setTimeout(() => {
                this.totalRequests += 1
                this.getEndpointStatus()
            }, 3000)
        },
        getEndpointStatus() {
            return this.$store.dispatch('stats/getEndpointStatuses')
                .then(() => {
                    if (this.totalRequests > 250) {
                        return false
                    }
                    this.initStatusIntervall()
                })
        },
    },
}
</script>

<style lang="scss">
tr.offline .v-icon              { opacity: 0.5 }
tr.offline td:first-child       { border-left: 8px solid #aaa; }

tr.err td:first-child           { border-left: 8px solid #888; }
tr.err .v-icon                  { color: #888; }

tr.ghost td:first-child          { border-left: 8px solid #d4d4d4; }
tr.ghost .v-icon                 { color: #d4d4d4; }

tr.free td:first-child          { border-left: 8px solid green; }
tr.free .v-icon                 { color: green; }

tr.meeting td:first-child       { border-left: 8px solid red; }
tr.meeting .v-icon              { color: red; }
tr.meeting_participants td:first-child { border-left: 8px solid red; }
tr.meeting_participants .v-icon        { color: red; }

tr.call td:first-child          { border-left: 8px solid orange; }
tr.call .v-icon                 { color: orange; }

tr.occupied td:first-child      { border-left: 8px solid blue; }
tr.occupied .v-icon             { color: blue; }

tr.ghost td:first-child         { border-left: 8px solid #ccc; }
tr.ghost .v-icon                { color: #ccc; }
</style>
