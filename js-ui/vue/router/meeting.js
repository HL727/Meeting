import { staticContentView } from '@/vue/router/helpers'

export default [
    {
        path: '/meeting/',
        name: 'meetings_list',
        component: () => import(/* webpackChunkName: "meeting" */ '@/vue/views/meeting/MeetingList'),
    },
    staticContentView('/meeting/add/', 'meetings_add'),
    staticContentView('/epm/meetings/:id', 'meeting_debug_details_epm'),
    staticContentView('/meetings/:id', 'meeting_debug_details'),
]
