<script>
import MeetingList from '@/vue/views/meeting/MeetingList'

export default {
    name: 'BookingsList',
    inheritAttrs: false,
    render(createElement) {
        const props = {
            onlyEndpoints: true,
            includeExternal: true,
            ...this.$attrs,
        }

        return createElement(MeetingList, { props, on: this.$listeners }, this.$children)
    },
}
</script>
