<template>
    <v-expansion-panel>
        <v-expansion-panel-header>
            <v-icon :color="iconColor">
                {{ icon }}
            </v-icon>
            <div>
                <strong class="d-block mb-2">{{ proxy.name }}</strong>
                <div><i>IP: {{ proxy.last_connect_ip }}</i></div>
            </div>
            <div class="ml-auto flex-grow-0 mr-2">
                <v-chip
                    pill
                    :class="{ 'bg-danger': !proxy.is_online, 'bg-success': proxy.is_online }"
                >
                    {{ counter }}
                </v-chip>
            </div>
        </v-expansion-panel-header>
        <v-expansion-panel-content class="px-0">
            <v-simple-table>
                <thead>
                    <tr>
                        <th
                            v-translate
                            class="text-left"
                            colspan="2"
                        >
                            Endpoints
                        </th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td v-translate>
                            Online
                        </td>
                        <td class="text-right">
                            {{ proxy.endpoint_count.online }}
                        </td>
                    </tr>
                    <tr>
                        <td v-translate>
                            Totalt
                        </td>
                        <td class="text-right">
                            {{ proxy.endpoint_count.total }}
                        </td>
                    </tr>
                </tbody>
            </v-simple-table>
        </v-expansion-panel-content>
    </v-expansion-panel>
</template>

<script>
export default {
    filters: {
        floatformat(value) {
            return parseFloat(value || 0)
                .toString()
                .replace(/\.(.).*/, '.$1')
        },
    },
    props: {
        proxy: {
            type: Object,
            required: true,
        },
        counter: {
            type: Number,
            default: 1,
        },
    },
    computed: {
        iconColor() {
            if (!this.proxy.is_online) {
                return 'red'
            }
            return 'green'
        },
        icon() {
            if (!this.proxy.is_online) {
                return 'mdi-alert-circle'
            }

            return 'mdi-check-circle'
        },
    },
}
</script>
