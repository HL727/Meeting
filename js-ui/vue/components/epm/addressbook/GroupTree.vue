<template>
    <TreeView
        :items="items"
        item-text="title"
        :label="$gettext('Välj grupp')"
        v-bind="allProps"
        v-on="$listeners"
    >
        <template v-slot:action>
            <v-dialog :max-width="420">
                <template v-slot:activator="{ on }">
                    <v-btn
                        color="primary"
                        text
                        v-on="on"
                    >
                        <translate>Lägg till grupp</translate>
                    </v-btn>
                </template>
                <GroupForm
                    :groups="items"
                    :parent="items[0].id"
                />
            </v-dialog>
            <v-divider />
        </template>

        <template v-slot:append="{ item }">
            <span class="grey--text">{{ item.totalCount ? `(${item.totalCount})` : '' }}</span>

            <span @click.stop>
                <v-dialog :max-width="420">
                    <template v-slot:activator="{ on }">
                        <v-btn
                            icon
                            v-on="on"
                        ><v-icon>mdi-plus</v-icon></v-btn>
                    </template>
                    <GroupForm
                        :groups="items"
                        :parent="item.id"
                    />
                </v-dialog>
            </span>
        </template>
    </TreeView>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import TreeView from '@/vue/components/tree/TreeView'
import GroupForm from './GroupForm'

export default {
    components: { GroupForm, TreeView },
    inheritAttrs: false,
    props: {
        items: {
            type: Array,
            required: true,
            default: () => [],
        },
    },
    computed: {
        allProps() {
            return {
                ...this.$attrs,
                ...this.$props,
            }
        },
    },
    render(createElement) {
        const props = {
            items: this.items,
            itemText: 'name',
            label: $gettext('Välj grupp'),
        }
        return createElement(TreeView, { props, on: this.$listeners }, this.$children)
    },
}
</script>
