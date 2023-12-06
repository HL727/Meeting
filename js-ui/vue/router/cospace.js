import { staticContentView } from '@/vue/router/helpers'
import {idIntProps} from './helpers'

export default [
    {
        path: '/cospaces/',
        name: 'cospaces_list',
        component: () => import(/* webpackChunkName: "cospace" */ '@/vue/views/cospace/CoSpaceList'),
    },
    {
        path: '/cospaces/:id/pexip/',
        name: 'pexip_cospaces_details',
        props: idIntProps,
        component: () => import(/* webpackChunkName: "cospace" */ '@/vue/views/cospace/PexipCoSpace'),
    },
    {
        path: '/cospaces/add/',
        name: 'cospaces_add',
        props: {
            addCoSpace: true,
        },
        component: () => import(/* webpackChunkName: "cospace" */ '@/vue/views/cospace/CoSpaceList'),
    },
    staticContentView('/cospaces/:id/', 'cospaces_details'),
    staticContentView('/cospaces/:id/invite/', 'cospaces_invite'),
    staticContentView('/webinar/', 'webinar'),
    staticContentView('/cospaces/changes/', 'cospaces_changes'),
    staticContentView('/cospaces/:id/edit/', 'cospaces_edit'),
]
