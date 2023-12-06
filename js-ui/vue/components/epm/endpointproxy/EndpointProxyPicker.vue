<template>
    <v-select
        v-model="internalValue"
        :items="items"
        return-object
        item-text="name"
        item-value="id"
        clearable
        v-bind="$attrs"
        @click:clear="$emit('input', null)"
        v-on="on"
    >
        <template v-slot:item="{ item }">
            <v-list-item-icon>
                <EndpointProxyStatusIndicator :proxy="item" />
            </v-list-item-icon>
            <v-list-item-content>
                <v-list-item-title>
                    {{ item.name }}
                </v-list-item-title>
                <v-list-item-subtitle v-if="item.last_connect_ip">
                    {{ item.last_connect_ip }}
                </v-list-item-subtitle>
            </v-list-item-content>
        </template>
    </v-select>
</template>
<script>

import EndpointProxyStatusIndicator from './EndpointProxyStatusIndicator'
export default {
    name: 'EndpointProxyPicker',
    components: {EndpointProxyStatusIndicator},
    inheritAttrs: false,
    props: {
        returnObject: Boolean,
        value: {
            type: [Object, Number],
            required: false,
            default: null,
        },
    },
    data() {
        let value = null
        if (this.value && typeof this.value == 'object') value = this.value.id
        else value = this.value

        return {
            internalValue: value || null,
        }
    },
    computed: {
        on() {
            return { ...this.$listeners, input: undefined }
        },
        returnValue() {
            if (!this.internalValue) return null
            return this.returnObject ? this.internalValue : this.internalValue.id
        },
        items() {
            return Object.values(this.$store.state.endpoint.proxies)
                .filter(proxy => !!proxy.ts_activated)
                .sort((a, b) => a.name.toString().localeCompare(b.name))
        },
    },
    watch: {
        internalValue(newValue, oldValue) {
            if ((newValue ? newValue.id : null) != (oldValue ? oldValue.id : null)) {
                this.$emit('input', this.returnValue)
            }
        },
        value(newValue) {
            if (newValue && typeof newValue == 'object') {
                this.internalValue = newValue
            } else if (newValue) {
                this.internalValue = this.$store.state.endpoint.proxies[newValue]
            } else {
                this.internalValue = null
            }
        }
    },
    mounted() {
        this.$store.dispatch('endpoint/getProxies')
    }
}
</script>
