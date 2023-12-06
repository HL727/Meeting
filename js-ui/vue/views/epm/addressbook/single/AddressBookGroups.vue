<template>
    <div style="position: relative;">
        <v-progress-linear
            :active="loading"
            indeterminate
            absolute
            top
        />
        <TreeView
            v-model="selectedGroups"
            :search="searchGroup"
            item-text="title"
            :items="groupsWithoutRoot"
            :count-items="items"
            count-items-key="group"
            show-empty
            hoverable
            :hide-select="true"
            :search-attr="{outlined: true, dense: true, style: 'max-width:20rem'}"
            class="pt-5"
            style="max-width:50rem;margin:0 -16px;"
        >
            <template v-slot:prepend="{ item }">
                <span
                    class="mr-2 grey--text"
                    style="display:inline-block;"
                >{{ item.totalCount ? `(${item.totalCount})` : '(0)' }}</span>
            </template>

            <!-- TODO move functionality and use GroupTree -->
            <template v-slot:append="{ item }">
                <span @click.stop>
                    <v-dialog max-width="420">
                        <template v-slot:activator="{ on }">
                            <v-btn
                                icon
                                v-on="on"
                            ><v-icon>mdi-plus</v-icon></v-btn>
                        </template>
                        <GroupForm
                            :groups="groups"
                            :parent="item ? item.id : null"
                        />
                    </v-dialog>

                    <span v-if="item.is_editable">
                        <v-dialog max-width="420">
                            <template v-slot:activator="{ on }">
                                <v-btn
                                    icon
                                    v-on="on"
                                ><v-icon>mdi-pencil</v-icon></v-btn>
                            </template>
                            <GroupForm
                                :groups="groups"
                                :edit-id="item.id"
                            />
                        </v-dialog>

                        <v-btn
                            icon
                            @click="removeItem = item"
                        ><v-icon>mdi-delete</v-icon></v-btn>
                    </span>
                </span>
            </template>
        </TreeView>

        <v-dialog
            :value="!!removeItem"
            max-width="320"
            @input="removeItem = null"
        >
            <v-card>
                <v-card-title class="headline">
                    <translate>Säker på att ta bort?</translate>
                </v-card-title>
                <v-card-text v-if="removeItem">
                    <translate :translate-params="{group: removeItem.title}">
                        Är du säker på att du vill ta bort gruppen %{group}? Alla inlägg i denna grupp kommer då också att tas bort.
                    </translate>
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-btn
                        color="primary"
                        :loading="removeItemLoading"
                        dark
                        @click="removeGroup(removeItem)"
                    >
                        <translate>Ta bort</translate>
                    </v-btn>
                    <v-spacer />
                    <v-btn
                        v-close-dialog
                        text
                        color="red"
                        :disabled="removeItemLoading"
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
            v-model="addDialog"
            max-width="420"
        >
            <GroupForm
                :groups="groups"
                :parent="groups.length && groups[0].id"
            />
        </v-dialog>
    </div>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import TreeView from '@/vue/components/tree/TreeView'
import GroupForm from '@/vue/components/epm/addressbook/GroupForm'

import SingleAddressBookMixin from '@/vue/views/epm/mixins/SingleAddressBookMixin'

export default {
    components: {TreeView, GroupForm},
    mixins: [SingleAddressBookMixin],
    data() {
        return {
            emitter: new GlobalEventBus(this),
            searchGroup: '',
            selectedGroups: [],
            loading: false,
            addDialog: false,
            removeItem: null,
            removeItemLoading: false
        }
    },
    computed: {
        items() {
            return Object.values(this.$store.state.addressbook.items[this.id] || {})
                .filter(i => i.is_editable)
        },
        groups() {
            return (this.$store.getters['addressbook/groupTrees'][this.id] || [])
                .filter(g => g.is_editable)
                .map(g => ({
                    ...g,
                    title: `${g.title || '<Root>'} (${g.source || $gettext('External')})`,
                    is_editable: false,
                }))
        },
        groupsWithoutRoot() {
            return this.groups.length == 1 && this.groups[0].children.length ? this.groups[0].children : this.groups
        }
    },
    mounted() {
        this.emitter.on('refresh', () => this.loadData())
        this.emitter.on('add', () => (this.addDialog = true))

        this.loadData()
    },
    methods: {
        removeGroup(item) {
            this.removeItemLoading = true
            return this.$store.dispatch('addressbook/deleteGroup', { id: item.id, addressBookId: this.id }).then(() => {
                this.removeItem = null
                this.removeItemLoading = false
            })
        },
        loadData() {
            this.loading = true
            this.emitter.emit('loading', true)

            return this.$store
                .dispatch('addressbook/getAddressBookEditableItems', this.id)
                .then(() => {
                    this.loading = false
                    this.emitter.emit('loading', false)
                })
        },
    }
}
</script>
