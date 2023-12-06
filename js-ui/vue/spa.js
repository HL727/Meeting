import router from './router'

import store from './store'
import Vue from 'vue'

import App from './views/App'

import vuetify from './vuetify'
import { getCurrentPageContent } from '@/vue/helpers/static_pages'

document.addEventListener('DOMContentLoaded', () => {
    const location = window.location.hash.replace(/^#\//, '')
        ? window.location.hash.substr(1)
        : `${window.location.pathname}?${window.location.search.replace(/^\?/, '')}`.replace(/\?$/, '')
    if (location !== '/') router.replace({ path: location }).catch(() => undefined)

    const app = document.getElementById('app')
    if (app) {
        initApp(app)
    }

    const staticVue = document.getElementById('staticvue')
    const breadcrumbDom = document.getElementById('staticbreadcrumb')

    if (staticVue) {
        const override = getCurrentPageContent(router, staticVue, breadcrumbDom, document.title)
        initApp(staticVue, {
            overrideContent: override,
        })
    }
})

const initApp = (app, attrs = {}) => {
    const csrf = app.getAttribute('data-csrftoken')
    if (csrf) store.commit('site/setCSRFToken', csrf)

    const customerId = app.getAttribute('data-customer-id')
    if (customerId) store.commit('site/setCustomerId', customerId)

    const providerId = app.getAttribute('data-provider-id')
    if (providerId) store.commit('site/setProviderId', providerId)

    const enableOrganization = app.getAttribute('data-enable-organization')
    if (enableOrganization) store.commit('site/setEnableOrganization', enableOrganization)

    document.body.removeAttribute('data-app')
    window.MIVIDAS.vue_spa = new Vue({
        router,
        store,
        vuetify,
        inheritAttrs: false,
        data: () => attrs,
        render: h => h(App, { props: { themes: window.MIVIDAS.themes } }),
    }).$mount(app)
}
