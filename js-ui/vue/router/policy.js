import { idIntProps } from '@/vue/router/helpers'

export default [
    {
        path: '/analytics/policy/report/',
        component: () => import(/* webpackChunkName: "policy" */ '@/vue/views/policy/PolicyStatistics'),
    },
    {
        path: '/analytics/policy/',
        component: () => import(/* webpackChunkName: "policy" */ '@/vue/views/policy/PolicyLimits'),
    },
    {
        path: '/policy/rules/',
        component: () => import(/* webpackChunkName: "policy" */ '@/vue/views/policy_rule/PolicyRuleList'),
        name: 'policy_rules',
    },
    {
        path: '/policy/rules/add/',
        component: () => import(/* webpackChunkName: "policy" */ '@/vue/views/policy_rule/PolicyRuleForm'),
        name: 'policy_rules_add',
    },
    {
        path: '/policy/rules/:id/',
        component: () => import(/* webpackChunkName: "policy" */ '@/vue/views/policy_rule/PolicyRuleList'),
        props: idIntProps,
        name: 'policy_rules_edit',
    },
    {
        path: '/debug/policy/log/',
        name: 'policy_log',
        component: () => import(/* webpackChunkName: "policy_log" */ '@/vue/views/policy/PolicyLogView'),
    },
]
