<template>
    <v-tooltip bottom>
        <template v-slot:activator="{ on }">
            <v-icon
                :color="color"
                size="22"
                class="mr-1"
                :class="{
                    'icon-status-passive': endpoint.connection_type === 0,
                    'icon-status-proxy': endpoint.connection_type === 2,
                }"
                v-on="on"
            >
                {{ icon }}
            </v-icon>
            <span v-if="text">{{ statusText }}</span>
        </template>

        <span>
            {{ statusText }}. <translate>Anslutning</translate>: {{ connectionText }}
        </span>
    </v-tooltip>
</template>

<script>
import {endpointConnectionTypeNames, endpointStatusNames} from '@/vue/store/modules/endpoint/consts'

export default {
    props: {
        endpoint: { type: Object, default() { return {} } },
        text: { type: Boolean, default: false },
        ignoreMeetingStatus: { type: Boolean, default: false },
    },
    computed: {
        status() {
            return this.endpoint.status_code
        },
        icon() {
            if (!this.ignoreMeetingStatus && this.endpoint.status && this.endpoint.status.active_meeting) {
                return this.status === 20 ? 'mdi-calendar-account' : 'mdi-calendar'
            }
            if (this.status < 0) {
                return 'mdi-alert'
            }

            const icons = {
                0: 'mdi-checkbox-blank-circle-outline',
                1: 'mdi-help-circle-outline',
                10: 'mdi-checkbox-marked-circle',
                20: 'mdi-phone-in-talk'
            }

            return icons[this.status] || 'mdi-circle'
        },
        color() {
            if (!this.ignoreMeetingStatus && this.endpoint.status && this.endpoint.status.active_meeting) {
                return '#F44336'
            }

            const colors = {
                10: '#4CAF50',
                20: '#F44336',
            }
            return colors[this.status] || '#666666'
        },
        statusText() {
            return endpointStatusNames[this.status]
        },
        connectionText() {
            return endpointConnectionTypeNames[this.endpoint.connection_type]
        },
    },
}
</script>

<style>
.icon-status-passive {
    border-bottom: 1px #666 dashed;
}
.icon-status-proxy {
    border-bottom: 1px #666 dotted;
}
</style>
