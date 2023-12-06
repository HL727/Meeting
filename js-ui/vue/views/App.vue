<template>
    <v-app>
        <v-navigation-drawer
            v-model="drawer"
            dark
            app
        >
            <DebugViewsNavigation v-if="isDebugViews" />
            <EPMNavigation
                v-else-if="isEPM"
                :themes="themes"
            />
            <AnalyticsNavigation
                v-else-if="isAnalytics"
                :themes="themes"
            />
            <CoreNavigation
                v-else-if="settings.enableCore"
                :themes="themes"
            />
        </v-navigation-drawer>

        <v-app-bar app>
            <v-app-bar-nav-icon
                v-if="!drawer"
                @click.stop="drawer = !drawer"
            />
            <v-btn
                v-else
                icon
                @click.stop="drawer = !drawer"
            >
                <v-icon>mdi-window-close</v-icon>
            </v-btn>

            <v-divider
                vertical
                class="ml-1"
            />
            <v-text-field
                v-if="!searchDialog"
                v-model="search"
                :label="$gettext('Sök...')"
                solo
                hide-details
                dense
                flat
                outlined
                clearable
                prepend-inner-icon="mdi-magnify"
                class="align-self-center mx-4"
            />

            <v-spacer />

            <v-toolbar-items class="d-none d-sm-flex">
                <v-divider
                    v-if="settings.enableEPM"
                    vertical
                />
                <v-btn
                    v-if="settings.enableCore"
                    to="/"
                    :class="{ 'orange darken-2 white--text': !isEPM && !isDebugViews && !isAnalytics }"
                    text
                >
                    <translate>CORE</translate>
                </v-btn>
                <v-divider
                    v-if="settings.enableCore && settings.enableEPM"
                    vertical
                />
                <v-btn
                    v-if="settings.enableEPM"
                    to="/epm/"
                    text
                    active-class="pink darken-1 white--text"
                >
                    <translate>ROOMS</translate>
                </v-btn>

                <v-divider
                    v-if="settings.enableEPM && settings.enableAnalytics"
                    vertical
                />
                <v-btn
                    v-if="settings.enableAnalytics"
                    to="/analytics/"
                    text
                    active-class="light-blue white--text darken-3"
                >
                    <translate>INSIGHT</translate>
                </v-btn>

                <v-divider vertical />

                <v-select
                    :value="$language.current"
                    :items="languages"
                    :hide-details="true"
                    item-text="code"
                    item-value="code"
                    dense
                    solo
                    prepend-icon="mdi-earth"
                    class="align-center mx-4"
                    style="max-width:7rem;"
                    @change="setLanguage"
                />

                <v-divider
                    v-if="settings.perms.staff"
                    vertical
                />
                <v-btn
                    v-if="settings.perms.staff"
                    icon
                    :to="{ name: 'debug_dashboard' }"
                    active-class="lime white--text darken-2"
                >
                    <v-icon>mdi-bug</v-icon>
                </v-btn>

                <v-divider vertical />

                <v-menu offset-y>
                    <template v-slot:activator="{ on }">
                        <v-btn
                            text
                            class="px-2"
                            v-on="on"
                        >
                            <v-avatar
                                color="grey lighten-2"
                                size="42"
                            >
                                {{ userSymbol }}
                            </v-avatar>
                        </v-btn>
                    </template>
                    <v-list>
                        <v-list-item>
                            <strong>{{ username }}</strong>
                        </v-list-item>
                        <v-divider />
                        <v-list-item
                            v-if="!settings.ldapAuthentication"
                            link
                            href="/change_password/"
                        >
                            <v-list-item-title>
                                <translate>Byt lösenord</translate>
                            </v-list-item-title>
                        </v-list-item>
                        <v-divider />
                        <v-list-item
                            link
                            href="/accounts/logout/"
                        >
                            <v-list-item-title>
                                <translate>Logga ut</translate>
                            </v-list-item-title>
                        </v-list-item>
                    </v-list>
                </v-menu>
            </v-toolbar-items>

            <v-menu
                left
                bottom
            >
                <template v-slot:activator="{ on }">
                    <v-btn
                        icon
                        class="d-sm-none"
                        v-on="on"
                    >
                        <v-icon>mdi-dots-vertical</v-icon>
                    </v-btn>
                </template>

                <v-list>
                    <v-list-item
                        v-if="settings.enableCore"
                        to="/"
                    >
                        <v-list-item-icon><v-icon>mdi-chevron-right</v-icon></v-list-item-icon>
                        <v-list-item-title><translate>Core</translate></v-list-item-title>
                    </v-list-item>
                    <v-list-item
                        v-if="settings.enableEPM"
                        to="/epm/"
                    >
                        <v-list-item-icon><v-icon>mdi-chevron-right</v-icon></v-list-item-icon>
                        <v-list-item-title><translate>Rooms</translate></v-list-item-title>
                    </v-list-item>
                    <v-list-item
                        v-if="settings.enableAnalytics"
                        to="/analytics/"
                    >
                        <v-list-item-icon><v-icon>mdi-chevron-right</v-icon></v-list-item-icon>
                        <v-list-item-title><translate>Insights</translate></v-list-item-title>
                    </v-list-item>
                    <v-divider v-if="settings.enableAnalytics" />
                    <v-list-item
                        v-if="settings.perms.staff"
                        :to="{ name: 'debug_dashboard' }"
                    >
                        <v-list-item-icon><v-icon>mdi-bug</v-icon></v-list-item-icon>
                        <v-list-item-title><translate>Debug</translate></v-list-item-title>
                    </v-list-item>
                    <v-divider />
                    <v-list-item href="/accounts/logout/">
                        <v-list-item-icon><v-icon>mdi-logout</v-icon></v-list-item-icon>
                        <v-list-item-title><translate>Logga ut</translate></v-list-item-title>
                    </v-list-item>
                </v-list>
            </v-menu>
        </v-app-bar>

        <v-main>
            <GlobalSearch
                ref="globalSearch"
                v-model="searchDialog"
                :search="search"
            />
            <v-container fluid>
                <v-alert
                    v-if="hasNewVersion"
                    prominent
                    dismissible
                    type="info"
                >
                    <translate>En ny version har driftsatts.</translate> <v-btn
                        outlined
                        @click="reload"
                    >
                        <translate>Ladda om sidan</translate>
                    </v-btn>
                </v-alert>
                <router-view />
            </v-container>
        </v-main>
    </v-app>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import EPMNavigation from '@/vue/views/layout/EPMNavigation'
import CoreNavigation from '@/vue/views/layout/CoreNavigation'
import DebugViewsNavigation from '@/vue/views/layout/DebugViewsNavigation'
import AnalyticsNavigation from './layout/AnalyticsNavigation'

import GlobalSearch from '@/vue/components/GlobalSearch'

export default {
    components: { GlobalSearch, AnalyticsNavigation, EPMNavigation, CoreNavigation, DebugViewsNavigation },
    props: {
        overrideContent: { type: Object, default() { return {} } },
        breadcrumbs: { type: Object, default() { return {} } },
        themes: { type: Object, default() { return {} } },
    },
    data() {
        return {
            drawer: null,
            title: '',
            logoEPM: require('@/assets/images/mividas-epm-logo.svg'),
            logoCore: require('@/assets/images/mividas-core-logo.svg'),
            logoDebugViews: require('@/assets/images/mividas-debug-logo.svg'),
            favicon: {
                core: require('@/assets/images/favicon/core.png'),
                rooms: require('@/assets/images/favicon/rooms.png'),
                insight: require('@/assets/images/favicon/insight.png'),
                debug: require('@/assets/images/favicon/debug.png'),
            },
            search: '',
            searchDialog: false
        }
    },
    computed: {
        username() {
            return this.settings.username
        },
        userSymbol() {
            return this.username.charAt(0).toUpperCase()
        },
        isDebugViews() {
            if (!this.settings.enableDebugViews) return false
            return this.$route.fullPath.indexOf('/debug') !== -1
        },
        isEPM() {
            if (!this.settings.enableEPM) return false
            return this.$route.fullPath.indexOf('/epm') !== -1
        },
        isAnalytics() {
            if (!this.settings.enableAnalytics) return false
            return this.$route.fullPath.indexOf('/analytics') !== -1
        },
        hasNewVersion() {
            return this.$store.state.site.hasNewVersion
        },

        settings() {
            return this.$store.state.site || {}
        },
        theme() {
            return this.$store.state.theme.theme
        },
        languages() {
            return Object.entries(this.$language.available).map((lang) => {
                return {
                    code: lang[0],
                    title: lang[1],
                }
            })
        },
    },
    watch: {
        title(newValue) {
            document.title = newValue
        },
        '$route.path': function() {
            this.$nextTick(() => this.updateTitle())
            setTimeout(() => { this.updateTitle() }, 300)
            this.search = (this.$route.query.globalSearch || '')
        },
        'instanceHead.title'() {
            this.$nextTick(this.updateTitle)
        },
        '$language'() {
            this.$forceUpdate()
        },
        search(newValue) {
            if (newValue) {
                this.$refs.globalSearch.search = newValue
                this.searchDialog = true
            }
        },
        searchDialog(newValue) {
            if (!newValue) {
                this.search = ''
            }
        }
    },
    mounted() {
        this.updateTitle()
        this.initCheckVersion()
    },
    methods: {
        getInstance() {
            try {
                if (!this.$route.matched.length) return { fallback: 1 }
                const instance = this.$route.matched[0].instances.default
                return instance || { fallback: 2 }
            } catch (e) {
                // eslint-disable-next-line no-console
                console.log(e)
                return {}
            }
        },
        getTitle() {
            const title = this.getCurrentViewTitle() || ''

            if (title && this.$vuetify.breakpoint.smAndDown) return title.replace(/ :: .*/, '')

            if (title.indexOf('::') !== -1) return title

            let suffix = ''

            if (this.isEPM) {
                this.setFavicon(this.favicon.rooms)
                suffix = 'Mividas Rooms'
            }
            else if (this.isAnalytics) {
                this.setFavicon(this.favicon.insight)
                suffix = 'Mividas Insights'
            }
            else if (this.isDebugViews) {
                this.setFavicon(this.favicon.debug)
                suffix = 'Mividas Debug'
            }
            else {
                this.setFavicon(this.favicon.core)
                suffix = 'Mividas Core'
            }

            return title ? title + ' :: ' + suffix : suffix
        },
        getCurrentViewTitle() {
            let title = ''
            try {
                const instance = this.getInstance()
                if (instance.head && instance.head.title) {
                    return instance.head.title
                }
                if (instance.$el) {
                    const h1 = instance.$el.querySelector('h1') || instance.$el.querySelector('span.h1')
                    if (h1) title = h1.querySelector('span')?.textContent
                    if (h1 && !title) title = h1.textContent || ''
                    return title
                }
            } catch (e) {
                // eslint-disable-next-line no-console
                console.log('Error getting title:', e)
            }
        },
        setFavicon(icon) {
            const favicon = document.getElementById('favicon')
            if (!favicon) return

            if (this.theme.favicon) {
                favicon.href = this.theme.favicon
                return
            }
            favicon.href = icon
        },
        updateTitle() {
            if (this.isDebugViews) {
                this.setFavicon(this.favicon.debug)
                this.title = $gettext('Mividas Debug')
            } else {
                this.title = this.getTitle()
            }
        },
        initCheckVersion() {
            let nextCheck = null
            this.$router.beforeEach((to, from, next) => {
                next()
                if (nextCheck && nextCheck > new Date().getTime()) {
                    return
                }
                nextCheck = new Date().getTime() + 30 * 1000
                this.$store.dispatch('site/checkSession', { nextUrl: to.fullPath })
            })
            this.$store.dispatch('site/checkSession')
        },
        setLanguage(code) {
            return this.$store.api()
                .post('language/', { code })
                .then(() => location.reload())
        },
        reload() {
            location.reload()
        },

    },
}
</script>
