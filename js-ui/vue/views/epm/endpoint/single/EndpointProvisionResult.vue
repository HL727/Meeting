<template>
    <v-dialog
        v-model="resultDialog"
        scrollable
        :max-width="1400"
    >
        <!-- Result dialog -->
        <v-card>
            <v-card-title>
                <translate>Resultat</translate>
            </v-card-title>
            <v-divider />
            <v-card-text>
                <ErrorMessage :error="error" />
                <EndpointTaskGrid
                    :endpoint-id="endpointId"
                    :provision-id="provisionId"
                    :hidden="!resultDialog"
                />
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-spacer />
                <v-btn
                    v-close-dialog
                    color="red"
                    text
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
import EndpointTaskGrid from '@/vue/components/epm/endpoint/EndpointTaskGrid'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

export default {
    name: 'EndpointProvisionResult',
    components: {ErrorMessage, EndpointTaskGrid },
    props: {
        endpoints: { type: Array, required: false, default() { return [] }},
        value: Boolean,
        configuration: { type: Array, required: false, default() { return [] }},
        commands: { type: Array, required: false, default() { return [] }},
        provisionData: { type: Object, required: false, default() { return {} }},
    },
    data() {
        return {
            resultDialog: false,
            provisionId: null,
            error: null,
            resultLoading: false,
        }
    },
    computed: {
        endpointIds() {
            return (this.endpoints || []).map(e => e.id || e)
        },
        endpointId() {
            if (this.endpointIds.length == 1) return this.endpointIds[0]
            return null
        }
    },
    watch: {
        value(val) {
            this.resultDialog = val
        },
        resultDialog(val) {
            this.$emit('input', val)
        },
        resultLoading(val) {
            this.$emit('update:loading', val)
        },
        error(val) {
            this.$emit('update:error', val)
        }
    },
    methods: {
        serializeData() {
            const data = this.provisionData || {}
            if (!data.configuration && this.configuration) data.configuration = this.configuration
            if (!data.commands && this.commands) data.commands = this.commands
            return data
        },
        apply(provisionData) {

            this.resultDialog = false
            this.provisionId = null
            this.resultLoading = true
            this.error = null

            setTimeout(() => {
                if (!this.error) this.resultDialog = true
            }, 500)

            return this.$store
                .dispatch('endpoint/provision', { endpoints: this.endpointIds, ...provisionData })
                .then(response => {
                    this.resultDialog = true
                    this.provisionId = response.id
                }).catch(e => {
                    this.error = e
                    this.resultDialog = true
                    this.resultLoading = false
                    throw e
                }).then(() => this.resultLoading = false)
        },
    }
}
</script>
