<template>
    <div>
        <div
            v-if="error"
            class="ma-8"
        >
            <v-alert type="warning">
                <translate>Ett fel uppstod.</translate>
                <span
                    v-if="endpoint.has_direct_connection"
                    v-translate
                >Kontrollera din anslutning och försök igen</span>
                <span
                    v-else
                    v-translate
                >Aktiv anslutning saknas, och ingen cachad data hittades</span>
            </v-alert>
            <v-textarea
                readonly
                light
                class="mt-4"
                :label="$gettext('Felinformation')"
                :value="error"
                rows="2"
            />
        </div>
        <v-tabs
            :vertical="$vuetify.breakpoint.mdAndUp"
            background-color="grey lighten-4"
        >
            <v-tab
                v-for="node in settingObjects(configuration)"
                :key="node.title"
                class="text-left justify-start"
            >
                {{ node.title }}
                <v-icon
                    v-if="rootElements.indexOf(node.title) != -1"
                    class="ml-auto"
                >
                    mdi-check
                </v-icon>
            </v-tab>
            <v-tab-item
                v-for="node in settingObjects(configuration)"
                :key="node.title + 'item'"
            >
                <v-card flat>
                    <v-card-title>{{ node.title }}</v-card-title>
                    <v-card-text>
                        <ConfigurationTree
                            :is-root="true"
                            :filter="filter"
                            :parent="node"
                            :tree="node.setting ? [node.orig] : node.children"
                            :endpoint-id="endpoint.id"
                        />
                    </v-card-text>
                </v-card>
            </v-tab-item>
        </v-tabs>
    </div>
</template>

<script>
import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import ConfigurationTree from '@/vue/components/epm/endpoint/ConfigurationTree'

export default {
    name: 'EndpointConfigurationForm',
    components: {
        ConfigurationTree,
    },
    mixins: [SingleEndpointMixin],
    data() {
        return {
            loading: true,
            error: '',
            templateDialog: false,
        }
    },
    computed: {
        configuration() {
            return this.$store.state.endpoint.configuration[this.id]?.data || []
        },
        activeConfiguration() {
            return Object.values(this.$store.state.endpoint.activeConfiguration)
        },
        templates() {
            return Object.values(this.$store.state.endpoint.templates) || []
        },
        rootElements() {
            return Object.values(this.$store.state.endpoint.activeConfiguration).map(config => config.path[0].replace(/\[\d+\]$/, ''))
        },
    },
    watch: {
        activeConfiguration(newValue) {
            this.$emit('input', newValue)
        },
    },
    mounted() {
        return this.loadData()
    },
    methods: {
        settingObjects(nodes) {
            const filtered = !this.filter
                ? nodes
                : nodes.filter(
                    node =>
                        JSON.stringify(node)
                            .toLowerCase()
                            .indexOf(this.filter.toLowerCase()) != -1
                )
            return filtered.map(node => {
                const [title, options, children, setting] = node
                return { title, options, children, setting, orig: node }
            })
        },
        loadData() {
            this.error = ''
            this.loading = true
            return Promise.all([
                this.$store.dispatch('endpoint/getConfiguration', this.id),
                this.$store.dispatch('endpoint/getTemplates'),
            ]).then(() => {
                this.loading = false
                this.$emit('loaded')
            }).catch(e => {
                this.error = (e instanceof Array ? e : [e]).filter(e => e).map(e => e.toString()).join(', ')
                this.loading = false
                this.$emit('loaded')
            })
        },
    },
}
</script>
