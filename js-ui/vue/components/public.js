export default {
    CoSpacePicker: () => import('./cospace/CoSpacePicker'),
    CoSpacesTabs: () => import('@/vue/components/cospace/CoSpacesTabs'),
    NumberSeriesGetter: () => import('./NumberSeriesGetter'),
    SipAddressPicker: () => import('@/vue/components/epm/endpoint/SipAddressPicker'),
    UserPicker: () => import('./user/UserPicker'),
    UserTabs: () => import('@/vue/components/user/UserTabs'),
    OrganizationPicker: () => import('@/vue/components/organization/OrganizationPicker'),
    DateTimePicker: () => import('@/vue/components/datetime/DateTimePicker'),
}
