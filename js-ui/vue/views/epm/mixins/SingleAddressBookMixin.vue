<script>
import { $gettext } from '@/vue/helpers/translate'

import AddressBooksMixin from '@/vue/views/epm/mixins/AddressBooksMixin'

export default {
    filters: {},
    mixins: [AddressBooksMixin],
    props: {
        id: { type: Number, required: true },
    },
    computed: {
        addressbook() {
            return this.$store.state.addressbook.books[this.id] || {}
        },
    },
    mounted() {
        return this.$store.dispatch('addressbook/getAddressBook', this.id).then(() => {
            this.setBreadCrumb()
        })
    },
    methods: {
        setBreadCrumb(current = null) {
            const addressbook = this.addressbook
            const crumbs = [
                { title: $gettext('AddressBooks'), to: { name: 'epm_list' } },
                {
                    to: { name: 'addressbook_details', params: [addressbook.id] },
                    title: addressbook.hostname || addressbook.ip,
                },
            ]

            if (current) {
                crumbs.push(current)
            }
            this.$store.commit('site/setBreadCrumb', crumbs)
        },
    },
}
</script>
