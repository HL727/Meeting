<template>
    <v-list
        style="z-index: 4;position:relative"
        class="mb-8"
    >
        <div
            v-for="item in items"
            :key="item.icon"
        >
            <v-list-item two-line>
                <v-icon class="mr-4">
                    {{ item.icon }}
                </v-icon>
                <v-list-item-title style="max-width: 12rem;">
                    {{ item.title }}
                </v-list-item-title>
                <div
                    v-for="total in item.totals"
                    :key="total.label"
                    class="d-flex align-self-stretch align-center"
                >
                    <div
                        class="mr-4"
                        style="min-width:3.5rem;"
                    >
                        <small>{{ total.label }}</small>
                        <h3>{{ total.value }}</h3>
                    </div>
                    <v-divider
                        vertical
                        class="mr-4"
                    />
                </div>
                <div class="d-none d-sm-flex">
                    <slot
                        name="item"
                        :item="{ ...item }"
                    />
                </div>
                <v-btn
                    v-if="item.to"
                    small
                    color="primary"
                    :to="item.to"
                    class="d-none d-sm-flex"
                >
                    <translate>Visa alla</translate>
                </v-btn>
                <v-btn
                    v-if="item.to"
                    small
                    fab
                    color="primary"
                    :to="item.to"
                    class="d-sm-none ml-auto"
                >
                    <v-icon>mdi-arrow-right</v-icon>
                </v-btn>
            </v-list-item>
            <v-divider />
        </div>
    </v-list>
</template>

<script>
export default {
    name: 'DashboardOverview',
    props: {
        items: { type: Array, default() { return [] } }
    }
}
</script>
