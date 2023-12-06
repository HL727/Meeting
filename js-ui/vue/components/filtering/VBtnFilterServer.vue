<template>
    <v-dialog
        v-model="dialog"
        scrollable
        max-width="320"
    >
        <template v-slot:activator="{ on }">
            <VBtnFilter
                :filters="filters"
                hide-close
                icon="mdi-server"
                :text="$gettext('Server')"
                :disabled="loading"
                :class="buttonClass"
                v-on="on"
            />
        </template>
        <v-card>
            <v-card-title><translate>Server</translate></v-card-title>
            <v-divider />
            <v-card-text class="pt-4">
                <v-radio-group v-model="filterServer">
                    <v-radio
                        v-for="server in servers"
                        :key="'server' + server.id"
                        :label="server.title"
                        :value="server.id"
                    >
                        {{ server.title }}
                    </v-radio>
                </v-radio-group>
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-btn
                    color="primary"
                    @click="applyFilters"
                >
                    <translate>Tillämpa</translate>
                </v-btn>
                <v-spacer />
                <v-btn
                    v-close-dialog
                    text
                    color="red"
                >
                    <translate>Stäng</translate>
                    <v-icon
                        right
                        dark
                    >
                        mdi-close
                    </v-icon>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import VBtnFilter from '@/vue/components/filtering/VBtnFilter'

export default {
    name: 'VBtnFilterServer',
    components: { VBtnFilter },
    props: {
        title: { type: String, default: ''},
        value: { type: Number, default: 0 },
        servers: { type: Array, required: true },
        loading: { type: Boolean, default: false },
        buttonClass: { type: String, default: '' }
    },
    data() {
        return {
            dialog: false,
            filterServer: this.value,
        }
    },
    computed: {
        activeServer() {
            if (!this.servers) {
                return null
            }
            return this.servers.find(s => s.id === this.value)
        },
        filters() {
            return [{
                value: this.activeServer ? this.activeServer.title : ''
            }]
        },
    },
    watch: {
        value(newValue) {
            this.filterServer = newValue
        }
    },
    methods: {
        applyFilters() {
            this.$emit('input', this.filterServer)
            this.$emit('filter')
            this.dialog = false
        }
    },
}
</script>
