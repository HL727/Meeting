import Vue from 'vue'
import Router from 'vue-router'

import { isTest } from '@/consts'
import endpoint from './endpoint'
import addressbook from './addressbook'
import cospace from './cospace'
import user from './user'
import calls from './calls'
import meeting from './meeting'
import policy from './policy'
import analytics from './analytics'
import provider from '@/vue/router/provider'
import roomcontrol from '@/vue/router/roomcontrol'
import debug_views from './debug_views'
import StaticPageFallback from '@/vue/views/StaticPageFallback'

Vue.use(Router)

// eslint-disable-next-line max-lines-per-function
function getRouter() {
    const router = new Router({
        mode: isTest ? 'hash' : 'history',
        routes: [
            ...endpoint,
            ...addressbook,
            ...cospace,
            ...roomcontrol,
            ...user,
            ...calls,
            ...meeting,
            ...debug_views,
            ...policy,
            ...analytics,
            ...provider,


            {
                path: '/core/admin/restclient/',
                name: 'rest_client',
                component: StaticPageFallback,
            },
            {
                path: '/core/admin/customers/',
                name: 'customer_dashboard',
                component: () => import(/* webpackChunkName: "provider" */ '@/vue/views/customer/CustomerDashboard'),
            },
            {
                path: '/core/admin/settings/',
                name: 'settings',
                component: () => import(/* webpackChunkName: "theme" */ '@/vue/views/theme/ThemeSettings'),
            },
            {
                path: '/',
                name: 'start',
                component: () => import(/* webpackChunkName: "core" */ '@/vue/views/CoreDashboard'),
            },
            {
                path: '*',
                component: StaticPageFallback,
                pathToRegexpOptions: {
                    strict: true,
                },
            },
        ],
    })

    let routeCounter = 0
    router.beforeEach(function(to, from, next) {
        const customerId = to && to.query && to.query.customer
        if (customerId !== undefined) {
            if (customerId.toString() !== window.MIVIDAS.customer_id.toString()) {
                location.href = to.fullPath
                return next(false)
            }
        }
        /* Use to separate events for a specific page load. Use with GlobalEmitter */
        to.meta.prevRoute = {
            counter: routeCounter,
            name: from.name,
            query: from.query
        }

        routeCounter += 1
        to.meta.counter = routeCounter
        next()
    })

    return router
}

const router = getRouter()

export default router

export { getRouter }
