import '@mdi/font/css/materialdesignicons.css' // Ensure you are using css-loader
import 'typeface-roboto'

import Vue from './vue'

import * as Sentry from '@sentry/browser'
import * as Integrations from '@sentry/integrations'

import VueClipboard from 'vue-clipboard2'

VueClipboard.config.autoSetContainer = true
Vue.use(VueClipboard)

if (process.env.NODE_ENV == 'production' && window && window.MIVIDAS_ALLOW_SENTRY) {
    Sentry.init({
        dsn: 'https://e47accf806344f73883c33f3e1eccdc7@sentry.infra.mividas.com/6',
        environment: window.MIVIDAS.hostname,
        release: window.MIVIDAS.sentry_release,
        integrations: [new Integrations.Vue({ Vue, attachProps: true, logErrors: true })],
        ignoreErrors: ['Network Error', /^Request has been terminated/],
    })
}
