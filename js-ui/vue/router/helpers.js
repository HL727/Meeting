import { addCustomerQuery, trailingSlash } from '@/vue/helpers/url'
import StaticPageFallback from '@/vue/views/StaticPageFallback'

let tempFix = null
setTimeout(() => {
    tempFix = true
}, 2000)

export const staticContentView = (path, name) => {
    return {
        path,
        name,
        component: StaticPageFallback,
        pathToRegexpOptions: {
            strict: true,
        },
    }
}

export const redirectUrl = (path, name) => {
    return {
        path,
        name,
        beforeEnter(to) {
            if (!tempFix) return // temp fix for onload-redirect
            const newUrl = trailingSlash(addCustomerQuery(to.fullPath))
            location.href = newUrl
            return false
        },
        pathToRegexpOptions: {
            strict: true,
        },
    }
}
export const idIntProps = route => {
    return { id: parseInt(route.params.id) }
}
