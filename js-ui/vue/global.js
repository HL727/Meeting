import Vue from 'vue'

import { closeDialog } from '@/vue/helpers/dialog'
import { timestamp, since, duration, formatDate, isoDate } from '@/vue/helpers/datetime'

export function initVue(Vue) {

    Vue.filter('timestamp', ts => {
        return timestamp(ts)
    })
    Vue.filter('since', ts => {
        return since(ts)
    })
    Vue.filter('duration', ts => {
        return duration(ts)
    })

    Vue.filter('date', ts => {
        return isoDate(ts)
    })

    Vue.filter('time', ts => {
        return formatDate(ts, 'HH:mm')
    })

    Vue.directive('close-dialog', (el, directive, vnode) => {
        const component = vnode.componentInstance || vnode.context
        component.$on('click', e => {
            if (closeDialog(vnode)) e.preventDefault()
        })
    })

    Vue.directive('router-link', (el, directive, vnode) => {
        const href = vnode.context.$router.resolve(directive.value).href
        el.setAttribute('href', href)
        el.addEventListener('click', e => {
            vnode.context.$router.push(directive.value).catch(() => null)
            e.preventDefault()
        })
    })

}

initVue(Vue)
