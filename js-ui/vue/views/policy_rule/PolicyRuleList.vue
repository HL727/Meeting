<template>
    <Page
        icon="mdi-format-list-checks"
        :title="$gettext('Call routing-regler')"
        :actions="[
            { icon: 'mdi-plus', click: () => (addDialog = true) },
            {
                icon: 'mdi-swap-horizontal',
                loading: syncLoading,
                click: () => syncRules(),
                tooltip: $gettext('Hämta regler')
            },
            { type: 'refresh', click: () => loadData() }
        ]"
        :loading="loading"
    >
        <template v-slot:search>
            <VTextSearch
                v-model="search"
                :label="$gettext('Sök')"
            />
        </template>
        <template v-slot:filter>
            <VBtnFilterProvider
                v-model="provider"
                :loading="loading"
                :initial-cluster="provider"
                :title="$gettext('Visa regler för')"
                hide-customer
                only-clusters
                :provider-types="['pexip']"
                @filter="loadData"
            />
            <v-btn
                :disabled="loading"
                class="ml-4"
                color="primary"
                outlined
                small
                @click="rulesTestdialog = true"
            >
                <translate>Testa regler</translate>
            </v-btn>
        </template>
        <template v-slot:content>
            <ErrorMessage
                v-if="error"
                :error="error"
            />

            <v-data-table
                v-else
                :items="items"
                :search="search"
                :headers="headers"
                class="policy-rule-table"
                sort-by="priority"
            >
                <template v-slot:item.enable="{ item }">
                    <div class="d-flex">
                        <v-icon
                            class="mr-1"
                            :color="item.enable ? 'green' : 'red'"
                            v-text="item.enable ? 'mdi-check-circle' : 'mdi-cancel'"
                        />

                        <v-icon
                            class="mr-1"
                            :color="item.match_incoming_calls ? 'green' : 'blue-grey lighten-4'"
                        >
                            mdi-phone-incoming
                        </v-icon>
                        <v-icon :color="item.match_outgoing_calls ? 'green' : 'blue-grey lighten-4'">
                            mdi-phone-outgoing
                        </v-icon>
                    </div>
                </template>
                <template v-slot:item.priority="{ item }">
                    <v-avatar
                        left
                        class="blue-grey lighten-5"
                        size="32"
                    >
                        {{ item.priority }}
                    </v-avatar>
                </template>
                <template v-slot:item.name="{ item }">
                    <div class="py-3">
                        <v-tooltip bottom>
                            <template v-slot:activator="{ on, attrs }">
                                <router-link
                                    :to="{name: 'policy_rules_edit', params: { id: item.id }}"
                                    @click.native.prevent="editRule = item.id"
                                >
                                    <span
                                        v-bind="attrs"
                                        v-on="on"
                                    >
                                        {{ item.name }}
                                    </span>
                                </router-link>
                            </template>
                            {{ item.info_text || '-- no description --' }}
                        </v-tooltip>
                        <div class="mt-1">
                            <v-chip
                                class="mr-2"
                                :color="item.sync_back && item.in_sync ? 'green' : 'blue-grey lighten-3'"
                                text-color="white"
                                small
                            >
                                <v-avatar left>
                                    <v-icon>mdi-swap-horizontal</v-icon>
                                </v-avatar>                                <span
                                    v-if="item.sync_back && item.in_sync"
                                    v-translate
                                >Synk</span>
                                <span
                                    v-else-if="item.sync_back"
                                    v-translate
                                >Fel</span>
                                <span
                                    v-else-if="!item.sync_back && item.in_sync"
                                    v-translate
                                >Ändrad</span>
                                <span
                                    v-else-if="!item.sync_back"
                                    v-translate
                                >Lokal</span>
                            </v-chip>

                            <v-chip
                                v-if="item.called_device_type"
                                class="mr-2"
                                color="blue-grey lighten-1"
                                text-color="white"
                                small
                            >
                                <strong class="mr-1"><translate>Typ</translate>:</strong>
                                <span>{{ item.called_device_type }}</span>
                            </v-chip>
                            <v-chip
                                v-if="item.outgoing_protocol"
                                class="mr-2"
                                color="blue-grey lighten-2"
                                text-color="white"
                                small
                            >
                                <strong class="mr-1"><translate>Protokoll</translate>:</strong>
                                <span>{{ item.outgoing_protocol }}</span>
                            </v-chip>
                        </div>
                    </div>
                </template>
                <template v-slot:header.incoming_info>
                    <v-tooltip bottom>
                        <template v-slot:activator="{ on, attrs }">
                            <span
                                v-translate
                                v-bind="attrs"
                                v-on="on"
                            >Matcha inkommande</span>
                        </template>
                        R = Registered only<br>
                        W = WebRTC<br>
                        S = SIP<br>
                        L = Lync/Skype<br>
                        H = H323<br>
                    </v-tooltip>
                </template>

                <template v-slot:item.incoming_info="{ item }">
                    <v-avatar
                        class="white--text mr-1"
                        :class="item.match_incoming_calls && item.match_incoming_only_if_registered ? 'green' : 'blue-grey lighten-4'"
                        size="24"
                    >
                        <strong>R</strong>
                    </v-avatar>
                    <v-avatar
                        class="white--text mr-1"
                        :class="item.match_incoming_calls && item.match_incoming_webrtc ? 'green' : 'blue-grey lighten-4'"
                        size="24"
                    >
                        <strong>W</strong>
                    </v-avatar>
                    <v-avatar
                        class="white--text mr-1"
                        :class="item.match_incoming_calls && item.match_incoming_sip ? 'green' : 'blue-grey lighten-4'"
                        size="24"
                    >
                        <strong>S</strong>
                    </v-avatar>
                    <v-avatar
                        class="white--text mr-1"
                        :class="item.match_incoming_calls && item.match_incoming_mssip ? 'green' : 'blue-grey lighten-4'"
                        size="24"
                    >
                        <strong>L</strong>
                    </v-avatar>
                    <v-avatar
                        class="white--text mr-1"
                        :class="item.match_incoming_calls && item.match_incoming_h323 ? 'green' : 'blue-grey lighten-4'"
                        size="24"
                    >
                        <strong>H</strong>
                    </v-avatar>
                </template>

                <template v-slot:item.match="{ item }">
                    <v-tooltip bottom>
                        <template v-slot:activator="{ on, attrs }">
                            <span
                                v-bind="attrs"
                                v-on="on"
                            >{{ item.match_string.substr(0, 20) }}</span>
                        </template>
                        <translate>Match</translate>: {{ item.match_string }}
                        Replace: {{ item.replace_string }}
                    </v-tooltip>
                </template>

                <template v-slot:item.location="{ item }">
                    <div>
                        <v-icon :color="item.location_str ? 'green' : 'blue-grey lighten-4'">
                            mdi-arrow-left
                        </v-icon>
                        <span :class="item.location_str ? '' : 'blue-grey--text text--lighten-4'">
                            {{ item.location_str || $gettext('Ingen') }}
                        </span>
                    </div>
                    <div>
                        <v-icon
                            v-if="item.treat_as_trusted"
                            color="green lighten-2"
                        >
                            mdi-shield-check
                        </v-icon>
                        <v-icon
                            v-else
                            :color="item.outgoing_location_str ? 'green' : 'blue-grey lighten-4'"
                        >
                            mdi-arrow-right
                        </v-icon>
                        <span :class="item.outgoing_location_str ? '' : 'blue-grey--text text--lighten-4'">
                            {{ item.outgoing_location_str || $gettext('Ingen') }}
                        </span>
                    </div>
                </template>
            </v-data-table>


            <v-dialog
                v-model="addDialog"
                scrollable
                max-width="600"
                @input="copyRule && $router.replace({query: {copy: undefined}})"
            >
                <PolicyRuleForm
                    :provider="provider"
                    :initial-data="copyRule"
                />
            </v-dialog>

            <v-dialog
                :value="!!editRule"
                scrollable
                max-width="600"
                @input="editRule = null"
            >
                <PolicyRuleForm
                    :id="editRule"
                    :provider="provider"
                />
            </v-dialog>

            <v-dialog
                v-model="rulesTestdialog"
                scrollable
                max-width="600"
            >
                <PolicyRuleDebugForm
                    :rules="items"
                    :source-locations="{}"
                    :matching-mode="{}"
                    :provider="provider"
                    @update:editRule="editRule = $event"
                />
            </v-dialog>
        </template>
    </Page>
</template>

<script>
import { idMap } from '../../helpers/store'
import { $gettext } from '@/vue/helpers/translate'
import { setQuery } from '@/vue/helpers/url'

import Page from '@/vue/views/layout/Page'

import VTextSearch from '@/vue/components/VTextSearch'
import VBtnFilterProvider from '@/vue/components/filtering/VBtnFilterProvider'
import PolicyRuleForm from './PolicyRuleForm'
import PolicyRuleDebugForm from '../../components/policy_rules/PolicyRuleDebugForm'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

export default {
    components: { Page, VTextSearch, VBtnFilterProvider, PolicyRuleForm, PolicyRuleDebugForm, ErrorMessage },
    props: {
        id: { type: Number, default: null },
    },
    data() {
        return {
            search: '',
            addDialog: !!this.$route.query.copy,
            rulesTestdialog: false,
            editRule: this.id,
            syncLoading: false,
            selectedCluster: null,
            provider: this.$route.query.provider ? parseInt(this.$route.query.provider, 10) : undefined,
            loading: false,
            error: null,
        }
    },
    computed: {
        items() {
            const locations = idMap(this.$store.state.policy_rule.related.system_location || [])
            return Object.values(this.$store.state.policy_rule.rules || {}).map(l => {
                const locationNames = {
                    location_str: l.match_source_location && l.match_source_location in locations ? locations[l.match_source_location].name : '',
                    outgoing_location_str: l.outgoing_location && l.outgoing_location in locations ? locations[l.outgoing_location].name : '',
                }

                const info = []
                if (l.description) info.push(l.description + '. ')
                if (l.match_string) info.push('Match: ' + l.match_string)
                if (l.replace_string) info.push('(replace with ' + l.replace_string + ')')

                return {
                    ...l,
                    ...locationNames,
                    // for search:
                    info_text: info.join(''),
                    location: `${locationNames.location_str} ${locationNames.outgoing_location_str}`,
                    incoming_info: `${l.match_string} ${l.replace_string || ''} `,
                }
            })
        },
        headers() {
            const extra = []
            if (this.$vuetify.breakpoint.lgAndUp) {
                extra.push(
                    { value: 'hit_count_long', align: 'end', text: $gettext('6M') },
                )
            }
            return [
                { value: 'enable', text: $gettext('Aktiv'), width: 80 },
                { value: 'priority', text: $gettext('Prio'), width: 80 },
                { value: 'name', text: $gettext('Namn') },
                { value: 'incoming_info', text: $gettext('Matcha') },
                { value: 'location', text: $gettext('Location In/Ut') },
                { value: 'hit_count', align: 'end', text: $gettext('Träffar') },
                ...extra,
            ]
        },
        copyRule() {
            if (this.$route.query.copy) {
                return this.items.find(r => r.id.toString() == this.$route.query.copy)
            }
            return null
        },
        freePriorities() {
            const occupied = idMap(this.items.filter(r => r.external_id), 'priority')
            const free = []
            for (let i = 1; i <= 200; i++) {
                if (!occupied[i]) {
                    free.push(i)
                }
            }
            return free
        },
    },
    watch: {
        editRule(newValue) {
            if (!newValue && this.$route.name === 'policy_rules_edit') {
                this.$router.replace({ name: 'policy_rules', query: { provider: this.provider } })
            }

            // Ugly fix for setting pageLoading to false in PageHeader
            this.loading = true
            this.$nextTick(() => {
                this.loading = false
            })
        },
        provider(newValue) {
            const newUrl = setQuery(this.$route.fullPath, { provider: newValue }, true)
            this.$router.push(newUrl)
            this.loadData()
        },
        '$route.query.copy'(newValue) {
            if (newValue) {
                this.editRule = null
                this.addDialog = true
            }
        }
    },
    mounted() {
        this.loadData()
    },
    methods: {
        async syncRules() {
            this.syncLoading = true
            try {
                await this.$store.dispatch('policy_rule/syncRules', { provider: this.provider })
                this.error = null
            } catch (e) {
                this.error = e.toString()
            }
            this.syncLoading = false
        },
        loadData() {
            this.loading = true
            this.error = null

            Promise.all([
                this.$store.dispatch('policy_rule/getRules', { provider: this.provider }),
                this.$store.dispatch('policy_rule/getRelatedObjects', { provider: this.provider })
            ]).then(() => {
                this.loading = false
            })
                .catch(e => {
                    this.error = e
                    this.loading = false
                })
        }
    },
}
</script>
