import { idIntProps } from '@/vue/router/helpers'

export default [
    {
        path: '/core/admin/provider/',
        name: 'provider_dashboard',
        component: () => import(/* webpackChunkName: "provider" */ '@/vue/views/provider/ProviderDashboard'),
    },
    {
        path: '/epm/admin/provider/',
        name: 'cloud_dashboard_epm',
        component: () => import(/* webpackChunkName: "provider" */ '@/vue/views/provider/CloudDashboard'),
    },
    {
        path: '/setup/msgraph/oauth/:id',
        name: 'msgraph_oauth',
        props: idIntProps,
        component: () => import(/* webpackChunkName: "provider" */ '@/vue/views/onboard/GraphOAuth'),
    },
    {
        path: '/setup/ews/oauth/:id',
        name: 'ews_oauth',
        props: idIntProps,
        component: () => import(/* webpackChunkName: "provider" */ '@/vue/views/onboard/EWSSetupOAuth'),
    },
]
