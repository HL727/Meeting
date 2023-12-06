import { idIntProps } from '@/vue/router/helpers'

export default [
    {
        path: '/epm/',
        name: 'epm_dashboard',
        component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/Dashboard'),
    },
    {
        path: '/epm/firmware/',
        name: 'epm_firmware',
        component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/firmware/FirmwareList'),
    },
    {
        path: '/epm/bookings/',
        name: 'epm_bookings',
        component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/bookings/BookingList'),
    },
    {
        path: '/epm/statistics/calls/',
        name: 'epm_statistics',
        component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/EPMStatistics'),
    },
    {
        path: '/epm/statistics/rooms/',
        name: 'epm_statistics_rooms',
        component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/EPMRoomStatistics'),
    },
    {
        path: '/epm/people_count/',
        name: 'epm_statistics_people_count',
        component: () => import(/* webpackChunkName: "stats" */ '@/vue/views/epm/PeopleCount'),
    },
    {
        path: '/epm/endpoint/',
        component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/endpoint/ListWrapper'),
        children: [
            {
                path: '',
                name: 'epm_list',
                component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/endpoint/list/EndpointList'),
            },
            {
                path: 'tasks/',
                name: 'epm_task_list',
                component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/endpoint/list/EndpointTaskList'),
            },
            {
                path: 'incoming/',
                name: 'epm_incoming',
                component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/endpoint/EndpointIncomingList'),
            },
        ],
    },
    {
        path: '/epm/admin/proxies/',
        name: 'epm_proxies',
        component: () => import(/* webpackChunkName: "epm" */ '@/vue/views/epm/endpointproxy/ProxyList'),
    },

    // single

    {
        path: '/epm/endpoint/:id/',
        props: idIntProps,
        component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/SingleWrapper'),
        children: [
            {
                path: '',
                name: 'endpoint_details',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointDashboard'),
            },
            {
                path: '/epm/endpoint/:id/status/',
                name: 'endpoint_status',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointStatus'),
            },
            {
                path: '/epm/endpoint/:id/configuration/',
                name: 'endpoint_configuration',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointConfiguration'),
            },
            {
                path: '/epm/endpoint/:id/configuration/apply/',
                name: 'endpoint_configuration_apply',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointConfigurationApply'),
            },
            {
                path: '/epm/endpoint/:id/command/apply/',
                name: 'endpoint_command_apply',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointCommandApply'),
            },
            {
                path: '/epm/endpoint/:id/commands/',
                name: 'endpoint_commands',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointCommands'),
            },
            {
                path: '/epm/endpoint/:id/backup/',
                name: 'endpoint_backup',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointBackup'),
            },
            {
                path: '/epm/endpoint/:id/tasks/',
                name: 'endpoint_tasks',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointTasks'),
            },
            {
                path: '/epm/endpoint/:id/provision/',
                name: 'endpoint_provision',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointProvision'),
            },
            {
                path: '/epm/endpoint/:id/statistics/',
                name: 'endpoint_stats',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "epm_single_stats" */ '@/vue/views/epm/endpoint/single/EndpointStats'),
            },
        ],
    },

    // settings

    {
        path: '/epm/admin/settings/',
        component: () => import(/* webpackChunkName: "epm_settings" */ '@/vue/views/epm/settings/SettingsWrapper'),
        children: [
            {
                path: '',
                name: 'epm_settings',
                component: () => import(/* webpackChunkName: "epm_settings" */ '@/vue/views/epm/CustomerSettings'),
            },
        ],
    },
    {
        path: '/epm/admin/customers/',
        name: 'epm_customer_dashboard',
        component: () => import(/* webpackChunkName: "provider" */ '@/vue/views/customer/CustomerDashboard'),
    },
    {
        path: '/epm/admin/organization/',
        name: 'epm_organization',
        component: () => import(/* webpackChunkName: "epm_settings" */ '@/vue/views/epm/OrganizationEditView'),
    },
    {
        path: '/epm/admin/branding/',
        name: 'epm_branding',
        component: () => import(/* webpackChunkName: "epm_settings" */ '@/vue/views/epm/settings/BrandingProfiles'),
    },

    // Cockpit
    {
        path: '/epm/endpoint/:id/debug',
        name: 'endpoint_debug',
        props: idIntProps,
        component: () => import(/* webpackChunkName: "epm_single" */ '@/vue/views/epm/endpoint/single/EndpointDebug'),
    },

]
