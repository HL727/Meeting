<template>
    <div>
        <v-list-item
            v-if="theme.logo"
            style="height:64px;"
            :class="{'justify-center': true, 'grey lighten-4 elevation-5': !theme.darkMode}"
        >
            <img
                :src="theme.logo"
                style="height:40px;max-width:220px;"
            >
        </v-list-item>
        <v-list-item
            v-else
            two-line
        >
            <v-list-item-content>
                <v-list-item-title><translate>Mividas</translate></v-list-item-title>
                <v-list-item-subtitle class="orange--text text--lighten-1">
                    <translate>CORE</translate>
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
            <v-list-item v-if="customers.length > 1">
                <v-list-item-content>
                    <CustomerPicker
                        prepend-icon="mdi-domain"
                        navigate
                        dense
                        flat
                        solo
                        :outlined="false"
                        :hide-details="true"
                        :settings-link="settings.perms.admin"
                    />
                </v-list-item-content>
            </v-list-item>
            <v-divider v-if="customers.length > 1" />

            <v-list-item
                to="/?"
                exact
            >
                <v-list-item-action>
                    <v-icon color="orange lighten-1">
                        mdi-view-dashboard-outline
                    </v-icon>
                </v-list-item-action>
                <v-list-item-content>
                    <v-list-item-title><translate>Dashboard</translate></v-list-item-title>
                </v-list-item-content>
            </v-list-item>

            <template v-if="settings.hasCoreProvider">
                <v-list-item to="/users/?">
                    <v-list-item-action>
                        <v-icon color="orange lighten-1">
                            mdi-account-multiple
                        </v-icon>
                    </v-list-item-action>
                    <v-list-item-content>
                        <v-list-item-title><translate>Användare</translate></v-list-item-title>
                    </v-list-item-content>
                </v-list-item>

                <v-list-item to="/cospaces/?">
                    <v-list-item-action>
                        <v-icon color="orange lighten-1">
                            mdi-door-closed
                        </v-icon>
                    </v-list-item-action>
                    <v-list-item-content>
                        <v-list-item-title>{{ $ngettext('Mötesrum', 'Mötesrum', 2) }}</v-list-item-title>
                    </v-list-item-content>
                </v-list-item>

                <v-list-item to="/calls/?">
                    <v-list-item-action>
                        <v-icon color="orange lighten-1">
                            mdi-google-classroom
                        </v-icon>
                    </v-list-item-action>
                    <v-list-item-content>
                        <v-list-item-title><translate>Möten</translate></v-list-item-title>
                    </v-list-item-content>
                </v-list-item>

                <v-list-item to="/meeting/?">
                    <v-list-item-action>
                        <v-icon color="orange lighten-1">
                            mdi-calendar
                        </v-icon>
                    </v-list-item-action>
                    <v-list-item-content>
                        <v-list-item-title><translate>Bokade möten</translate></v-list-item-title>
                    </v-list-item-content>
                </v-list-item>

                <v-list-item to="/stats/?">
                    <v-list-item-action>
                        <v-icon color="orange lighten-1">
                            mdi-chart-bar
                        </v-icon>
                    </v-list-item-action>
                    <v-list-item-content>
                        <v-list-item-title><translate>Samtalsstatistik</translate></v-list-item-title>
                    </v-list-item-content>
                </v-list-item>
            </template>

            <v-divider />

            <v-expansion-panels
                flat
                tile
                active-class="grey darken-4"
                :value="adminRoute ? 0 : null"
            >
                <v-expansion-panel class="transparent">
                    <v-expansion-panel-header class="pa-0 pr-3">
                        <v-list-item>
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-settings
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Admin</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                    </v-expansion-panel-header>
                    <v-expansion-panel-content class="grey darken-4 expansion-panel-menu">
                        <v-divider />

                        <v-list-item to="/core/admin/messages/?">
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-email-box
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Meddelandetexter</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item
                            v-if="settings.perms.api"
                            :to="{ name: 'rest_client' }"
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-package-variant-closed
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>API-klient</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item
                            v-if="settings.perms.staff && customers.length > 1"
                            :to="{ name: 'customer_dashboard' }"
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-domain
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Kunder</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item
                            v-if="settings.perms.staff"
                            :to="{ name: 'provider_dashboard' }"
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-server-network
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Videomötesbryggor</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item
                            v-if="settings.enableBranding"
                            :to="{ name: 'settings' }"
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-brush
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Temainställningar</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item
                            v-if="settings.enableDemo"
                            :to="{ name: 'demo_generator' }"
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-table-row-plus-after
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Demo generator</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item
                            v-if="settings.perms.admin"
                            href="/admin/"
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-cogs
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Backend admin</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                    </v-expansion-panel-content>
                </v-expansion-panel>
            </v-expansion-panels>
        </v-list>
    </div>
</template>

<script>
import CustomerPicker from '@/vue/components/tenant/CustomerPicker'
export default {
    name: 'CoreNavigation',
    components: { CustomerPicker },
    props: {
        themes: { type: Object, default() { return {} } },
    },
    data() {
        return {
            logo: require('@/assets/images/mividas-core-logo.svg'),
        }
    },
    computed: {
        customers() {
            return Object.values(this.$store.state.site.customers || {})
        },
        theme() {
            return this.$store.state.theme.theme
        },
        settings() {
            return this.$store.getters['settings']
        },
        adminRoute() {
            return this.$route.fullPath.indexOf('/core/admin') !== -1
        },
        isPexip() {
            return this.$store.state.site.isPexip
        },
    },
}
</script>

<style>
.expansion-panel-menu > div {
    padding: 0;
    background: transparent;
}
</style>
