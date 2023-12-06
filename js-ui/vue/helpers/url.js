import * as QS from 'query-string'
import store from '@/vue/store'

export function addCustomerQuery(url, customerId = null) {
    const realId = customerId === null ? store.state.site.customerId : customerId
    if (!realId) return url
    return replaceQuery(url, { customer: realId })
}

export function replaceQuery(curUrl, newParams) {
    const { url, query } = QS.parseUrl(curUrl || location.href)
    const params = { ...query, ...newParams }

    return `${url}?${QS.stringify(params)}`
}

export function setQuery(curUrl, newParams, removeEmpty = false) {
    const { url, query } = QS.parseUrl(curUrl || location.href)

    let result = {}

    if (removeEmpty) {
        Object.entries(newParams ? newParams : query).forEach(x => {
            if (x[1] || x[1] === 0) result[x[0]] = x[1]
        })
    } else {
        result = newParams ? newParams : query
    }

    return `${url}?${QS.stringify(result)}`.replace(/\?$/, '')
}

export function trailingSlash(curUrl) {
    const [url, query] = curUrl.split('?')

    if (!url || url.substring(url.length - 1) === '/') return curUrl

    if (query) return `${url}/?${query}`

    return url + '/'
}
