<template>
    <div>
        <v-list-item two-line>
            <v-list-item-content>
                <v-list-item-title><translate>Mividas</translate></v-list-item-title>
                <v-list-item-subtitle class="lime--text">
                    <translate>DEBUG</translate>
                </v-list-item-subtitle>
            </v-list-item-content>
            <v-avatar color="grey darken-4">
                <v-icon color="lime">
                    mdi-bug
                </v-icon>
            </v-avatar>
        </v-list-item>
        <v-divider />

        <v-list
            dense
            class="py-0"
        >
            <v-list-item
                :to="{ name: 'debug_dashboard' }"
                :exact="true"
            >
                <v-list-item-action>
                    <v-icon color="lime">
                        mdi-view-dashboard-outline
                    </v-icon>
                </v-list-item-action>
                <v-list-item-content>
                    <v-list-item-title><translate>Dashboard</translate></v-list-item-title>
                </v-list-item-content>
            </v-list-item>

            <div
                v-for="(debugViews, product) of items"
                :key="product"
            >
                <v-subheader>{{ productTitle[product] || product }}</v-subheader>
                <v-list-item
                    v-for="(item, debugView) in debugViews"
                    :key="debugView"
                    :to="item.to ? item.to : { name: 'debug_api', params: { debugView: debugView } }"
                    :exact="true"
                >
                    <v-list-item-action>
                        <v-icon color="lime">
                            mdi-chevron-right
                        </v-icon>
                    </v-list-item-action>
                    <v-list-item-content>
                        <v-list-item-title>{{ item.title }}</v-list-item-title>
                    </v-list-item-content>
                </v-list-item>
            </div>
        </v-list>
    </div>
</template>

<script>
import { debugViewStructurePerProduct } from '@/vue/store/modules/debug_views/consts'

export default {
    name: 'DebugViewsNavigation',
    data() {
        return {
            logo: require('@/assets/images/mividas-debug-logo.svg'),
            debugViewStructure: debugViewStructurePerProduct(this.$store.state.site),
            productTitle: {
                core: 'Mividas Core',
                epm: 'Mividas Rooms',
                shared: this.$gettext('Övriga loggar'),
            }
        }
    },
    computed: {
        items() {
            return debugViewStructurePerProduct(this.$store.state.site)
        },
        customers() {
            return Object.values(this.$store.state.site.customers || {})
        },
    },
}
</script>
