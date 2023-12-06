<template>
    <Page
        icon="mdi-notebook-multiple"
        :title="$gettext('Adressböcker')"
        :actions="pageActions"
    >
        <template
            v-if="addressBooks.length > 0"
            v-slot:search
        >
            <v-form @submit.prevent="reloadAddressBooks()">
                <div class="d-flex align-center">
                    <v-text-field
                        v-model="search"
                        hide-details
                        prepend-inner-icon="mdi-magnify"
                        :placeholder="$gettext('Sök adressbok') + '...'"
                        outlined
                        dense
                        class="mr-4"
                    />
                    <v-btn
                        color="primary"
                        :loading="addressbooksLoading"
                        class="mr-md-4"
                        @click="reloadAddressBooks"
                    >
                        <v-icon>mdi-refresh</v-icon>
                    </v-btn>
                </div>
            </v-form>
        </template>
        <template
            v-if="addressBooks.length > 0"
            v-slot:filter
        >
            <VBtnFilter
                :disabled="addressbooksLoading"
                :filters="filterList"
                @click="filterDialog = true"
                @removeFilter="resetFilters"
            />
        </template>
        <template v-slot:content>
            <div v-if="addressBooks.length === 0 && addressbooksLoading">
                <v-progress-linear
                    indeterminate
                    color="primary"
                />
            </div>
            <div
                v-else-if="addressBooks.length === 0"
                max-width="420"
                class="my-10"
                style="max-width: 420px"
            >
                <p v-translate>
                    Lägg till din första adressbok
                </p>

                <v-card>
                    <v-card-text>
                        <AddressBookForm
                            ref="addFormFirst"
                            @complete="addAddressBookComplete"
                        />
                    </v-card-text>
                    <v-card-actions>
                        <v-btn
                            color="primary"
                            @click="$refs.addFormFirst.submit()"
                        >
                            <translate>Lägg till</translate>
                        </v-btn>
                    </v-card-actions>
                </v-card>
            </div>
            <div v-else>
                <v-data-table
                    :headers="headers"
                    :items="filteredAddressBooks"
                    :loading="addressbooksLoading"
                    :items-per-page.sync="pagination.itemsPerPage"
                    :page.sync="pagination.page"
                >
                    <template v-slot:top>
                        <v-dialog
                            :value="!!editAdressBookId"
                            max-width="420"
                            @input="editAdressBookId = null"
                        >
                            <v-card>
                                <v-card-title>
                                    <translate>Redigera adressbok</translate>
                                </v-card-title>
                                <v-divider />
                                <v-card-text>
                                    <AddressBookForm
                                        :id="editAdressBookId"
                                        ref="editForm"
                                        @complete="editAdressBookId = null"
                                    />
                                </v-card-text>
                                <v-divider />
                                <v-card-actions>
                                    <v-btn
                                        v-close-dialog
                                        color="primary"
                                        @click="$refs.editForm.submit()"
                                    >
                                        <translate>Spara</translate>
                                    </v-btn>
                                    <v-spacer />
                                    <v-btn
                                        v-close-dialog
                                        text
                                        color="red"
                                    >
                                        <translate>Avbryt</translate>
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
                    </template>

                    <template v-slot:item.title="{ item }">
                        <a
                            v-if="item.type === 1 && item.external_edit_url"
                            :href="item.external_edit_url"
                            target="_blank"
                        >{{ item.title }} (extern redigering)</a>
                        <router-link
                            v-else
                            :to="{ name: 'addressbook_details', params: { id: item.id } }"
                        >
                            {{ item.title }} <span
                                v-if="item.type === 1"
                                v-translate
                            >(extern)</span>
                        </router-link>
                    </template>
                    <template v-slot:item.action="{ item }">
                        <v-btn
                            icon
                            @click="editAdressBookId = item.id"
                        >
                            <v-icon>mdi-pencil</v-icon>
                        </v-btn>
                        <v-btn
                            icon
                            @click="copyAddressBook(item)"
                        >
                            <v-icon>mdi-content-copy</v-icon>
                        </v-btn>
                        <v-btn-confirm
                            icon
                            :dialog-text="$gettext(`Är du säker på att du vill ta bort adressboken?`) + ' (' + item.title + ')'"
                            @click="beforeDeleteAddressBook(item)"
                        >
                            <v-icon>mdi-delete</v-icon>
                        </v-btn-confirm>
                    </template>
                </v-data-table>
            </div>

            <v-dialog
                v-model="addDialog"
                max-width="290px"
            >
                <v-card>
                    <v-card-title>
                        <translate>Lägg till ny adressbok</translate>
                    </v-card-title>
                    <v-divider />
                    <v-card-text>
                        <AddressBookForm
                            ref="addForm"
                            @complete="addAddressBookComplete"
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-actions>
                        <v-btn
                            color="primary"
                            @click="$refs.addForm.submit()"
                        >
                            <translate>Lägg till</translate>
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
                v-model="filterDialog"
                scrollable
                max-width="320"
            >
                <v-card>
                    <v-card-title><translate>Filtrera</translate></v-card-title>
                    <v-divider />
                    <v-card-text>
                        <v-select
                            v-model="filters.type"
                            :placeholder="$gettext('Välj typ')"
                            :items="addressBookTypes"
                            item-text="label"
                            item-value="value"
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
                :value="deleteAddressBookItem !== null"
                max-width="290"
                @input="deleteAddressBookItem = null"
            >
                <v-card>
                    <v-card-title class="headline">
                        <translate>Säker på att ta bort?</translate>
                    </v-card-title>
                    <v-card-text>
                        <translate :translate-params="{count: linkedAddressBooks}">
                            Adressboken du försöker ta bort är länkad till %{count} andra adressböcker.
                        </translate>
                    </v-card-text>
                    <v-divider />
                    <v-card-actions>
                        <v-btn
                            color="primary"
                            dark
                            :loading="deleteAddressBookLoading"
                            @click="deleteAddressBook(deleteAddressBookItem)"
                        >
                            <translate>Ta bort</translate>
                        </v-btn>
                        <v-spacer />
                        <v-btn
                            v-close-dialog
                            text
                            color="red"
                        >
                            <translate>Avbryt</translate>
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
        </template>
    </Page>
</template>

<script>
import { globalEmit } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'

import AddressBookForm from '@/vue/components/epm/addressbook/AddressBookForm'
import VBtnConfirm from '@/vue/components/VBtnConfirm'
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'

import AddressBooksMixin from '@/vue/views/epm/mixins/AddressBooksMixin'

export default {
    components: { Page, VBtnConfirm, AddressBookForm, VBtnFilter },
    mixins: [AddressBooksMixin],
    // eslint-disable-next-line max-lines-per-function
    data() {
        const pageHistory = history.state?.page || {}
        const initialFilters = { type: -1, ...(pageHistory.filter || {}) }

        return {
            addDialog: false,
            editAdressBookId: false,
            selected: [],
            headers: [
                {
                    text: $gettext('Namn'),
                    value: 'title',
                },
                {
                    text: $gettext('Typ'),
                    value: 'type',
                },
                {
                    value: 'action',
                    align: 'end',
                    sortable: false,
                },
            ],
            search: pageHistory.search || '',
            pagination: {
                itemsPerPage: 10,
                page: 1,
                ...(pageHistory.pagination || {})
            },
            addressBookTypes: [
                {
                    label: $gettext('Alla'),
                    value: -1
                },
                {
                    label: $gettext('Manuell'),
                    value: 0
                },
                {
                    label: $gettext('Extern'),
                    value: 1
                }
            ],
            filterDialog: false,
            filters: { ...initialFilters },
            activeFilters: { ...initialFilters },
            deleteAddressBookItem: null,
            deleteAddressBookLoading: false,
            linkedAddressBooks: 0,
        }
    },
    computed: {
        pageActions() {
            return [
                {
                    icon: 'mdi-plus',
                    click: () => (this.addDialog = true)
                },
                {
                    type: 'refresh',
                    click: () => this.reloadAddressBooks()
                }
            ]
        },
        filterList() {
            if (this.activeFilters.type > -1) {
                return [{
                    title: $gettext('Typ'),
                    value: this.addressBookTypes.find(t => t.value === this.activeFilters.type).label
                }]
            }

            return []
        },
        filteredAddressBooks() {
            return this.addressBooks.filter(f => {
                if (this.activeFilters.type > -1) {
                    if (f.type !== this.activeFilters.type) {
                        return false
                    }
                }

                return JSON.stringify(f)
                    .toLowerCase()
                    .indexOf(this.search.toLowerCase()) !== -1
            }).map(f => {
                return {
                    ...f,
                    type: f.type === 0 ? $gettext('Manuell') : $gettext('Extern')
                }
            })
        }
    },
    watch: {
        search() {
            this.replaceHistroyState()
        },
        pagination: {
            deep: true,
            handler() {
                this.replaceHistroyState()
            }
        },
        filter: {
            deep: true,
            handler() {
                this.replaceHistroyState()
            }
        }
    },
    mounted() {
        this.$on('refreshed', () => {
            globalEmit(this, 'loading', false)
        })

        this.$store.commit('site/setBreadCrumb', [{ title: $gettext('Addressbok') }])
    },
    methods: {
        replaceHistroyState() {
            history.replaceState({
                ...history.state,
                page: {
                    search: this.search,
                    filter: { ...this.filter },
                    pagination: { ...this.pagination }
                }
            }, '')
        },
        resetFilters() {
            this.filters.type = -1
            this.applyFilters()
        },
        applyFilters() {
            this.activeFilters = { ...this.filters }
            this.filterDialog = false
        },
        addAddressBookComplete(book) {
            this.$router.push({ name: 'addressbook_edit', params: { id: book.id } })
        },
        copyAddressBook(book) {
            return this.$store
                .dispatch('addressbook/copyAddressBook', { addressBookId: book.id, form: {} })
                .then(book => this.addAddressBookComplete(book))
        },
        beforeDeleteAddressBook(book) {
            return this.$store.dispatch('addressbook/checkLinkedAddressbook', book.id).then(result => {
                if (result.length > 0) {
                    this.linkedAddressBooks = result.length
                    this.deleteAddressBookItem = book
                    return
                }

                this.deleteAddressBook(book)
            })
        },
        deleteAddressBook(book) {
            this.deleteAddressBookLoading = true
            return this.$store.dispatch('addressbook/deleteAddressBook', book.id).then(() => {
                this.deleteAddressBookLoading = false
                this.deleteAddressBookItem = null
                this.linkedAddressBooks = 0
                this.reloadAddressBooks()
            })
        },
    },
}
</script>
