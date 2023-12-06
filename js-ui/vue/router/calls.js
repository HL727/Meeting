import { staticContentView } from '@/vue/router/helpers'

export default [
    {
        path: '/calls/',
        name: 'calls_list',
        component: () => import(/* webpackChunkName: "calls" */ '@/vue/views/call/CallsList'),
    },
    {
        path: '/calls/pexip/:id',
        name: 'call_details_pexip',
        props: true,
        component: () => import(/* webpackChunkName: "calls" */ '@/vue/views/call/CallControl'),
    },
    staticContentView('/calls/:id', 'calls_details'),
]
