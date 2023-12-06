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
                <v-list-item-subtitle class="pink--text text--lighten-1">
                    <translate>ROOMS</translate>
                </v-list-item-subtitle>
            </v-list-item-content>
            <img
                :src="logo"
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
                v-for="item in menuItems"
                :key="item.label"
                :to="item.to"
                :exact="item.exact ? true : false"
            >
                <v-list-item-action>
                    <v-icon color="pink lighten-1">
                        {{ item.icon }}
                    </v-icon>
                </v-list-item-action>
                <v-list-item-content>
                    <v-list-item-title>{{ item.label }}</v-list-item-title>
                </v-list-item-content>
            </v-list-item>


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

                        <v-list-item
                            v-if="settings.perms.staff"
                            :to="{ name: 'epm_settings' }"
                            exact
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-server-plus
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Inställningar</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item :to="{ name: 'epm_organization' }">
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-file-tree
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Organisationsträd</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item :to="{ name: 'epm_branding' }">
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-image-outline
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Brandingprofiler</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item
                            v-if="settings.perms.staff"
                            :to="{ name: 'epm_proxies' }"
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-weather-cloudy-arrow-right
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Proxyklienter</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item
                            v-if="settings.perms.staff"
                            :to="{ name: 'cloud_dashboard_epm' }"
                            exact
                        >
                            <v-list-item-action>
                                <v-icon color="grey">
                                    mdi-calendar-star
                                </v-icon>
                            </v-list-item-action>
                            <v-list-item-content>
                                <v-list-item-title><translate>Kalendertjänster</translate></v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>

                        <v-list-item
                            v-if="settings.perms.staff && customers.length > 1"
                            :to="{ name: 'epm_customer_dashboard' }"
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
                            v-if="settings.enableDemo"
                            :to="{ name: 'demo_generator_epm' }"
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
import { $gettext } from '@/vue/helpers/translate'

import CustomerPicker from '@/vue/components/tenant/CustomerPicker'
const menuItems = [
    {
        label: $gettext('Dashboard'),
        icon: 'mdi-view-dashboard-outline',
        to: { name: 'epm_dashboard' },
        exact: true,
    },
    {
        label: $gettext('System'),
        icon: 'mdi-google-lens',
        to: { name: 'epm_list' },
    },
    {
        label: $gettext('Adressböcker'),
        icon: 'mdi-notebook-multiple',
        to: { name: 'addressbook_list' },
    },
    {
        label: $gettext('Firmware'),
        icon: 'mdi-download-network',
        to: { name: 'epm_firmware' },
    },
    {
        label: $gettext('Bokade möten'),
        icon: 'mdi-calendar',
        to: { name: 'epm_bookings' },
    },
    {
        label: $gettext('Paneler och macron'),
        icon: 'mdi-apps-box',
        to: { name: 'control_list' },
    },
    {
        label: $gettext('Samtalsstatistik'),
        icon: 'mdi-chart-bar',
        to: { name: 'epm_statistics' },
    },
    {
        label: $gettext('Personräknare'),
        icon: 'mdi-account-group',
        to: { name: 'epm_statistics_people_count' },
    },
]

export default {
    name: 'EPMNavigation',
    components: { CustomerPicker },
    props: {
        themes: { type: Object, default() { return {} } },
    },
    data() {
        return {
            menuItems,
            logo: require('@/assets/images/mividas-epm-logo.svg'),
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
            return this.$route.fullPath.indexOf('/epm/admin') !== -1
        }
    },
}
</script>
