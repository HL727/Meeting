<template>
    <TreeView
        v-if="!loadingUnits"
        v-bind="allProps"
        ref="tree"
        :items="organizations"
        item-text="name"
        :label="$gettext('Sök organisationsenhet')"
        :search-attr="searchAttr"
        dense
        :duplicate-parents-as-nodes="duplicateParentsAsNodes"
        separator=" > "
        v-on="$listeners"
    >
        <template v-slot:header>
            <v-skeleton-loader
                v-if="loadingUnits"
                tile
                height="90"
                type="image"
                class="mb-0"
            />
            <v-alert
                v-else-if="!organizations.length"
                tile
                type="info"
                class="mb-0"
            >
                <translate>Hittade inga organisationsenheter</translate>
            </v-alert>

            <ErrorMessage :error="error" />
        </template>
        <template
            v-if="!hideAddNew"
            v-slot:action
        >
            <v-dialog :max-width="420">
                <template v-slot:activator="{ on }">
                    <v-card-text>
                        <v-btn
                            color="primary"
                            v-on="on"
                        >
                            <translate>Lägg till organisation</translate>
                        </v-btn>
                    </v-card-text>
                </template>
                <UnitForm />
            </v-dialog>
            <v-divider />
        </template>

        <template
            v-for="(_, name) in $scopedSlots"
            :slot="name"
            slot-scope="slotData"
        >
            <slot
                :name="name"
                v-bind="slotData"
            />
        </template>
        <template v-slot:append="{ item }">
            <span class="grey--text">{{ item.totalCount ? `(${item.totalCount})` : '' }}</span>

            <span
                :style="{ visibility: item.isParentDuplicate ? 'hidden': 'show'}"
                @click.stop
            >
                <v-dialog
                    v-if="!hideAddNew"
                    :max-width="420"
                >
                    <template v-slot:activator="{ on }">
                        <v-btn
                            icon
                            v-on="on"
                        ><v-icon>mdi-plus</v-icon></v-btn>
                    </template>
                    <UnitForm :parent="item.duplicatedRealId ? item.duplicatedRealId : item.id" />
                </v-dialog>

                <template v-if="enableEdit">
                    <v-dialog :max-width="420">
                        <template v-slot:activator="{ on }">
                            <v-btn
                                icon
                                v-on="on"
                            ><v-icon>mdi-pencil</v-icon></v-btn>
                        </template>
                        <UnitForm :edit-id="item.duplicatedRealId ? item.duplicatedRealId : item.id" />
                    </v-dialog>

                    <v-btn-confirm
                        icon
                        @click="removeUnit(item.duplicatedRealId ? item.duplicatedRealId : item.id)"
                    ><v-icon>mdi-delete</v-icon></v-btn-confirm>
                </template>
            </span>
        </template>
    </TreeView>
</template>

<script>
import TreeView from '@/vue/components/tree/TreeView'
import UnitForm from '@/vue/components/organization/UnitForm'
import VBtnConfirm from '@/vue/components/VBtnConfirm'
import { normalizeProps } from '@/vue/helpers/vue'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

export default {
    components: { ErrorMessage, VBtnConfirm, UnitForm, TreeView },
    inheritAttrs: false,
    props: {
        enableEdit: Boolean,
        single: { type: Boolean, default: false },
        hideAddNew: { type: Boolean, default: false },
        searchAttr: { type: Object, default: () => ({}) },
        forceLoad: { type: Boolean, default: false },
        showReload: { type: Boolean, default: false },
        openAll: { type: Boolean, default: false },
        duplicateParentsAsNodes: { type: [Boolean, String], required: false, default: false },
    },
    data() {
        return {
            loadingUnits: true,
            error: null,
        }
    },
    computed: {
        organizations() {
            return this.$store.getters['organization/tree']
        },
        allProps() {
            return {
                ...normalizeProps(this.$attrs),
                ...this.$props,
            }
        },
    },
    mounted() {
        this.loadData()
    },
    methods: {
        removeUnit(itemId) {
            return this.$store.dispatch('organization/deleteUnit', itemId)
        },
        loadData() {
            this.loadingUnits = true
            this.error = null
            return this.$store.dispatch(this.forceLoad ? 'organization/getUnits' : 'organization/refreshUnits')
                .then(() => {
                    this.loadingUnits = false
                    if (this.openAll) {
                        this.$nextTick(() => this.$refs.tree?.openAllNodes())
                    }
                    this.$emit('refreshed')
                }).catch(e => {
                    this.loadingUnits = false
                    this.error = e
                })
        }
    },
}
</script>
