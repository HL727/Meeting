<template>
    <div>
        <PageSearchFilter>
            <template slot="search">
                <v-text-field
                    v-model="search"
                    hide-details
                    prepend-inner-icon="mdi-magnify"
                    :placeholder="$gettext('Sök inlägg') + '...'"
                    outlined
                    dense
                />
            </template>
            <template slot="filter">
                <VBtnFilter
                    class="d-xl-none"
                    :disabled="loading"
                    :filters="filters"
                    :text="$gettext('Filtrera på grupp')"
                    icon="mdi-select-group"
                    @click="filterDialog = true"
                    @removeFilter="removeFilter"
                />
                <v-btn
                    :to="{ name: 'addressbook_groups', params: { id: id } }"
                    color="primary"
                    small
                    outlined
                    class="ml-2"
                >
                    <v-icon
                        left
                        dark
                    >
                        mdi-pencil
                    </v-icon>
                    <translate>Redigera grupper</translate>
                </v-btn>
            </template>
        </PageSearchFilter>

        <v-row>
            <v-col
                cols="3"
                class="d-none d-xl-block"
            >
                <p class="overline mb-0">
                    <translate>Filter</translate>
                </p>

                <TreeView
                    v-model="selectedGroups"
                    :items="groups"
                    :label="$gettext('Sök grupp')"
                    :count-items="items"
                    count-items-key="group"
                    duplicate-parents-as-nodes
                    style="margin-left: -16px;"
                />
            </v-col>
            <v-col
                cols="12"
                xl="9"
            >
                <v-data-table
                    :search="search"
                    :headers="headers"
                    :loading="loading"
                    :items="filteredItems"
                >
                    <template v-slot:item.action="{ item }">
                        <v-btn
                            icon
                            @click="editItemId = item.id"
                        >
                            <v-icon>mdi-pencil</v-icon>
                        </v-btn>
                        <v-btn-confirm
                            icon
                            @click="removeItem(item)"
                        >
                            <v-icon>mdi-delete</v-icon>
                        </v-btn-confirm>
                    </template>
                </v-data-table>
            </v-col>
        </v-row>

        <v-dialog
            :value="!!editItemId"
            scrollable
            :max-width="420"
            @input="editItemId = null"
        >
            <ItemForm
                :groups="groups"
                :edit-id="editItemId"
            />
        </v-dialog>

        <v-dialog
            v-model="addDialog"
            scrollable
            :max-width="420"
        >
            <ItemForm :groups="groups" />
        </v-dialog>

        <v-dialog
            v-model="addBulkDialog"
            scrollable
            :max-width="1500"
        >
            <ItemBulkForm
                v-if="addBulkDialog"
                :groups="groups"
                :address-book-id="id"
            />
        </v-dialog>

        <v-dialog
            v-model="filterDialog"
            scrollable
            max-width="420"
        >
            <v-card>
                <v-card-title><translate>Filtrera på grupp</translate></v-card-title>
                <v-divider />
                <v-card-text>
                    <TreeView
                        v-model="activeFilters.selectedGroups"
                        :items="groups"
                        :label="$gettext('Sök grupp')"
                        :count-items="items"
                        count-items-key="group"
                        duplicate-parents-as-nodes
                        style="margin:0 -24px;"
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
    </div>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'

import ItemForm from '@/vue/components/epm/addressbook/ItemForm'
import ItemBulkForm from '@/vue/components/epm/addressbook/ItemBulkForm'
import TreeView from '@/vue/components/tree/TreeView'
import VBtnConfirm from '@/vue/components/VBtnConfirm'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'

import SingleAddressBookMixin from '@/vue/views/epm/mixins/SingleAddressBookMixin'

export default {
    components: {
        TreeView,
        ItemForm,
        VBtnFilter,
        ItemBulkForm,
        VBtnConfirm,
        PageSearchFilter,
    },
    mixins: [SingleAddressBookMixin],
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            emitter: new GlobalEventBus(this),
            addDialog: false,
            addBulkDialog: false,
            editItemId: null,

            searchGroup: '',
            loading: false,
            selectedGroups: [],
            activeFilters: {
                selectedGroups: []
            },
            search: '',
            filterDialog: false,
            headers: [
                {
                    text: $gettext('Rubrik'),
                    value: 'title',
                },
                {
                    text: $gettext('Grupp'),
                    value: 'group_title',
                },
                {
                    text: $gettext('SIP'),
                    value: 'sip',
                },
                {
                    text: $gettext('H323'),
                    value: 'h323',
                },
                {
                    text: '',
                    value: 'action',
                    align: 'end',
                },
            ],
        }
    },
    computed: {
        filters() {
            return this.selectedGroups.map(g => {
                let groupInfo = this.groups.find(group => group.id === g)

                function findGroup(root, id) {
                    const stack = []
                    let node
                    let ii

                    stack.push(root)

                    while (stack.length > 0) {
                        node = stack.pop()
                        //console.log(node.id, id) // eslint-disable-line
                        if (node.id === id) {
                            return node
                        } else if (node.children && node.children.length) {
                            for (ii = 0; ii < node.children.length; ii += 1) {
                                stack.push(node.children[ii])
                            }
                        }
                    }

                    return null
                }

                if (!groupInfo) {
                    groupInfo = findGroup({id: -1, children: this.groups}, g)
                }

                return {
                    id: groupInfo.id,
                    title: $gettext('Grupp'),
                    value: groupInfo.title
                }
            })
        },
        groupsMapped() {
            return this.$store.state.addressbook.groups[this.id]
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
        items() {
            return Object.values(this.$store.state.addressbook.items[this.id] || {}).filter(
                i => i.is_editable
            ).map(item => {
                return {
                    ...item,
                    group_title: (item.group in this.groupsMapped) ? this.groupsMapped[item.group].title : ''
                }
            })
        },
        filteredItems() {
            let items = this.items

            if (this.selectedGroups.length) {
                items = items.filter(i => this.selectedGroups.includes(i.group))
            }

            if (this.search) {
                items = items.filter(f => {
                    return JSON.stringify(f)
                        .toLowerCase()
                        .indexOf(this.search.toLowerCase()) != -1
                })
            }

            return items
        },
    },
    mounted() {
        this.emitter.on('add', () => this.addSingle())
        this.emitter.on('add-multiple', () => this.addBulk())
        this.emitter.on('refresh', () => this.loadData())

        this.loadData()
    },
    methods: {
        removeFilter({ filter }) {
            this.$delete(this.activeFilters.selectedGroups,
                this.activeFilters.selectedGroups.indexOf(filter.id))

            this.applyFilters()
        },
        applyFilters() {
            this.selectedGroups = [...this.activeFilters.selectedGroups]
            this.filterDialog = false
        },
        removeItem(item) {
            return this.$store.dispatch('addressbook/deleteItem', { id: item.id, addressBookId: this.id })
        },
        addBulk() {
            this.addDialog = false
            this.addBulkDialog = true
        },
        addSingle() {
            this.addBulkDialog = false
            this.addDialog = true
        },
        loadData() {
            this.loading = true
            this.emitter.emit('loading', true)

            return this.$store
                .dispatch('addressbook/getAddressBookEditableItems', this.id)
                .then(() => {
                    this.emitter.emit('loading', false)
                    this.loading = false
                })
        }
    }
}
</script>
