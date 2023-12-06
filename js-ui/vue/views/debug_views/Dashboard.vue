<template>
    <Page icon="mdi-view-dashboard-outline">
        <template v-slot:title>
            <h1><translate>Debug dashboard</translate></h1>
        </template>
        <template v-slot:content>
            <v-row
                v-for="(debugViews, product) of items"
                :key="product"
                class="mt-4"
                style="max-width:70rem"
            >
                <v-col cols="12">
                    <h2>{{ productTitle[product] || product }}</h2>
                </v-col>
                <v-col
                    v-for="(item, debugView) in debugViews"
                    :key="debugView"
                    cols="6"
                    md="4"
                    lg="3"
                    class="d-flex"
                >
                    <v-hover>
                        <template v-slot="{ hover }">
                            <v-card
                                :class="`elevation-${hover ? 4 : 1}`"
                                class="transition-swing d-flex flex-column flex-grow-1"
                                :to="item.to ? item.to : { name: 'debug_api', params: { debugView: debugView } }"
                            >
                                <v-progress-linear
                                    color="lime"
                                    value="100"
                                />
                                <v-card-text>
                                    <h3 class="mb-4 grey--text text--darken-4">
                                        {{ item.title }}
                                    </h3>
                                    {{ item.description }}
                                </v-card-text>
                            </v-card>
                        </template>
                    </v-hover>
                </v-col>
            </v-row>
        </template>
    </Page>
</template>

<script>
import Page from '@/vue/views/layout/Page'
import { debugViewStructurePerProduct } from '@/vue/store/modules/debug_views/consts'

export default {
    components: { Page },
    data() {
        return {
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
    },
}
</script>
