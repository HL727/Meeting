<script>
import { globalEmit } from '@/vue/helpers/events'

export default {
    data() {
        return {
            loading: false,
            searchTimeout: null
        }
    },
    methods: {
        setLoading(value) {
            globalEmit(this, 'loading', value)
            this.loading = value
        },
        searchDebounce(reset=false) {
            if (this.pagination && reset) {
                this.pagination.page = 1
            }

            clearTimeout(this.searchTimeout)

            this.searchTimeout = setTimeout(() => {
                if (this.loading) {
                    this.searchDebounce(reset)
                }
                else {
                    this.newSearch(reset)
                }
            }, 300)
        },
    }
}
</script>
