import Vue from 'vue'
import Vuex from 'vuex'

import { debug } from '@/consts'
import { storeAPIPlugin } from './api'

import endpoint from './modules/endpoint'
import endpoint_branding from './modules/endpoint_branding'
import addressbook from './modules/addressbook'
import organization from './modules/organization'
import calendar from './modules/calendar'
import customer from './modules/customer'
import cospace from './modules/cospace'
import call from './modules/call'
import user from './modules/user'
import pexipUser from './modules/user/pexip'
import provider from './modules/provider'
import site from './modules/site'
import pexipCospace from './modules/cospace/pexip'
import meeting from './modules/meeting'
import stats from './modules/stats'
import policy from './modules/policy'
import theme from './modules/theme'
import policy_rule from './modules/policy_rule'
import roomcontrol from './modules/roomcontrol'
import debug_views from './modules/debug_views'

Vue.use(Vuex)

// eslint-disable-next-line max-lines-per-function
export function getStore() {
    const store = new Vuex.Store({
        plugins: [storeAPIPlugin],
        getters: {
            settings(state) {
                return state.site
            },
        },
        modules: {
            endpoint,
            endpoint_branding,
            addressbook,
            organization,
            cospace,
            'cospace/pexip': pexipCospace,
            calendar,
            customer,
            roomcontrol,
            call,
            user,
            'user/pexip': pexipUser,
            stats,
            policy,
            policy_rule,
            meeting,
            provider,
            site,
            theme,
            debug_views,
        },
        strict: debug,
    })

    if (module.hot) {
        // accept actions and mutations as hot modules
        module.hot.accept(
            [
                './modules/endpoint',
                './modules/endpoint_branding',
                './modules/addressbook',
                './modules/organization',
                './modules/cospace',
                './modules/site',
                './modules/meeting',
                './modules/stats',
                './api',
            ],
            () => {
                store.hotUpdate({
                    modules: {
                        endpoint: require('./modules/endpoint').default,
                        endpoint_branding: require('./modules/endpoint_branding').default,
                        addressbook: require('./modules/addressbook').default,
                        organization: require('./modules/organization').default,
                        cospace: require('./modules/cospace').default,
                        meeting: require('./modules/meeting').default,
                        site: require('./modules/site').default,
                        stats: require('./modules/stats').default,
                    },
                })
                Vuex.Store.prototype.api = require('./api').default
            }
        )
    }

    return store
}

const store = getStore()

export default store
