<script>
export default {
    components: {},
    filters: {},
    data() {
        return {
            addressbooksLoading: true
        }
    },
    computed: {
        addressBooks() {
            return this.$store.getters['addressbook/addressBooks']
        },
    },
    mounted() {
        this.reloadAddressBooks()
    },
    methods: {
        initAddressBooks() { true },
        reloadAddressBooks() {
            this.addressbooksLoading = true
            return this.$store.dispatch('addressbook/getAddressBooks').then(() => {
                this.addressbooksLoading = false
                this.initAddressBooks()
                this.$emit('refreshed')
            })
        },
    },
}
</script>
