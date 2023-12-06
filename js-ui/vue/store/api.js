import axios from 'axios'
//import mockData from "@/../tests/mock_data/"

import { baseURL, isTest } from '@/consts'
import * as QS from 'qs'

if (process.env.VUE_APP_TEST_SESSION) {
    window.document.cookie = 'csrftoken=ljG9lhVNHwMw3Fleim33YmGPEV4dvz4mZpGQqnV67QYfFeFCxIwlqEyKtFM5gJNO'
    window.document.cookie = 'sessionid=hyicx3e7396hbtp3gvw6x7geshqa45kt'

    axios.defaults.xsrfCookieName = 'csrftoken'
    axios.defaults.xsrfHeaderName = 'X-CSRFTOKEN'
}

function storeAPIPlugin(store) {
    let globalContext = {}
    const contextApi = (plain = false, context=null) => {
        return api.call(store, plain, {...globalContext, ...context})
    }
    store.api = contextApi
    store.subscribeAction(action => {
        globalContext = { action }
    })
}

function api(plain = false, context) {
    const headers = {
        'Content-Type': 'application/json',
    }
    if (this.state.site.csrfToken) {
        headers['X-CSRFToken'] = this.state.site.csrfToken
    }

    const instance = axios.create({
        baseURL: baseURL,
        headers: headers,
        responseType: 'json',
        paramsSerializer: params => QS.stringify(params, { arrayFormat: 'repeat' }),
        validateStatus: () => true,
    })

    instance.interceptors.request.use(config => {
        if (config.data instanceof FormData) {
            //
        } else {
            config.data = config.data || '{}'
        }

        const customerId = this.state.site.customerId

        if (!config.params) config.params = {}
        if (!config.params.customer && customerId && !config.data.customer) {
            config.headers['X-Mividas-Customer'] = customerId
        }

        if (isTest) {
            this._last_api_url = config.url
        }
        return config
    })

    if (plain) return instance

    instance.interceptors.response.use(response => handleAPIData.call(this, response, this, context))
    return instance
}

function error(context, message = null, extra, defaultMessage = '') {
    const { config, data, action, body } = context
    if (typeof message == 'string' && message.substr(0, 50).match(/<html/i)) {
        message = null
    }
    message = message || data.error || data.message || data.detail || defaultMessage

    if (isTest) {
        message += `: ${config.method.toUpperCase()} ${config.url} Action: ${action ? action.type : null} Input: ${config.data ? JSON.stringify(config.data) : ''}  Data:  ${data ? JSON.stringify(data) : body}`
    }
    const obj = new Error(message)
    Object.assign(obj, { error: message, reason: message, url: config.url, action, ...extra })
    throw obj
}

const statusErrors = {
    500: 'Unhandled exception',
    400: 'Invalid input data',
    403: 'Permission denied',
    404: 'Not found',
}

function handleAPIData(response, store, context) {
    const data = response.data

    if (isTest) {
        store._last_api_response = response
    }

    if (store.dispatch && (response.status === 401 || response.status === 403)) {
        store.dispatch('site/checkSession')
    }

    const errorContext = {
        config: response.config,
        body: response.body,
        data,
        action: context && context.action ? context.action : null,
    }

    if (!data) {
        if (response.status == 204 || response.status == 201) {
            return data
        }
        throw error(errorContext, statusErrors[response.status] || 'Invalid data')
    }

    if (data.status === 'fail' || data.errors) {
        throw error(errorContext, null, data, 'Response error')
    }
    if (response.status.toString().substr(0, 1) !== '2') {
        throw error(errorContext, null, { status: response.status, errors: data }, statusErrors[response.status] || 'Invalid response code')
    }

    return data
}

export default api
export { baseURL, storeAPIPlugin }
