<template>
    <Page
        icon="mdi-google-lens"
        :title="$gettext('System')"
        :actions="pageActions"
    >
        <template v-slot:tabs>
            <v-tabs
                v-model="tab"
                show-arrows
            >
                <v-tab
                    v-for="tab in tabs"
                    :key="tab.url"
                    exact
                    :class="$route.name === tab.url && 'v-tab--active'"
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
import { globalEmit } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

export default {
    components: { Page },
    data() {
        return {
            tab: this.$route.name,
            tabs: [
                {
                    url: 'epm_list',
                    title: $gettext('Sök'),
                },
                {
                    url: 'epm_task_list',
                    title: $gettext('Kö/historik'),
                },
                {
                    url: 'epm_incoming',
                    title: $gettext('Godkänn nya system'),
                },
            ],
        }
    },
    computed: {
        pageActions() {
            return [
                {
                    icon: 'mdi-plus',
                    hidden: (this.tab !== '/epm/endpoint/'),
                    click: () => globalEmit(this, 'add')
                },
                {
                    icon: 'mdi-layers-plus',
                    hidden: (this.tab !== '/epm/endpoint/'),
                    click: () => globalEmit(this, 'add-bulk')
                },
                {
                    type: 'refresh'
                }
            ]
        },
        activeTab() {
            return this.tabs.find(t => t.url === this.$route.name)
        },
    },
}
</script>
