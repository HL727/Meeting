<template>
    <div>
        <v-data-table
            :headers="headers"
            :loading="loading"
            :items="sources"
        >
            <template v-slot:item.last_sync="{ item }">
                <v-tooltip
                    v-if="item.sync_errors"
                    bottom
                    max-width="600"
                >
                    <template v-slot:activator="{ on }">
                        <v-icon v-on="on">
                            mdi-alert
                        </v-icon>
                    </template>
                    <div>{{ item.sync_errors }}</div>
                </v-tooltip>
                <span v-if="item.last_sync">{{ item.last_sync|timestamp }}</span>
            </template>
            <template v-slot:item.action="{ item }">
                <v-btn-confirm
                    icon
                    @click="deleteSource(item)"
                >
                    <v-icon>mdi-delete</v-icon>
                </v-btn-confirm>
            </template>
        </v-data-table>

        <v-dialog
            v-model="addDialog"
            scrollable
            max-width="420"
        >
            <v-card @keydown.enter="delaySubmit">
                <v-card-title>
                    <translate>Lägg till extern källa</translate>
                </v-card-title>
                <v-divider />
                <v-card-text>
                    <v-text-field
                        v-model="form.title"
                        :label="$gettext('Beskrivning')"
                    />
                    <OrganizationPicker
                        :text-path.sync="form.prefix"
                        persistent-hint
                        :label="$gettext('Lägg till i undergrupp')"
                        :hint="$gettext('Grupper/mappstruktur och poster kommer synkroniseras till denna mapp. Lämna tomt för att synkronisera till huvudnivå. Separera flera nivåer med >')"
                    />

                    <v-card class="mt-4">
                        <v-card-text>
                            <v-select
                                v-model="tab"
                                outlined
                                :items="tabItems"
                                item-value="index"
                                item-text="label"
                            />

                            <v-tabs-items v-model="tab">
                                <v-tab-item key="epm">
                                    <v-container
                                        style="max-height: 300px;"
                                        class="overflow-y-auto"
                                    >
                                        <translate>Synkronisera enbart system och trädstruktur som ligger under denna del av trädet</translate>:
                                        <OrganizationPicker
                                            v-model="form.epm.org_unit"
                                            single
                                            :label="$gettext('Välj ev. del av trädet att filtrera')"
                                        />
                                        <v-checkbox
                                            v-model="form.epm.flatten"
                                            :label="$gettext('Slå ihop undermappar')"
                                        />
                                        <v-checkbox
                                            v-model="form.epm.ignore_hide_status"
                                            :label="$gettext('Inkludera även dolda system')"
                                        />
                                    </v-container>
                                </v-tab-item>

                                <v-tab-item key="tms">
                                    <v-text-field
                                        v-model="form.tms.phonebook_url"
                                        :label="$gettext('URL till PhonebookSearch')"
                                        hint="Ex. https://example.org/tms/public/external/phonebook/phonebookservice.asmx?op=Search"
                                    />
                                    <v-text-field
                                        v-model="form.tms.mac"
                                        :label="$gettext('MAC-adress för identifiering')"
                                    />
                                </v-tab-item>
                                <v-tab-item key="manual_link">
                                    <v-select
                                        v-model="form.manual_link.manual_source"
                                        :label="$gettext('Länka till annan adressbok')"
                                        item-value="id"
                                        item-text="title"
                                        :items="providers.manual"
                                    />

                                    <translate>Redigerbara poster kommer synkroniseras</translate>
                                </v-tab-item>

                                <v-tab-item
                                    v-if="providers.cms && providers.cms.length"
                                    key="cms_user"
                                >
                                    <v-select
                                        v-model="form.cms_user.provider"
                                        :label="$gettext('CMS-server')"
                                        item-value="id"
                                        item-text="title"
                                        :items="providers.cms"
                                    />
                                </v-tab-item>

                                <v-tab-item
                                    v-if="providers.cms && providers.cms.length"
                                    key="cms_spaces"
                                >
                                    <v-select
                                        v-model="form.cms_spaces.provider"
                                        :label="$gettext('CMS-server')"
                                        item-value="id"
                                        item-text="title"
                                        :items="providers.cms"
                                    />
                                </v-tab-item>

                                <v-tab-item
                                    v-if="providers.vcs && providers.vcs.length"
                                    key="vcs"
                                >
                                    <v-select
                                        v-model="form.vcs.provider"
                                        :label="$gettext('VCS-server')"
                                        item-value="id"
                                        item-text="title"
                                        :items="providers.vcs"
                                    />
                                    <v-combobox
                                        :label="$gettext('Begränsa till domäner')"
                                        :hint="$gettext('Tabb-separerad')"
                                        multiple
                                        chips
                                        @change="form.vcs.limit_domains = $event.join(',')"
                                    />
                                </v-tab-item>
                            </v-tabs-items>
                        </v-card-text>
                    </v-card>
                </v-card-text>
                <v-divider />
                <v-alert
                    v-if="error"
                    type="error"
                    tile
                >
                    {{ error }}
                </v-alert>
                <v-card-actions>
                    <v-btn
                        type="submit"
                        color="primary"
                        :loading="formLoading"
                        @click="delaySubmit"
                    >
                        <translate>Lägg till</translate>
                    </v-btn>
                    <v-spacer />
                    <v-btn
                        color="red"
                        text
                        @click="addDialog = false"
                    >
                        <translate>Avbryt</translate>
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import VBtnConfirm from '@/vue/components/VBtnConfirm'
import OrganizationPicker from '@/vue/components/organization/OrganizationPicker'

import SingleAddressBookMixin from '@/vue/views/epm/mixins/SingleAddressBookMixin'

export default {
    components: { VBtnConfirm, OrganizationPicker },
    mixins: [SingleAddressBookMixin],
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            emitter: new GlobalEventBus(this),
            addDialog: false,
            tab: 0,
            error: '',
            formLoading: false,
            loading: false,
            headers: [
                {
                    text: $gettext('Beskrivning'),
                    value: 'title',
                },
                {
                    text: $gettext('Undergrupp'),
                    value: 'prefix',
                },
                {
                    text: $gettext('Senast synkroniserad'),
                    value: 'last_sync',
                },
                {
                    text: $gettext('Typ av källa'),
                    value: 'type',
                },
                {
                    text: '',
                    value: 'action',
                },
            ],

            form: {
                title: '',
                prefix: '',
                epm: {
                    org_unit: null,
                    flatten: false,
                    ignore_hide_status: false,
                },
                cms_user: {
                    provider: null,
                },
                cms_spaces: {
                    provider: null,
                },
                vcs: {
                    provider: null,
                },
                tms: {
                    mac: '',
                    phonebook_url: '',
                },
                manual_link: {
                    manual_source: null,
                },
            },
        }
    },
    computed: {
        tabItems() {
            let index = 0
            const items = [
                { index: index++, key: 'epm', label: $gettext('Hanterade videokonferenssystem') },
                { index: index++, key: 'tms', label: $gettext('TMS') },
                { index: index++, key: 'manual_link', label: $gettext('Kopia manuella inlägg från adressbok') },
            ]

            if (this.providers.cms && this.providers.cms.length) {
                items.push({ index: index++, key: 'cms_user', label: $gettext('CMS-användare') })
                items.push({ index: index++, key: 'cms_spaces', label: $gettext('CMS videorum') })
            }
            if (this.providers.vcs && this.providers.vcs.length) {
                items.push({ index: index++, key: 'vcs', label: $gettext('VCS') })
            }

            return items
        },
        sources() {

            const manual = Object.values(this.$store.state.addressbook.sources[this.id] || {}).filter(s => s.type == 'Manual')

            let result = Object.values(this.$store.state.addressbook.sources[this.id] || {})
            if (manual.length <= 1) {
                result = result.filter(s => s.type !== 'Manual')
            }

            return result.map(s =>
                s.title
                    ? s
                    : {
                        ...s,
                        title: '<no name>',
                    }
            )
        },
        providers() {
            return this.$store.state.addressbook.providers || {}
        },
    },
    mounted() {
        this.emitter.on('add', () => (this.addDialog = true))
        this.emitter.on('refresh', () => this.loadData())

        return this.loadData()
    },
    methods: {
        delaySubmit() {
            // make sure comboboxes are saved
            return new Promise(resolve => setTimeout(() => resolve(this.add()), 100))
        },
        add() {
            const tabKey = this.tabItems[this.tab].key
            this.formLoading = true
            this.$store
                .dispatch('addressbook/addSource', {
                    addressBookId: this.id,
                    form: {
                        title: this.form.title,
                        prefix: this.form.prefix,
                        type: tabKey,
                        ...this.form[tabKey],
                    },
                })
                .then(() => {
                    this.addDialog = false
                    this.error = ''
                    this.formLoading = false
                }).catch(e => {
                    this.error = (e.errors ? JSON.stringify(e.errors) : e).toString()
                    this.formLoading = false
                })
        },
        deleteSource(item) {
            return this.$store.dispatch('addressbook/deleteSource', { addressBookId: this.id, sourceId: item.id })
        },
        loadData() {
            this.loading = true
            this.emitter.emit('loading', true)

            return this.$store.dispatch('addressbook/getProviders').then(() => {
                this.loading = false
                this.emitter.emit('loading', false)

                if (this.providers.cms.length == 1) this.form.cms_user.provider = this.providers.cms[0].id
                if (this.providers.cms.length == 1) this.form.cms_spaces.provider = this.providers.cms[0].id
                if (this.providers.vcs.length == 1) this.form.vcs.provider = this.providers.vcs[0].id
            })
        }
    }
}
</script>
