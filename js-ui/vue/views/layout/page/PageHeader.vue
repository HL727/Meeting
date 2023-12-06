<template>
    <v-list class="pb-0">
        <v-list-item class="px-0 align-center">
            <v-list-item-icon
                v-if="icon"
                class="mr-2 mr-sm-4"
                :class="{ 'd-none': isMobile }"
            >
                <v-icon
                    :x-large="!isMobile"
                >
                    {{ icon }}
                </v-icon>
            </v-list-item-icon>
            <v-list-item-content :class="{ 'page-title-mobile': isMobile }">
                <h1 v-if="title">
                    {{ title }}
                </h1>
                <slot name="title" />
            </v-list-item-content>

            <v-btn
                fab
                text
                small
                class="d-sm-none"
                @click="mobileShowActions = !mobileShowActions"
            >
                <v-icon>mdi-dots-vertical</v-icon>
            </v-btn>
            <v-slide-x-transition>
                <div
                    v-if="!isMobile || mobileShowActions"
                    :class="{
                        actionsMobilePopout: isMobile,
                        'elevation-6': isMobile
                    }"
                    :style="actionsContainerStyle"
                    @click="mobileShowActions = false"
                >
                    <v-btn
                        fab
                        text
                        small
                        class="d-sm-none mb-2"
                        color="danger"
                        @click="mobileShowActions = !mobileShowActions"
                    >
                        <v-icon>mdi-close</v-icon>
                    </v-btn>
                    <template v-if="$slots.actions || actions">
                        <slot
                            v-if="$slots.actions"
                            name="actions"
                        />
                        <v-list-item-icon
                            v-for="action in filteredActions"
                            :key="action.icon"
                            class="ma-0 align-self-center"
                        >
                            <v-tooltip
                                v-if="action.type === 'refresh'"
                                bottom
                            >
                                <template v-slot:activator="{ on, attrs }">
                                    <v-btn
                                        color="primary"
                                        class="ml-2"
                                        fab
                                        small
                                        outlined
                                        v-bind="attrs"
                                        :loading="isLoading"
                                        :disabled="action.disabled"
                                        v-on="on"
                                        @click="action.click ? triggerRefresh(action.click) : emitRefresh()"
                                    >
                                        <v-icon>mdi-refresh</v-icon>
                                    </v-btn>
                                </template>
                                <span><translate>Uppdatera</translate></span>
                            </v-tooltip>
                            <v-btn-confirm
                                v-else-if="action.type === 'delete'"
                                color="error"
                                fab
                                small
                                button-class="ml-2"
                                :dialog-text="action.text ? action.text : $gettext('Är du säker?')"
                                :disabled="isLoading || action.disabled"
                                :tooltip="$gettext('Ta bort')"
                                @click="emitDelete"
                            >
                                <v-icon>mdi-delete</v-icon>
                            </v-btn-confirm>
                            <v-tooltip
                                v-else-if="action.type === 'info'"
                                bottom
                            >
                                <template v-slot:activator="{ on, attrs }">
                                    <v-btn
                                        color="primary"
                                        class="ml-2"
                                        fab
                                        small
                                        v-bind="attrs"
                                        :disabled="isLoading || action.disabled"
                                        v-on="on"
                                        @click="action.click"
                                    >
                                        <v-icon>mdi-information-variant</v-icon>
                                    </v-btn>
                                </template>
                                <span><translate>Information</translate></span>
                            </v-tooltip>
                            <v-icon
                                v-else-if="action.type === 'alert'"
                                color="grey"
                                class="mr-1 ml-3"
                                large
                                :disabled="isLoading"
                            >
                                mdi-alert
                            </v-icon>
                            <v-tooltip
                                v-else-if="settings.perms.api && action.type === 'api'"
                                bottom
                            >
                                <template v-slot:activator="{ on, attrs }">
                                    <v-btn
                                        color="purple"
                                        class="ml-2 white--text"
                                        fab
                                        small
                                        v-bind="attrs"
                                        :to="{
                                            name: 'rest_client',
                                            query: { url: action.url },
                                        }"
                                        :disabled="isLoading || action.disabled"
                                        v-on="on"
                                    >
                                        <v-icon>
                                            mdi-package-variant-closed
                                        </v-icon>
                                    </v-btn>
                                </template>
                                <span>API</span>
                            </v-tooltip>
                            <v-tooltip
                                v-else-if="action.type === 'debug'"
                                bottom
                            >
                                <template v-slot:activator="{ on, attrs }">
                                    <v-btn
                                        color="lime darken-1"
                                        class="ml-2 white--text"
                                        fab
                                        small
                                        v-bind="attrs"
                                        :disabled="isLoading || action.disabled"
                                        v-on="on"
                                        @click="action.click"
                                    >
                                        <v-icon>mdi-bug</v-icon>
                                    </v-btn>
                                </template>
                                <span>Debug</span>
                            </v-tooltip>
                            <v-tooltip
                                v-else
                                bottom
                            >
                                <template v-slot:activator="{ on, attrs }">
                                    <v-btn
                                        color="primary"
                                        class="ml-2"
                                        fab
                                        small
                                        v-bind="attrs"
                                        :outlined="action.outlined"
                                        :disabled="isLoading || action.disabled"
                                        :loading="action.loading"
                                        v-on="on"
                                        @click="action.click"
                                    >
                                        <v-icon>{{ action.icon }}</v-icon>
                                    </v-btn>
                                </template>
                                <span>{{ action.tooltip }}</span>
                            </v-tooltip>
                        </v-list-item-icon>
                        <DocumentationButton
                            :doc-url="docUrl"
                            class="ml-2"
                        />
                    </template>
                </div>
            </v-slide-x-transition>
        </v-list-item>
        <slot />
        <v-divider class="my-0" />
    </v-list>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import { GlobalEventBus } from '@/vue/helpers/events'

import VBtnConfirm from '@/vue/components/VBtnConfirm'
import DocumentationButton from '@/vue/components/DocumentationButton'

export default {
    name: 'PageHeader',
    components: { VBtnConfirm, DocumentationButton },
    props: {
        icon: { type: String, default: '' },
        title: { type: String, default: '' },
        actions: { type: Array, default: () => [] },
        docUrl: { type: String, default: '' },
        loading: { type: Boolean, default: false }
    },
    data() {
        return {
            emitter: new GlobalEventBus(this),
            pageLoading: true,
            mobileShowActions: false,
        }
    },
    computed: {
        isLoading() {
            return this.loading || this.pageLoading
        },
        settings() {
            return this.$store.getters['settings']
        },
        filteredActions() {
            return this.actions.filter(a => {
                return !a.hidden
            }).map(a => {
                return {
                    ...a,
                    tooltip: a.tooltip ? a.tooltip : this.getTooltip(a)
                }
            })
        },
        actionsContainerStyle() {
            if (this.$vuetify.breakpoint.smAndUp) {
                return {
                    display: 'flex'
                }
            }

            return null
        },
        isMobile() {
            return !this.$vuetify.breakpoint.smAndUp
        },
    },
    watch: {
        loading(value) {
            this.pageLoading = value
        },
        $route() {
            this.pageLoading = true
            this.emitter = new GlobalEventBus(this)
        }
    },
    mounted() {
        this.emitter.on('loading', value => (this.pageLoading = value))
    },
    methods: {
        getTooltip(action) {
            const tooltips = {
                'mdi-pencil': $gettext('Redigera'),
                'mdi-plus': $gettext('Lägg till'),
                'mdi-layers-plus': $gettext('Lägg till flera'),
                'mdi-download': $gettext('Exportera'),
                'mdi-phone-outgoing': $gettext('Nytt samtal'),
                'mdi-email-outline': $gettext('Inbjudan'),
                'mdi-swap-horizontal': $gettext('Synkronisera')
            }

            return tooltips[action.icon] || null
        },
        emitDelete() {
            this.emitter.emit('delete')
        },
        emitRefresh() {
            this.pageLoading = true
            this.emitter.emit('refresh')
        },
        triggerRefresh(fn) {
            this.pageLoading = true
            fn.call()
        },
    }
}
</script>

<style lang="scss">
.actionsMobilePopout {
    display: flex;
    flex-direction: column;
    position: absolute;
    right: -0.75rem;
    z-index: 4;
    top: -0.5rem;
    background: #fff;
    padding: 0.75rem;
    border-radius: 4px 0 0 4px;
    align-items: center;

    > div.ma-0 {
        display: flex;
        margin-bottom: 0.5rem!important;

        > * {
            margin: 0!important;
        }
    }
    > *:last-child {
        margin: 0!important;
    }
}
.page-title-mobile > * {
    font-size: 1.25rem;
}
</style>
