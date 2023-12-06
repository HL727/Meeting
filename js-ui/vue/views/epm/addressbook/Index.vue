<template>
    <Page
        icon="mdi-notebook"
        :title="addressbook.title || addressbook.hostname || addressbook.ip"
        :actions="pageActions"
    >
        <template v-slot:tabs>
            <v-tabs v-model="tab">
                <v-tab
                    v-for="tab in activeTabs"
                    :key="tab.url"
                    exact
                    :to="{ name: tab.url, params: { id: id } }"
                >
                    {{ tab.title }}
                </v-tab>
            </v-tabs>
        </template>
        <template v-slot:content>
            <router-view v-if="addressbook.id" />

            <v-dialog
                v-model="infoDialog"
                scrollable
                max-width="420"
            >
                <v-card>
                    <v-card-title>
                        <translate>Sökuppgifter</translate>
                    </v-card-title>
                    <v-divider />
                    <v-card-text>
                        <v-text-field
                            :label="$gettext('Type')"
                            hide-details
                            value="TMS"
                            style="flex-basis:80px;"
                            class="mb-4"
                        />
                        <v-text-field
                            :label="$gettext('URL')"
                            hide-details
                            :value="addressbook.soap_search_url"
                            append-icon="mdi-content-copy"
                            @click:append="$refs.copySnackbar.copy(addressbook.soap_search_url)"
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

            <ClipboardSnackbar ref="copySnackbar" />
        </template>
    </Page>
</template>

<script>
import { globalEmit } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

import ClipboardSnackbar from '@/vue/components/ClipboardSnackbar'

import SingleAddressBookMixin from '@/vue/views/epm/mixins/SingleAddressBookMixin'

export default {
    components: { Page, ClipboardSnackbar },
    mixins: [SingleAddressBookMixin],
    data() {
        return {
            search: '',
            tab: this.$route.name,
            infoDialog: false,
            tabs: [
                {
                    url: 'addressbook_details',
                    title: $gettext('Innehåll'),
                    details: true,
                    download: true,
                    delete: true
                },
                {
                    url: 'addressbook_edit',
                    title: $gettext('Redigera'),
                    add: true,
                    addMultiple: true,
                    download: true,
                },
                {
                    url: 'addressbook_groups',
                    title: $gettext('Grupper'),
                    add: true,
                },
                {
                    url: 'addressbook_sources',
                    title: $gettext('Synkroniserade källor'),
                    add: true,
                },
            ],
        }
    },
    computed: {
        pageActions() {
            return [
                {
                    icon: 'mdi-plus',
                    hidden: !this.activeTab.add,
                    click: () => globalEmit(this, 'add')
                },
                {
                    icon: 'mdi-layers-plus',
                    hidden: !this.activeTab.addMultiple,
                    click: () => globalEmit(this, 'add-multiple')
                },
                {
                    icon: 'mdi-download',
                    hidden: !this.activeTab.download,
                    click: () => this.$store.dispatch('addressbook/export', this.addressbook.id)
                },
                {
                    type: 'info',
                    hidden: !this.activeTab.details,
                    click: () => (this.infoDialog = true)
                },
                {
                    type: 'delete',
                    hidden: !this.activeTab.delete
                },
                {
                    type: 'refresh',
                }
            ]
        },
        activeTabs() {
            return !this.addressbook.id ? this.tabs.slice(0, 1) : this.tabs
        },
        activeTab() {
            return this.tabs.find(t => t.url === this.$route.name)
        }
    },
}
</script>
