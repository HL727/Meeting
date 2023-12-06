<template>
    <div>
        <div v-if="!loading">
            <div
                v-include-override
                class="static-dom view"
            />
        </div>
        <div
            v-else
            class="view"
        >
            <v-progress-linear
                indeterminate
                color="primary"
            />

            <v-skeleton-loader
                tile
                type="heading"
                class="mb-8 mt-4"
                min-height="50"
            />
            <v-row>
                <v-col
                    cols="12"
                    md="8"
                >
                    <v-skeleton-loader
                        tile
                        type="card"
                    />
                </v-col>
                <v-col
                    cols="12"
                    md="4"
                >
                    <v-skeleton-loader
                        tile
                        type="card"
                    />
                </v-col>
            </v-row>
        </div>
    </div>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import axios from 'axios'
import { getCurrentPageContent } from '@/vue/helpers/static_pages'
import { trailingSlash, addCustomerQuery } from '@/vue/helpers/url'
import {replaceQuery} from '../helpers/url'
import { globalEmit } from '@/vue/helpers/events'

/* eslint-disable no-console */
export default {
    name: 'StaticPageFallback',
    directives: {
        includeOverride(dom, binding, vnode) {
            if (vnode.context.loading) return

            const activeOverride = vnode.context.activeOverride
            if (activeOverride && vnode.context.lastStateKey === activeOverride.stateKey) {
                return
            }

            vnode.context.lastStateKey = activeOverride ? activeOverride.stateKey : -1

            dom.innerHTML = ''
            if (!activeOverride) {
                return
            }

            vnode.context.$store.commit('site/setStaticPageUrlName', activeOverride.urlName)

            const slot = binding.arg || $gettext('default')
            const override = activeOverride.slots[slot] || []

            for (let i = 0; i < override.length; i++) {
                dom.appendChild(override[i])
            }
            try {
                window.dispatchEvent(new Event('resize'))
            } catch (e) {
                //
            }
        },
    },
    props: {
        overrideContent: {
            type: Object,
            default() {
                return this.$root.overrideContent || null
            },
        },
        staticContainerSelector: {
            type: String,
            default() {
                return '#staticvue'
            },
        },
        spaContainerSelector: {
            type: String,
            default() {
                return '#app'
            },
        },
    },
    data() {
        return {
            activeOverride: this.getOverrideContent(this.overrideContent, false),
            override: this.overrideContent,
            loading: false,
            lastStateKey: -1,
        }
    },
    computed: {
        head() {
            return {
                title: this.activeOverride ? this.activeOverride.title : '',
            }
        },
    },
    watch: {
        '$route.fullPath'() {
            this.updateOverrideContent()
        },
        override() {
            this.updateOverrideContent()
        },
    },
    created() {
        this.updateOverrideContent()
    },
    mounted() {
        this.$el.addEventListener('click', this.handleLinkClick)
        this.$el.addEventListener('submit', this.handleSubmit)
    },
    destroyed() {
        this.$el.removeEventListener('click', this.handleLinkClick)
        this.$el.removeEventListener('submit', this.handleSubmit)
        this.$store.commit('site/setStaticPageUrlName', '')
    },
    methods: {
        getOverrideContent(override, allowFetch = true) {
            const curPage = override && override[window.history.state && window.history.state.key]
            if (!curPage || curPage.url !== this.$route.fullPath) {
                if (curPage) console.log('url not matching', curPage.url, this.$route.fullPath)
                if (allowFetch) this.fetchExternalPage(this.$route.fullPath)
                return
            }

            return curPage
        },
        updateOverrideContent() {
            this.activeOverride = this.getOverrideContent(this.override)
        },
        bindLinkClick() {
            if (!this.$el) return console.log(this)
            this.$el.removeEventListener('click', this.handleLinkClick)
            this.$el.addEventListener('click', this.handleLinkClick)
        },
        isNativeLink(a) {
            if (!a || a.getAttribute('data-toggle') || a.getAttribute('target')) return true

            const href = a.getAttribute('href')
            if (!href || href.match(/^#/)) return true

            const hrefWithoutQuery = href.replace(/\?.*/, '')

            if (href.match(/:/)) return true  // probably scheme
            if (href.match(/:/)) return true  // probably scheme

            if (!hrefWithoutQuery.match(/\/$/)) { // No trailing slash. Probably not django html view
                // TODO make sure all none html-views are marked with target or file extension
                return true
            }
            return false
        },
        handleLinkClick(ev) {
            const a = ev.target?.closest('a')

            if (!a) return

            const href = a.getAttribute('href')
            if (!href || this.isNativeLink(a)) return

            const customerIdMatch = href.match(/customer=(\d+)/)
            if (customerIdMatch && customerIdMatch[1] !== this.$store.state.site.customerId.toString()) {
                ev.preventDefault()
                location.href = href // reload full page with new customer settings loaded
            }

            const match = this.$router.resolve(href).resolved.matched
            if (match.length) {
                if (a.getAttribute('href') === this.$route.fullPath) {
                    return // click on same page -> reload
                }
                ev.preventDefault()
                this.$router.push(a.getAttribute('href')).catch(e => {
                    if (e && e.name === 'NavigationDuplicated') {
                        this.$router.push(replaceQuery(this.$route.fullPath, { _: new Date() - 1 }))
                    }
                })
            }
        },
        handleSubmit(ev) {
            const form = ev.target?.closest('form')

            if (form && !form.getAttribute('action')) {
                form.action = trailingSlash(location.href)
            }
        },
        async fetchExternalPage(url) {
            this.loading = true
            let response
            try {
                response = await axios.get(addCustomerQuery(trailingSlash(url)), {
                    headers: { 'X-STATICFALLBACK': 1 },
                })
            } catch (e) {
                console.warn('Get error', e)
                return location.reload()
            } finally {
                this.loading = false
            }

            if (response.status === 200) {
                this.mountHtml(response.data, url)
                globalEmit(this, 'loaded')
                return
            }

            if (!this.$route.query._fallback_redirect) {
                location.href = replaceQuery(location.href, { _fallback_redirect: 1 })
            }
        },
        mountHtml(html, url) {

            const tempEl = document.createElement('div')

            const title = html.match(/<title> *(.*?) *<\/title>/i)

            const body = html.replace(/.*<body/, '<body').replace(/<\/body>.*/, '</body>')

            if (window.jQuery) {
                // runs javascript
                try {
                    window
                        .jQuery(tempEl)
                        .appendTo(document.body)
                        .append(body)
                        .remove()
                } catch (e) {
                    console.log(e)
                    tempEl.innerHTML = body
                }
            } else {
                tempEl.innerHTML = body
            }

            const container = tempEl.querySelector(this.staticContainerSelector)
            const app = tempEl.querySelector(this.spaContainerSelector)
            if (container) {
                this.initContainer(url, container, title)
            } else if (app && app.getAttribute('data-url')) {
                this.$router.replace(app.getAttribute('data-url')).catch(() => true)
            }
        },
        initContainer(url, container, title) {
            window.jsInlineInit && window.jsInlineInit.forEach(cb => cb(container))
            this.override = {
                ...this.override,
                ...getCurrentPageContent(this.$router, container, null, title ? title[1] : ''),
            }

            container.querySelectorAll('form').forEach(form => {
                if (!form.getAttribute('action')) {
                    form.action = addCustomerQuery(trailingSlash(url))
                }
            })

            this.$root.updateTitle && this.$root.updateTitle()
        },
    },
}
</script>
