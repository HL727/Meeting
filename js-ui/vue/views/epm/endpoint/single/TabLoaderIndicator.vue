<template>
    <div>
        <v-tabs
            :vertical="$vuetify.breakpoint.mdAndUp"
            background-color="grey lighten-4"
        >
            <v-tab
                class="justify-start"
                style="min-width: 160px;"
            >
                <translate>Laddar...</translate>
            </v-tab>
            <v-tab-item>
                <v-card flat>
                    <v-card-title>
                        <v-skeleton-loader
                            type="heading"
                            tile
                        />

                        <v-progress-linear
                            indeterminate
                            color="primary"
                        />
                    </v-card-title>
                    <v-card-text>
                        <v-skeleton-loader
                            min-height="800"
                            type="list-item@8"
                            tile
                        />
                    </v-card-text>
                </v-card>
            </v-tab-item>
        </v-tabs>
    </div>
</template>

<script>
export default {
    name: 'TabLoaderIndicator',
    props: {
        loading: Boolean,
    },
}
</script>
