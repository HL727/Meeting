export default [
    {
        path: '/core/admin/demo-generator/',
        name: 'demo_generator',
        component: () => import(/* webpackChunkName: "debug" */ '@/vue/views/demo_generator/DemoGenerator'),
    },
    {
        path: '/epm/admin/demo-generator/',
        name: 'demo_generator_epm',
        component: () => import(/* webpackChunkName: "debug" */ '@/vue/views/demo_generator/DemoGenerator'),
    },
    {
        path: '/debug/',
        name: 'debug_dashboard',
        component: () => import(/* webpackChunkName: "debug" */ '@/vue/views/debug_views/Dashboard'),
    },
    {
        path: '/debug/api/:debugView',
        name: 'debug_api',
        props: true,
        component: () => import(/* webpackChunkName: "debug" */ '@/vue/views/debug_views/JsonAPIDebug'),
    },
]
