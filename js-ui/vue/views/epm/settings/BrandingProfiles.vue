<template>
    <Page
        icon="mdi-image-outline"
        :title="$gettext('Brandingprofiler')"
        :actions="[
            { icon: 'mdi-plus', click: () => (addUpdateDialog = true) },
            { type: 'refresh', click: () => loadData() }
        ]"
        :loading="loading"
    >
        <template v-slot:content>
            <v-data-table
                :headers="headers"
                :items="profiles"
                :loading="loading"
            >
                <template
                    v-for="type in types"
                    v-slot:[`item.files.${type.name}`]="{ item }"
                >
                    <a
                        v-if="item[`file${type.name}`]"
                        :key="type.name"
                        href="#"
                        @click.prevent="previewUrl = item[`file${type.name}`]"
                    >
                        <v-img
                            :src="item[`file${type.name}`]"
                            class="ma-2"
                            width="64"
                        />
                    </a>
                    <v-icon
                        v-else
                        :key="type.name"
                        color="grey lighten-2"
                    >
                        mdi-close
                    </v-icon>
                </template>

                <template v-slot:item.action="{ item }">
                    <v-btn
                        icon
                        @click="editId = item.id"
                    >
                        <v-icon>mdi-pencil</v-icon>
                    </v-btn>
                    <v-btn-confirm
                        icon
                        @click="removeProfile(item.id)"
                    >
                        <v-icon>mdi-delete</v-icon>
                    </v-btn-confirm>
                </template>
            </v-data-table>

            <v-dialog
                :value="!!previewUrl"
                scrollable
                :max-width="420"
                @input="previewUrl = null"
            >
                <v-card>
                    <v-card-title>
                        <translate>Förhandsvisning</translate>
                    </v-card-title>
                    <v-divider />
                    <v-card-text>
                        <v-img
                            class="mt-4"
                            :src="previewUrl"
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-actions>
                        <v-spacer />
                        <v-btn
                            v-close-dialog
                            text
                            color="red"
                        >
                            <translate>Stäng</translate>
                            <v-icon
                                right
                                dark
                            >
                                mdi-close
                            </v-icon>
                        </v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>

            <v-dialog
                :value="!!editId"
                scrollable
                :max-width="420"
                @input="editId = null"
            >
                <BrandingProfileForm
                    :edit-id="editId"
                    :refresh="!!editId"
                />
            </v-dialog>

            <v-dialog
                v-model="addUpdateDialog"
                scrollable
                :max-width="420"
                @input="$refs.addForm.clear()"
            >
                <BrandingProfileForm
                    ref="addForm"
                    :refresh="addUpdateDialog"
                />
            </v-dialog>
        </template>
    </Page>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import Page from '@/vue/views/layout/Page'
import BrandingProfileForm from './BrandingProfileForm'
import VBtnConfirm from '@/vue/components/VBtnConfirm'

export default {
    name: 'BrandingProfiles',
    components: { Page, BrandingProfileForm, VBtnConfirm },
    data() {
        return {
            loading: false,
            addUpdateDialog: false,
            editId: null,
            previewUrl: null
        }
    },
    computed: {
        types() {
            return Object.values(this.$store.state.endpoint_branding.types)
        },
        headers() {
            const activeHeaders = [
                { text: $gettext('Namn'), value: 'name' },
                ...this.types.map(t => {
                    return {
                        text: t.label,
                        value: `files.${t.name}`,
                        sortable: false
                    }
                })
            ]
            activeHeaders.push({ text: '', value: 'action', align: 'end', sortable: false })
            return activeHeaders
        },
        profiles() {
            return Object.values(this.$store.state.endpoint_branding.profiles)
                .map(item => {
                    const newItem = {...item}
                    this.types.forEach(t => {
                        newItem[`file${t.name}`] = (item.files.find(f => f.type === t.id) || {}).file
                    })
                    return newItem
                })
        },
    },
    mounted() {
        this.loadData()
        this.$store.dispatch('endpoint_branding/loadFileTypes')
    },
    methods: {
        dataLoaded() {
            this.loading = false
        },
        async loadData() {
            this.loading = true
            await this.$store.dispatch('endpoint_branding/loadProfiles')
            this.dataLoaded()
        },
        removeProfile(id) {
            this.loading = true
            return this.$store.dispatch('endpoint_branding/removeProfile', id).then(() => {
                this.dataLoaded()
            })
        },
    },
}
</script>
