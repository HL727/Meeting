<template>
    <Page
        icon="mdi-brush"
        :title="$gettext('Temainställningar')"
        :loading="loading"
        :actions="[{ type: 'refresh', click: () => loadData() }]"
    >
        <template v-slot:content>
            <v-form @submit.prevent="save">
                <v-row>
                    <v-col
                        cols="12"
                        sm="7"
                        md="5"
                        class="order-1"
                    >
                        <h3 class="mt-4">
                            <span
                                v-if="theme.logo"
                                v-translate
                            >Ändra logotyp</span>
                            <span
                                v-else
                                v-translate
                            >Använd egen logotyp</span>
                        </h3>

                        <v-file-input
                            v-model="form.logo"
                            :label="$gettext('Egen logotyp')"
                            clearable
                        />

                        <v-checkbox
                            v-model="form.darkMode"
                            :label="$gettext('Använd mörk bakgrund där logotyp visas')"
                            hide-details
                        />

                        <v-divider class="my-4" />

                        <v-file-input
                            v-model="form.favicon"
                            :label="$gettext('Favicon')"
                            :hint="$gettext('Symbol som visas på fliken i webbläsaren')"
                            persistent-hint
                            clearable
                        />

                        <v-divider class="my-4" />

                        <v-btn
                            color="primary"
                            type="submit"
                            :loading="loading"
                            :disabled="loading"
                        >
                            <translate>Spara inställningar</translate>
                        </v-btn>
                    </v-col>
                    <v-col
                        cols="12"
                        sm="4"
                        class="order-sm-2"
                    >
                        <v-card
                            v-if="theme.logo"
                            class="mt-4"
                        >
                            <v-card-text :class="theme.darkMode ? 'grey darken-3 white--text' : ''">
                                <h3 class="mb-4">
                                    <translate>Uppladdad logotyp</translate>:
                                </h3>
                                <img
                                    :src="theme.logo"
                                    alt=""
                                    style="max-width:100%;width:10rem;"
                                >
                            </v-card-text>
                            <v-divider />
                            <v-card-actions>
                                <v-btn
                                    color="red darken-2"
                                    outlined
                                    :loading="loadingRemove"
                                    :disabled="loadingRemove"
                                    @click="removeLogo"
                                >
                                    <translate>Ta bort logotyp</translate>
                                </v-btn>
                            </v-card-actions>
                        </v-card>

                        <v-card
                            v-if="theme.favicon"
                            class="mt-4"
                        >
                            <v-card-text>
                                <h3 class="mb-4">
                                    <translate>Uppladdad favicon</translate>:
                                </h3>
                                <img
                                    :src="theme.favicon"
                                    alt=""
                                    style="max-width:100%;width:10rem;"
                                >
                            </v-card-text>
                            <v-divider />
                            <v-card-actions>
                                <v-btn
                                    color="red darken-2"
                                    outlined
                                    :loading="loadingRemoveIcon"
                                    :disabled="loadingRemoveIcon"
                                    @click="removeIcon"
                                >
                                    <translate>Ta bort favicon</translate>
                                </v-btn>
                            </v-card-actions>
                        </v-card>
                    </v-col>
                </v-row>
            </v-form>
        </template>
    </Page>
</template>

<script>
import Page from '@/vue/views/layout/Page'
export default {
    name: 'ThemeSettings',
    components: { Page },
    data() {
        return {
            form: {
                logo: null,
                favicon: null,
                darkMode: true
            },
            loading: false,
            uploading: 0,
            loadingRemove: false,
            loadingRemoveIcon: false,
        }
    },
    computed: {
        theme() {
            return this.$store.state.theme.theme
        }
    },
    mounted() {
        this.loadData()
    },
    methods: {
        save() {
            const formData = new FormData()

            if (this.form.logo) {
                formData.append('logo_image', this.form.logo, this.form.logo.name)
            }
            if (this.form.favicon) {
                formData.append('favicon', this.form.favicon, this.form.favicon.name)
            }
            formData.append('dark_mode', this.form.darkMode)

            const progress = percent => {
                this.uploading = percent * 100
            }

            this.loading = true
            return this.$store.dispatch('theme/updateTheme', { form: formData, progress }).then(() => {
                this.loading = false
                this.form.logo = null
                this.form.favicon = null
                this.uploading = 0
            })
        },
        removeLogo() {
            this.loadingRemove = true
            return this.$store.dispatch('theme/updateTheme', { form: { logo_image: null } }).then(() => {
                this.loadingRemove = false
            })
        },
        removeIcon() {
            this.loadingRemoveIcon = true
            return this.$store.dispatch('theme/updateTheme', { form: { favicon: null } }).then(() => {
                this.loadingRemoveIcon = false
            })
        },

        loadData() {
            this.loading = true

            return this.$store.dispatch('theme/getTheme').then(formValues => {
                this.loading = false

                this.form = {
                    darkMode: formValues.dark_mode
                }
            })
        }
    },
}
</script>
