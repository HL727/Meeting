import store from './store'
import * as Sentry from '@sentry/browser'

const commitSettings = (settings) => {
    if (settings.csrftoken) store.commit('site/setCSRFToken', settings.csrftoken)
    if (settings.customer_id) store.commit('site/setCustomerId', settings.customer_id)
    if (settings.provider_id) store.commit('site/setProviderId', settings.provider_id)
    if (settings.customers) store.commit('site/setCustomers', settings.customers)
    if (settings.epm_hostname) store.commit('site/setEPMHostname', settings.epm_hostname)
    if (settings.enable_organization) store.commit('site/setEnableOrganization', settings.enable_organization)
    if (settings.enable_group) store.commit('site/setEnableGroups', settings.enable_group)
    if (settings.perms) store.commit('site/setPermissions', settings.perms)
    if (settings.username) store.commit('site/setUsername', settings.username)
    if (settings.is_pexip) store.commit('site/setPexip', settings.is_pexip)
    if (settings.version) store.commit('site/setVersion', settings.version)
    if (settings.release) store.commit('site/setRelease', settings.release)
    if (settings.license) store.commit('site/setLicense', settings.license)
    if (settings.version_hash) store.commit('site/setPageLoadVersion', settings.version_hash)
}

document.addEventListener('DOMContentLoaded', () => {
    const hadSettings = !!window.MIVIDAS
    const settings = window.MIVIDAS || {}
    window.MIVIDAS = settings

    commitSettings(settings)

    if (hadSettings) {
        store.commit('site/setEnableCore', settings.enable_core)
        store.commit('site/setEnableEPM', settings.enable_epm)
        store.commit('site/setEnableAnalytics', settings.enable_analytics)
        store.commit('site/setEnableDebugViews', settings.enable_debug_views)
        store.commit('site/setEnableBranding', settings.enable_branding)
        store.commit('site/setEnableDemo', settings.enable_demo)
        store.commit('site/setEnableObtp', settings.enable_obtp)
        store.commit('site/setHasLdapAuthentication', settings.ldap_authentication)
        store.commit('site/setHasCoreProvider', settings.customer_has_provider)
        store.commit('site/setHasCalendar', settings.customer_has_calendar)
        store.commit('theme/setTheme', settings.theme_settings)
    }

    if (settings.username)
        Sentry.setUser({
            username: settings.username,
        })
})
