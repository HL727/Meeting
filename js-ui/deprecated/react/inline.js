import ReactDOM from 'react-dom'
import React from 'react'
import jQuery from 'jquery'

import components from './components/public'

// TODO: kolla om funka utan import?
//import enGB from 'date-fns/locale/en-GB'
//registerLocale('en-GB', enGB);

class State extends React.Component {
    constructor(props) {
        super(props)

        this.state = {}
    }
}

const state = React.createElement(State)

function renderReactComponent(component, props, rendertarget) {
    props.state = state
    return ReactDOM.render(React.createElement(component, props), rendertarget)
}

let hasInitialized = false
jQuery(() => {
    if (hasInitialized) return
    hasInitialized = true

    initReactInline(document)
})

const initReactInline = parent => {
    const $ = jQuery
    $('[data-react]', parent).each(function() {
        var props = $(this).data()
        var componentName = props.react
        delete props.react

        var component = components[componentName]
        if (!component) {
            throw new Error('react-components.html: Could not find component "' + componentName + '"!')
        }

        var rendertarget = this
        renderReactComponent(component, props, rendertarget)
    })
}

;(window.jsInlineInit = window.jsInlineInit || []).push(initReactInline)
