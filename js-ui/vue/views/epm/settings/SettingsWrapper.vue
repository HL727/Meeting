<template>
    <Page
        icon="mdi-format-list-checks"
        :title="$gettext('Inställningar')"
        :actions="[{ type:'refresh', key: activeTab.url }]"
    >
        <template
            v-if="tabs.length > 1"
            v-slot:tabs
        >
            <v-tabs v-model="tab">
                <v-tab
                    v-for="tab in tabs"
                    :key="tab.url"
                    exact
                    :to="{ name: tab.url }"
                >
                    {{ tab.title }}
                </v-tab>
            </v-tabs>
        </template>
        <template v-slot:content>
            <router-view />
        </template>
    </Page>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

export default {
    components: { Page },
    data() {
        return {
            tab: this.$route.name,
            globalFilter: '',
            tabs: [
                {
                    url: 'epm_settings',
                    title: $gettext('Globala inställningar'),
                }
            ],
        }
    },
    computed: {
        activeTabs() {
            return this.tabs.map(tab => (tab.url === this.$route.name ? { ...tab, active: true } : tab))
        },
        activeTab() {
            return this.activeTabs.filter(tab => tab.active)[0] || {}
        },
    },
}
</script>
