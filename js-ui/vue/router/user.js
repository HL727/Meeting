import { staticContentView } from '@/vue/router/helpers'
import {idIntProps} from './helpers'

export default [
    {
        path: '/users/',
        name: 'user_list',
        component: () => import(/* webpackChunkName: "user" */ '@/vue/views/user/UserList'),
    },
    {
        path: '/users/:id/pexip/',
        name: 'pexip_user_details',
        props: idIntProps,
        component: () => import(/* webpackChunkName: "user" */ '@/vue/views/user/PexipUser'),
    },
    staticContentView('/users/:id/', 'user_details'),
    staticContentView('/users/:id/edit/', 'user_edit'),
    staticContentView('/users/changes/', 'user_changes'),
]
