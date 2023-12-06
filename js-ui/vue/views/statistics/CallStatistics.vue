<template>
    <PageAnalytics
        ref="page"
        :title="$gettext('Samtalsstatistik')"
        icon="mdi-chart-bar"
        :show-servers="true"
        :enable-tenants="enableTenants"
    >
        <template v-slot:content="{ stats, graphs, loading }">
            <CallStatisticsDetails
                v-bind="{ stats, graphs, loading, extras }"
                show-meeting-rooms
                @refilter="$refs.page.refilter($event)"
                @summary="summary = $event"
            />
        </template>
    </PageAnalytics>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import PageAnalytics from '@/vue/views/layout/PageAnalytics'

import CallStatisticsDetails from '@/vue/components/statistics/CallStatisticsDetails'

export default {
    name: 'CallStatistics',
    components: {
        PageAnalytics,
        CallStatisticsDetails,
    },
    props: {
        enableTenants: Boolean,
    },
    data() {
        return {
            summary: {},
        }
    },
    computed: {
        extras() {
            if (!Object.keys(this.summary).length) return []

            return [
                {
                    label: $gettext('Timmar'),
                    value: parseInt(this.summary.cospace_total[0], 10)
                },
                {
                    label: $gettext('Gästtimmar'),
                    value: parseInt(this.summary.cospace_total[1], 10)
                },
                {
                    label: $gettext('Deltagare'),
                    value: parseInt(this.summary.cospace_total[2], 10)
                },
                {
                    label: $gettext('Unika samtal'),
                    value: parseInt(this.summary.cospace_total[3], 10)
                }
            ]
        }
    }
}
</script>
