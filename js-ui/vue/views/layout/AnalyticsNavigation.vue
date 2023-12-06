<template>
    <div>
        <v-list-item
            v-if="themes && themes.logo"
            :style="'height:64px;background:' + themes.logoBackground"
            class="justify-center"
        >
            <img
                :src="themes.logo"
                style="height:40px;max-width:220px;"
            >
        </v-list-item>
        <v-list-item
            v-else
            two-line
        >
            <v-list-item-content>
                <v-list-item-title><translate>Mividas</translate></v-list-item-title>
                <v-list-item-subtitle class="light-blue--text">
                    <translate>INSIGHT</translate>
                </v-list-item-subtitle>
            </v-list-item-content>
            <img
                :src="logo"
                alt=""
                width="40"
            >
        </v-list-item>
        <v-divider />

        <v-list
            dense
            class="py-0"
        >
            <v-list-item
                :to="{name:'analytics_dashboard'}"
                exact
            >
                <v-list-item-action>
                    <v-icon color="light-blue lighten-1">
                        mdi-view-dashboard-outline
                    </v-icon>
                </v-list-item-action>
                <v-list-item-content>
                    <v-list-item-title><translate>Dashboard</translate></v-list-item-title>
                </v-list-item-content>
            </v-list-item>
            <v-list-item :to="{name:'analytics_calls'}">
                <v-list-item-action>
                    <v-icon color="light-blue lighten-1">
                        mdi-chart-bar
                    </v-icon>
                </v-list-item-action>
                <v-list-item-content>
                    <v-list-item-title><translate>Samtalsstatistik</translate></v-list-item-title>
                </v-list-item-content>
            </v-list-item>
            <v-list-item to="/analytics/rooms/?">
                <v-list-item-action>
                    <v-icon color="light-blue lighten-1">
                        mdi-home-analytics
                    </v-icon>
                </v-list-item-action>
                <v-list-item-content>
                    <v-list-item-title><translate>Rumsanalys</translate></v-list-item-title>
                </v-list-item-content>
            </v-list-item>

            <template v-if="settings.perms.policy">
                <v-subheader><translate>Förbrukning</translate></v-subheader>
                <v-list-item to="/analytics/policy/report/?">
                    <v-list-item-action>
                        <v-icon color="light-blue lighten-1">
                            mdi-chart-line-stacked
                        </v-icon>
                    </v-list-item-action>
                    <v-list-item-content>
                        <v-list-item-title><translate>Överförbrukning</translate></v-list-item-title>
                    </v-list-item-content>
                </v-list-item>
                <v-list-item
                    to="/analytics/policy/?"
                    exact
                >
                    <v-list-item-action>
                        <v-icon color="light-blue lighten-1">
                            mdi-chart-multiline
                        </v-icon>
                    </v-list-item-action>
                    <v-list-item-content>
                        <v-list-item-title><translate>Livestatus</translate></v-list-item-title>
                    </v-list-item-content>
                </v-list-item>
            </template>
        </v-list>
    </div>
</template>

<script>
export default {
    name: 'AnalyticsNavigation',
    props: {
        themes: { type: Object, default() { return {} } },
    },
    data() {
        return {
            logo: require('@/assets/images/mividas-insight-logo.svg'),
        }
    },
    computed: {
        customers() {
            return Object.values(this.$store.state.site.customers || {})
        },
        settings() {
            return this.$store.getters['settings']
        },
    },
}
</script>
