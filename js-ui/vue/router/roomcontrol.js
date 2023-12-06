import { staticContentView } from '@/vue/router/helpers'

export default [
    {
        path: '/epm/roomcontrol/',
        name: 'control_list',
        component: () => import(/* webpackChunkName: "controls" */ '@/vue/views/roomcontrol/ControlList'),
    },
    staticContentView('/epm/roomcontrol/:id', 'control_details'),
]
