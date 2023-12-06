<template>
    <v-expansion-panels
        v-if="groups"
        v-model="selectedTarget"
        accordion
        flat
        focusable
    >
        <v-expansion-panel style="overflow: hidden;">
            <v-expansion-panel-header>
                <v-chip
                    class="flex-grow-0 mr-3 px-2"
                    :color="selectedTarget === 0 && groups.organizations.length > 0 ? 'primary' : ''"
                >
                    <v-icon size="16">
                        {{ selectedTarget === 0 && groups.organizations.length > 0 ? 'mdi-check' : 'mdi-minus' }}
                    </v-icon>
                </v-chip>
                <translate>Per organisation</translate>
            </v-expansion-panel-header>
            <v-expansion-panel-content
                class="panel-tree-view-content"
            >
                <OrganizationTree
                    v-model="groups.organizations"
                    hide-toggle-empty
                    hide-actions
                    hide-add-new
                    :count-items="endpoints"
                    count-items-key="org_unit"
                    :show-empty="showEmpty"
                    duplicate-parents-as-nodes
                    :single="false"
                />
            </v-expansion-panel-content>
            <v-divider />
        </v-expansion-panel>

        <!-- dont mix v-if below, messes with v-model value orders -->
        <template v-if="endpoints.length">
            <v-expansion-panel style="overflow: hidden;">
                <v-expansion-panel-header>
                    <v-chip
                        class="flex-grow-0 mr-3 px-2"
                        :color="selectedTarget === 1 && groups.locations.length > 0 ? 'primary' : ''"
                    >
                        <v-icon size="16">
                            {{ selectedTarget === 1 && groups.locations.length > 0 ? 'mdi-check' : 'mdi-minus' }}
                        </v-icon>
                    </v-chip>
                    <translate>Per plats</translate>
                </v-expansion-panel-header>
                <v-expansion-panel-content
                    class="panel-tree-view-content"
                >
                    <TreeView
                        v-model="groups.locations"
                        hide-search
                        :items="objectFilters.location"
                        :count-items="endpoints"
                        count-items-key="location"
                        :show-empty="showEmpty"
                        aheight="tableHeight"
                    />
                </v-expansion-panel-content>
                <v-divider />
            </v-expansion-panel>
            <v-expansion-panel style="overflow: hidden;">
                <v-expansion-panel-header>
                    <v-chip
                        class="flex-grow-0 mr-3 px-2"
                        :color="selectedTarget === 2 && groups.models.length > 0 ? 'primary' : ''"
                    >
                        <v-icon size="16">
                            {{ selectedTarget === 2 && groups.models.length > 0 ? 'mdi-check' : 'mdi-minus' }}
                        </v-icon>
                    </v-chip>
                    <translate>Per modell</translate>
                </v-expansion-panel-header>
                <v-expansion-panel-content
                    class="panel-tree-view-content"
                >
                    <TreeView
                        v-model="groups.models"
                        hide-search
                        :items="objectFilters.product_name"
                        :count-items="endpoints"
                        count-items-key="product_name"
                        :show-empty="showEmpty"
                        aheight="tableHeight"
                    />
                </v-expansion-panel-content>
                <v-divider />
            </v-expansion-panel>
            <v-expansion-panel style="overflow: hidden;">
                <v-expansion-panel-header>
                    <v-chip
                        class="flex-grow-0 mr-3 px-2"
                        :color="selectedTarget === 3 && groups.status_code.length > 0 ? 'primary' : ''"
                    >
                        <v-icon size="16">
                            {{ selectedTarget === 3 && groups.status_code.length > 0 ? 'mdi-check' : 'mdi-minus' }}
                        </v-icon>
                    </v-chip>
                    <translate>Per status</translate>
                </v-expansion-panel-header>
                <v-expansion-panel-content
                    class="panel-tree-view-content"
                >
                    <TreeView
                        v-model="groups.status_code"
                        hide-search
                        :items="endpointStatusChoices"
                        :count-items="endpoints"
                        count-items-key="status_code"
                        :show-empty="showEmpty"
                        aheight="tableHeight"
                    />
                </v-expansion-panel-content>
                <v-divider />
            </v-expansion-panel>
            <v-expansion-panel style="overflow: hidden;">
                <v-expansion-panel-header>
                    <v-chip
                        class="flex-grow-0 mr-3 px-2"
                        :color="selectedTarget === 4 && groups.connection_type.length > 0 ? 'primary' : ''"
                    >
                        <v-icon size="16">
                            {{ selectedTarget === 4 && groups.connection_type.length > 0 ? 'mdi-check' : 'mdi-minus' }}
                        </v-icon>
                    </v-chip>
                    <translate>Per anslutning</translate>
                </v-expansion-panel-header>
                <v-expansion-panel-content
                    class="panel-tree-view-content"
                >
                    <TreeView
                        v-model="groups.connection_type"
                        hide-search
                        :items="endpointConnectionTypeChoices"
                        :count-items="endpoints"
                        count-items-key="connection_type"
                        :show-empty="showEmpty"
                        duplicate-parents-as-nodes
                        aheight="tableHeight"
                    />
                </v-expansion-panel-content>
            </v-expansion-panel>
        </template>
    </v-expansion-panels>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'
import { endpointConnectionTypeChoices, endpointStatusChoices } from '@/vue/store/modules/endpoint/consts'

import TreeView from '@/vue/components/tree/TreeView'
import OrganizationTree from '@/vue/components/organization/OrganizationTree'

export default {
    components: {
        TreeView,
        OrganizationTree,
    },
    props: {
        value: { type: Object, default: () => ({}) },
        target: { type: Number, default: null },

        endpoints: { type: Array, default: () => [] },
        showEmpty: { type: Boolean, default: false },
        availableFilters: { type: Object, default: () => ({}) },

        disabled: { type: Boolean, default: false },
    },
    data() {
        return {
            endpointStatusChoices,
            endpointConnectionTypeChoices,

            groups: this.value
        }
    },
    computed: {
        selectedTarget: {
            get() {
                return this.target
            },
            set(value) {
                this.$emit('update:target', value)
            }
        },
        objectFilters() {
            const filters = this.availableFilters || {}
            return {
                ...filters,
                location: (filters.location || []).map(l => ({id: l, title: l || $gettext('<Okänd tillhörighet>')})),
                product_name: (filters.product_name || []).map(p => ({id: p, title: p || $gettext('<Okänd tillhörighet>')})),
            }
        },
    },
    watch: {
        value: {
            deep: true,
            handler(newSelection) {
                this.groups = newSelection
            }
        },
        groups: {
            deep: true,
            handler(newSelection) {
                this.$emit('input', newSelection)

                if (!this.disabled) {
                    this.$emit('change')
                }
            }
        }
    }
}
</script>

<style lang="scss">
.panel-tree-view-content {
    padding: 0;
    overflow: auto;
    max-height: 450px;

    > .v-expansion-panel-content__wrap {
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
}
</style>
