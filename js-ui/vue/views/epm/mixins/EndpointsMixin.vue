<script>
import { $gettext, $gettextInterpolate } from '@/vue/helpers/translate'

import EndpointStatus from '@/vue/components/epm/EndpointStatus'
import EndpointUptime from '@/vue/components/epm/EndpointUptime'
import { mapTextPath } from '@/vue/helpers/tree'

export default {
    components: {
        EndpointStatus,
        EndpointUptime,
    },
    filters: {
        timesince(d) {
            const diff = new Date().getTime() - new Date(d).getTime()
            if (diff < 60 * 60 * 1000) {
                return $gettextInterpolate($gettext('%{ diff } min'), { diff: diff / (60 * 1000) })
            }
            return d.replace(/\.\d+/, '')
        },
    },
    data() {
        return {
            endpointsLoading: false
        }
    },
    computed: {

        endpoints() {
            const organizations = this.$store.state.organization.units || {}
            const empty = '<empty>'
            return this.$store.getters['endpoint/endpoints'].map(e => ({
                ...e,
                organizationPath: e.org_unit ? mapTextPath(e.org_unit, organizations, 'name') : empty,
            }))
        },
    },
    mounted() {
        return this.reloadEndpoints()
    },
    methods: {
        initEndpoints() { true },
        reloadEndpoints() {
            this.endpointsLoading = true
            this.$emit('loading')

            return this.$store.dispatch('endpoint/getEndpoints').then(() => {
                this.endpointsLoading = false
                this.$emit('refreshed')
                this.initEndpoints()
            })
        },
    },
}
</script>
