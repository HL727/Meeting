<template>
    <Page
        icon="mdi-download-network"
        :title="$gettext('Firmware')"
        :actions="pageActions"
    >
        <template v-slot:content>
            <FirmwareGrid
                ref="grid"
                :endpoint="null"
                :hide-title="true"
                @refreshed="refreshed"
            />
        </template>
    </Page>
</template>

<script>
import { globalEmit } from '@/vue/helpers/events'
import Page from '@/vue/views/layout/Page'
import FirmwareGrid from '@/vue/components/epm/endpoint/FirmwareGrid'

export default {
    components: {
        Page,
        FirmwareGrid,
    },
    computed: {
        pageActions() {
            return [
                {
                    icon: 'mdi-plus',
                    click: () => (this.$refs.grid.uploadDialog = true)
                },
                {
                    type: 'refresh',
                    click: () => this.$refs.grid.loadData()
                }
            ]
        }
    },
    methods: {
        refreshed() {
            globalEmit(this, 'loading', false)
        }
    }
}
</script>
