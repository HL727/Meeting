import { idIntProps } from '@/vue/router/helpers'

export default [
    {
        path: '/epm/addressbook/',
        name: 'addressbook_list',
        component: () => import(/* webpackChunkName: "addressbook" */ '@/vue/views/epm/addressbook/AddressBookList'),
    },
    {
        path: '/epm/addressbook/:id/',
        props: idIntProps,
        component: () => import(/* webpackChunkName: "addressbook" */ '@/vue/views/epm/addressbook/Index'),
        children: [
            {
                path: '',
                name: 'addressbook_details',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "addressbook" */ '@/vue/views/epm/addressbook/single/AddressBookDashboard'),
            },
            {
                path: 'sources/',
                name: 'addressbook_sources',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "addressbook" */ '@/vue/views/epm/addressbook/single/AddressBookSources'),
            },
            {
                path: 'edit/',
                name: 'addressbook_edit',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "addressbook" */ '@/vue/views/epm/addressbook/single/AddressBookEdit'),
            },
            {
                path: 'groups/',
                name: 'addressbook_groups',
                props: idIntProps,
                component: () => import(/* webpackChunkName: "addressbook" */ '@/vue/views/epm/addressbook/single/AddressBookGroups'),
            },
        ],
    },
]
