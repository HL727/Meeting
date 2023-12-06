
import { $gettext, $gettextInterpolate } from '@/vue/helpers/translate'
import Vue from 'vue'

import components from './components/public'
import vuetify from './vuetify'

import store from './store'
import router from './router'
import $ from 'jquery'

const state = new Vue({
    data() {
        return {
            provider_status: { loading: false },
            counters: { loading: false },
        }
    },
})

let hasInitialized = false
document.addEventListener('DOMContentLoaded', () => {
    if (hasInitialized) return
    hasInitialized = true

    initVueInline(document)
})

const initVue = (el, component, attrs, child) => {
    new Vue({
        el: el,
        store,
        router,
        vuetify,
        render: h =>
            h(
                component,
                {
                    props: { state },
                    attrs: { ...attrs }, // copy attrs, otherwise it can be reset by some reason (?)
                    components,
                },
                !child ? [] : [h(child, { attrs: { state } })]
            ),
    })
}

const initVueInline = parent => {


    $('[data-vue]', parent).each((i, el) => {
        const name = $(el).data('vue')
        mountInline(name, el)
    })

    const initDateTime = (query, component) => {
        $(query, parent).each(function(i, el) {
            $(el).wrap('<div>')
            mountInline(component, el.parentNode, {
                inputName: el.name,
                value: el.value,
            })
        })
    }

    initDateTime('input[name*=date_start], input[name*=date_stop]', 'DatePicker')
    initDateTime('input[name*=time_start], input[name*=time_stop]', 'DatePicker')
    initDateTime('input[name*=ts_start], input[name*=ts_stop], input[name*=ts_auto_remove]', 'DateTimePicker')
}

function loadAttrs(el, extraAttrs) {
    const attrs = { ...extraAttrs }

    Array.prototype.slice
        .call(el.attributes)
        .forEach(a => (attrs[a.name.replace(/^data-/, '')] = a.value))
    delete attrs.vue

    Object.entries(attrs).forEach(entry => {
        const [key, value] = entry
        if (typeof value !== 'string') return
        try {
            attrs[key] = JSON.parse(value)
        } catch (e) {
            //
        }
    })

    /* temp fix for input styles */
    if (name.match(/Picker$/)) {
        attrs['input-attrs'] = { ...attrs['input-attrs'], outlined: true }
    }
    return attrs
}

function mountInline(name, el, extraAttrs = null) {

    const attrs = loadAttrs(el, extraAttrs)

    if (components[name]) {
        let template = el.innerHTML
            .trim()
            .replace(/^`/, '')
            .replace(/[;`]+$/, '')
        if (template && !template.match(/^</)) {
            template = $gettextInterpolate($gettext('<div>%{ template }</div>'), { template: template })
        }

        const child = template
            ? {
                template,
                components,
            }
            : null

        initVue(el, components[name], attrs, child)
    } else {
        // eslint-disable-next-line no-console
        console.warn('Component ' + name + ' not availiable') //
    }
}

(window.jsInlineInit = window.jsInlineInit || []).push(initVueInline)
