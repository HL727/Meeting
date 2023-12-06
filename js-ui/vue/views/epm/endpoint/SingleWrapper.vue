<template>
    <Page
        icon="mdi-google-lens"
        :title="endpoint.title || endpoint.hostname || endpoint.ip"
        :actions="pageActions"
    >
        <template v-slot:tabs>
            <v-tabs
                v-model="tab"
                show-arrows
            >
                <v-tab
                    v-for="tab in activeTabs"
                    :key="tab.url"
                    :exact="!tab.notExact"
                    :to="{ name: tab.url, params: { id: id } }"
                >
                    {{ tab.title }}
                </v-tab>
            </v-tabs>
        </template>
        <template v-slot:content>
            <v-alert
                v-if="endpointNotFound"
                class="my-4"
                type="error"
            >
                <translate>Systemet hittades inte!</translate>
            </v-alert>
            <router-view />
        </template>
    </Page>
</template>

<script>
import { globalEmit } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import { EndpointManufacturer } from '@/vue/store/modules/endpoint/consts'

export default {
    components: { Page },
    mixins: [SingleEndpointMixin],
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            tab: this.$route.name,
            tabs: [
                {
                    url: 'endpoint_details',
                    title: $gettext('Start'),
                    edit: true,
                    delete: true,
                    refresh: true,
                    debug: true,
                },
                {
                    url: 'endpoint_status',
                    title: $gettext('Status'),
                    refresh: true
                },
                {
                    url: 'endpoint_configuration',
                    title: $gettext('Configuration'),
                    refresh: true
                },
                {
                    url: 'endpoint_commands',
                    title: $gettext('Commands'),
                    refresh: true,
                    hidden: endpoint => endpoint.manufacturer !== EndpointManufacturer.cisco,
                },
                {
                    url: 'endpoint_backup',
                    title: $gettext('Backups'),
                    add: true,
                    refresh: true
                },
                {
                    url: 'endpoint_tasks',
                    title: $gettext('Kö'),
                    refresh: true
                },
                {
                    url: 'endpoint_stats',
                    title: $gettext('Statistik'),
                    refresh: true,
                    notExact: true
                },
                {
                    url: 'endpoint_provision',
                    title: $gettext('Provisionera'),
                    refresh: true,
                },
            ],
        }
    },
    computed: {
        pageActions() {
            const actions = [
                {
                    icon: 'mdi-pencil',
                    hidden: !this.activeTab.edit,
                    click: () => globalEmit(this, 'edit')
                },
                {
                    icon: 'mdi-plus',
                    hidden: !this.activeTab.add,
                    click: () => globalEmit(this, 'add')
                },
                {
                    type: 'delete',
                    hidden: !this.activeTab.delete
                },
                {
                    type: 'debug',
                    hidden: !this.activeTab.debug || !this.$store.state.site.perms.admin,
                    click: () => this.$router.push({ name: 'endpoint_debug', params: { id: this.id } })
                },
                {
                    type: 'refresh',
                    hidden: !this.activeTab.refresh
                },
            ]

            if (this.endpoint && this.endpoint.status_code < 0) {
                actions.push({
                    type: 'alert',
                })
            }

            return actions
        },
        activeTabs() {
            const tabs = this.tabs.filter(tab => {
                if (tab.hidden && this.endpoint && tab.hidden(this.endpoint)) return false
                return true
            })
            return tabs.map(tab => (tab.url === this.$route.name ? { ...tab, active: true } : tab))
        },
        activeTab() {
            return this.activeTabs.filter(tab => tab.active)[0] || {}
        },
    },
    mounted() {
        this.$store.commit('endpoint/clearActiveConfiguration')
        this.$store.commit('endpoint/clearCommandQueue')
    }
}
</script>
