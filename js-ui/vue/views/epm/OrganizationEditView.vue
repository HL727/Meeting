<template>
    <Page
        icon="mdi-file-tree"
        :title="$gettext('Organisationsträd')"
        :actions="[
            { icon: 'mdi-plus', click: () => (addNewDialog = true) },
            { type: 'refresh', click: () => loadData() }
        ]"
        :loading="loading"
    >
        <template v-slot:content>
            <OrganizationTree
                ref="tree"
                enable-edit
                single
                :search-attr="{outlined: true, dense: true, class: 'mb-4', style: 'max-width: 20rem;'}"
                class="mt-5"
                style="margin: 0 -16px;max-width: 50rem"
                hoverable
                force-load
                :show-reload="true"
                open-all
                @refreshed="loading = false"
            >
                <template v-slot:action />
            </OrganizationTree>
            <v-dialog
                v-model="addNewDialog"
                scrollable
                :max-width="420"
            >
                <UnitForm />
            </v-dialog>
        </template>
    </Page>
</template>

<script>
import OrganizationTree from '../../components/organization/OrganizationTree'
import UnitForm from '../../components/organization/UnitForm'
import Page from '@/vue/views/layout/Page'

export default {
    name: 'OrganizationEditView',
    components: { Page, UnitForm, OrganizationTree },
    data() {
        return {
            loading: true,
            addNewDialog: false
        }
    },
    methods: {
        loadData() {
            this.loading = true
            this.$refs.tree.loadData()
        }
    }
}
</script>

