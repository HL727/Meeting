<script>
import { $gettext } from '@/vue/helpers/translate'

import EndpointsMixin from '@/vue/views/epm/mixins/EndpointsMixin'
import { endpointStatusNames } from '@/vue/store/modules/endpoint/consts'
import { mapTextPath } from '@/vue/helpers/tree'

export default {
    filters: {
        timesince(d) {
            const diff = new Date().getTime() - new Date(d).getTime()
            if (diff < 60 * 60 * 1000) {
                return `${diff / (60 * 1000)} min`
            }
            return d.replace(/\.\d+/, '')
        },
    },
    mixins: [EndpointsMixin],
    props: {
        id: { type: Number, required: true },
        filter: { type: String, default: '' },
    },
    data() {
        return {
            endpointNotFound: false,
        }
    },
    computed: {
        endpoint() {
            const endpoint = this.$store.state.endpoint.endpoints[this.id] || {}
            const empty = '<empty>'
            return {
                ...endpoint,
                status_text: endpointStatusNames[endpoint.status_code],
                organizationPath: endpoint.org_unit ? mapTextPath(endpoint.org_unit, this.organizations, 'name') : empty,
            }
        },
        organizations() {
            return this.$store.state.organization.units
        },
    },
    mounted() {
        this.$store.dispatch('organization/refreshUnits')
        return this.requireEndpoint(this.id).then(() => {
            this.setBreadCrumb()
            this.endpointNotFound = false
        }).catch(e => {
            if (e.status == 404) {
                this.endpointNotFound = true
            } else {
                throw e
            }
        })
    },
    methods: {
        setBreadCrumb(current = null) {
            const endpoint = this.endpoint
            const crumbs = [
                { title: $gettext('Endpoints'), to: { name: 'epm_list' } },
                {
                    to: { name: 'endpoint_details', params: [endpoint.id] },
                    title: endpoint.hostname || endpoint.ip,
                },
            ]

            if (current) {
                crumbs.push(current)
            }
            this.$store.commit('site/setBreadCrumb', crumbs)
        },
        requireEndpoint(id) {
            return this.$store.dispatch('endpoint/requireEndpoint', id === undefined ? this.id : id)
        },
        getEndpoint(id) {
            return this.$store.dispatch('endpoint/getEndpoint', id === undefined ? this.id : id)
        },
    },
}
</script>
