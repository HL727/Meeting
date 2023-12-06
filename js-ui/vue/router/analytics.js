export default [
    {
        path: '/analytics/',
        name: 'analytics_dashboard',
        component: () => import(/* webpackChunkName: "stats" */ '@/vue/views/statistics/Dashboard'),
    },
    {
        path: '/stats/',
        component: () => import(/* webpackChunkName: "stats" */ '@/vue/views/statistics/CallStatistics'),
    },
    {
        path: '/epm/room_analytics/',
        name: 'epm_room_analytics',
        component: () => import(/* webpackChunkName: "stats" */ '@/vue/views/statistics/RoomStatistics'),
    },
    {
        path: '/analytics/calls/',
        name: 'analytics_calls',
        component: () => import(/* webpackChunkName: "stats" */ '@/vue/views/statistics/MultiTenantStatistics'),
    },
    {
        path: '/analytics/stats/',
        name: 'analytics_stats',
        component: () => import(/* webpackChunkName: "stats" */ '@/vue/views/statistics/MultiTenantStatistics'),
    },
    {
        path: '/analytics/rooms/',
        name: 'analytics_rooms',
        props: {
            multitenant: true,
        },
        component: () => import(/* webpackChunkName: "stats" */ '@/vue/views/statistics/RoomStatistics'),
    },

]
