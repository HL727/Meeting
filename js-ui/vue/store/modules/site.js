import { replaceQuery } from '@/vue/helpers/url'
import { singleGet } from '@/vue/helpers/store'

export default {
    state() {
        return {
            csrfToken: '',
            customerId: null,
            customers: {},
            enableOrganization: true,
            enableGroups: false,
            breadcrumb: [],
            epmHostname: window.location.host,
            perms: {},
            username: '',
            enableCore: true,
            enableEPM: true,
            enableAnalytics: true,
            enableDebugViews: false,
            enableBranding: false,
            enableObtp: true,
            enableDemo: false,
            ldapAuthentication: false,
            hasNewVersion: false,
            hasCoreProvider: false,
            hasCalendar: false,
            isPexip: false,
            providerId: null,
            staticPageUrlName: '',
            license: {},
            version: '',
            release: '',
            pageLoadVersion: '',
            homeRoutes: {}
        }
    },
    getters: {
        customer(state) {
            if (!state.customerId) return {}
            return state.customers[state.customerId]
        },
        license(state) {
            return state.license
        }
    },
    actions: {
        singleGet,
        checkSession({ commit, state, dispatch }, options) {
            return dispatch('singleGet', 'session/').then(response => {
                if (response.status !== 'OK') {
                    return
                }

                if (state.pageLoadVersion && response.version_hash !== state.pageLoadVersion) {
                    commit('setHasNewVersion')
                }
                commit('setPageLoadVersion', response.version_hash)

                if (!response.is_authenticated) {
                    location.href = replaceQuery('/accounts/login/', { next: options ? options.nextUrl : undefined })
                } else if (response.license) {
                    commit('setLicense', response.license)
                }
            }).catch(e => e)
        }
    },
    mutations: {
        setCSRFToken(state, token) {
            state.csrfToken = token
        },
        setCustomerId(state, id) {
            state.customerId = id
        },
        setCustomers(state, customers) {
            const result = {}
            customers.forEach(c => (result[c.id || c.pk] = { ...c, id: c.id || c.pk }))
            state.customers = result
        },
        setProviderId(state, providerId) {
            state.providerId = providerId
        },
        setLicense(state, license) {
            state.license = { ...state.license, ...license }
        },
        setEPMHostname(state, hostname) {
            state.epmHostname = hostname
        },
        setEnableOrganization(state, enable) {
            state.enableOrganization = enable
        },
        setEnableGroups(state, enable) {
            state.enableGroups = enable
        },
        setBreadCrumb(state, crumbs) {
            state.breadcrumb = crumbs
        },
        setPermissions(state, perms) {
            state.perms = { ...state.perms, ...perms }
        },
        setUsername(state, username) {
            state.username = username
        },
        setEnableCore(state, enable) {
            state.enableCore = enable
        },
        setEnableEPM(state, enable) {
            state.enableEPM = enable
        },
        setEnableAnalytics(state, enable) {
            state.enableAnalytics = enable
        },
        setEnableBranding(state, enable) {
            state.enableBranding = enable
        },
        setEnableDemo(state, enable) {
            state.enableDemo = enable
        },
        setEnableObtp(state, enable) {
            state.enableObtp = enable
        },
        setHasLdapAuthentication(state, enable) {
            state.ldapAuthentication = enable
        },
        setEnableDebugViews(state, enable) {
            state.enableDebugViews = enable
        },
        setHasNewVersion(state) {
            state.hasNewVersion = true
        },
        setHasCoreProvider(state, value) {
            state.hasCoreProvider = value
        },
        setHasCalendar(state, value) {
            state.hasCalendar = value
        },
        setPexip(state, value) {
            state.isPexip = value
        },
        setStaticPageUrlName(state, value) {
            state.staticPageUrlName = value
        },
        setVersion(state, value) {
            state.version = value
        },
        setRelease(state, value) {
            state.release = value
        },
        setPageLoadVersion(state, value) {
            state.pageLoadVersion = value
        },
        setHomeRoute(state, route) {
            state.homeRoutes[route.name] = {
                name: route.name,
                query: { ...route.query }
            }
        }
    },
    namespaced: true,
}
