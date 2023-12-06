import Vue from 'vue'

export function closeDialog(target) {

    if (!target) return false

    let component = target
    if (target && target.parentNode) { // TODO loop many levels down?
        component = target.__vue__ ? target.__vue__ : target.parentNode.__vue__
        if (!component) {
            return false
        }
    }
    const instance = component.componentInstance ? component.componentInstance : component

    let p = instance
    while ((p = p.$parent))
        if (p.$options.name == 'v-dialog') {
            p.isActive = false
            return true
        }
    return false
}

export const CloseDialogMixin = Vue.extend({
    methods: {
        closeDialog() {
            closeDialog(this)
        },
    },
})

export function handleDjangoAdminPopup(href, windowNamespace, callback=null) {

    const popup = window.open(href, windowNamespace, 'width=1024,height=600')
    if (!popup) return

    const handlers = [
        'dismissChangeRelatedObjectPopup',
        'dismissDeleteRelatedObjectPopup',
        'dismissAddRelatedObjectPopup'
    ]
    const djangoEventCallback = (popupWindow, value) => {
        handlers.forEach(k => window[k] = function() {})
        if (callback) {
            callback(value)
        }
        popupWindow.close()
    }
    handlers.forEach(k => window[k] = djangoEventCallback)

    return popup
}
