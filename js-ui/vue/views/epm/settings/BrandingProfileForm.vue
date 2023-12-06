<template>
    <v-form @submit.prevent="save">
        <v-card>
            <v-card-title>
                <span v-if="id"><translate>Redigera profil</translate></span>
                <span v-else><translate>Lägg till profil</translate></span>
            </v-card-title>
            <v-divider />
            <v-card-text v-if="!loading">
                <v-text-field
                    v-model="form.name"
                    :label="$gettext('Namn')"
                    :disabled="saving"
                />
            </v-card-text>
            <v-progress-linear
                v-if="loading"
                indeterminate
                color="primary"
            />
            <template v-else-if="id">
                <v-divider />
                <v-list>
                    <template
                        v-for="(file, index) in files"
                    >
                        <v-divider
                            v-if="index > 1"
                            :key="index"
                        />
                        <v-list-item
                            :key="`file-type-${file.type}`"
                            class="py-2"
                        >
                            <template v-if="file.file">
                                <v-list-item-avatar v-if="typeof file.file == 'string'">
                                    <v-img
                                        :src="file.file"
                                        width="64"
                                        height="64"
                                    />
                                </v-list-item-avatar>

                                <v-list-item-content>
                                    <v-list-item-title>
                                        {{ types[file.type].label || types[file.type].name }}
                                    </v-list-item-title>
                                    <v-list-item-subtitle v-if="typeof file.file == 'object'">
                                        {{ file.file.name }}
                                    </v-list-item-subtitle>
                                </v-list-item-content>

                                <div>
                                    <v-btn
                                        fab
                                        small
                                        color="error"
                                        :disabled="saving"
                                        @click="file.file = null"
                                    >
                                        <v-icon>mdi-close</v-icon>
                                    </v-btn>
                                    <v-tooltip
                                        :max-width="500"
                                        bottom
                                    >
                                        <template v-slot:activator="{ on }">
                                            <v-icon
                                                class="mx-2"
                                                v-on="on"
                                            >
                                                {{ types[file.type].name == 'Background' ? 'mdi-alert-circle' : 'mdi-information' }}
                                            </v-icon>
                                        </template>
                                        <span>{{ types[file.type].help_text }}</span>
                                    </v-tooltip>
                                </div>
                            </template>
                            <template v-else>
                                <v-list-item-content class="py-0">
                                    <v-file-input
                                        v-model="file.file"
                                        :label="types[file.type].label || types[file.type].name"
                                        :disabled="saving"
                                        hide-details
                                        show-size
                                        accept=".jpg,.png,image/jpeg"
                                        clearable
                                        filled
                                    >
                                        <template v-slot:append-outer>
                                            <v-tooltip
                                                :max-width="500"
                                                bottom
                                            >
                                                <template v-slot:activator="{ on }">
                                                    <v-icon
                                                        class="mr-2"
                                                        v-on="on"
                                                    >
                                                        {{ types[file.type].name == 'Background' ? 'mdi-alert' : 'mdi-information' }}
                                                    </v-icon>
                                                </template>
                                                <span>{{ types[file.type].help_text }}</span>
                                            </v-tooltip>
                                        </template>
                                    </v-file-input>
                                </v-list-item-content>
                            </template>
                        </v-list-item>
                    </template>
                </v-list>
            </template>

            <ErrorMessage :error="error" />
            <v-divider />

            <v-alert
                v-if="sizeWarning"
                type="warning"
            >
                <translate>Det är rekommenderat att hålla filstorleken under 4MB</translate>
            </v-alert>

            <v-alert
                v-model="successAlert"
                tile
                dense
                dismissible
                border="top"
                type="success"
                class="mb-0"
            >
                {{ $gettext('Sparad') }}
            </v-alert>
            <v-progress-linear
                v-if="saving"
                indeterminate
                color="primary"
            />
            <v-card-actions>
                <v-btn
                    v-if="id"
                    class="mr-2"
                    color="primary"
                    type="submit"
                    :loading="saving"
                >
                    <translate>Uppdatera</translate>
                </v-btn>
                <v-btn
                    v-else
                    color="primary"
                    type="submit"
                    :loading="saving"
                >
                    <translate>Lägg till</translate>
                </v-btn>

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
    </v-form>
</template>
<script>
import { readFile } from '@/vue/helpers/file'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

function emptyFiles(types) {
    const files = {}
    Object.values(types).forEach(
        type =>
            (files[type.id] = {
                file: null,
                use_standard: true,
                type: type.id,
            })
    )
    return files
}

export default {
    name: 'BrandingProfileForm',
    components: {ErrorMessage},
    props: {
        editId: { type: Number, default: null },
        refresh: { type: Boolean, default: false }
    },
    data() {
        return {
            id: this.editId,
            form: {
                name: '',
            },
            files: {},
            successAlert: false,
            loading: false,
            saving: false,
            error: null,
        }
    },
    computed: {
        types() {
            return this.$store.state.endpoint_branding.types
        },
        sizeWarning() {
            let result = false
            Object.values(this.files).forEach(file => {
                if (file.file && file.file.size && file.file.size > 4 * 1024 * 1024) result = true
            })
            return result
        }
    },
    watch: {
        editId(newValue) {
            newValue ? this.editProfile(newValue) : this.clearForm()

            this.successAlert = false
        },
        refresh() {
            this.successAlert = false
        }
    },
    mounted() {
        return this.$store.dispatch('endpoint_branding/loadFileTypes').then(() => {
            this.files = emptyFiles(this.types)

            if (this.editId) this.editProfile(this.editId)
        })
    },
    methods: {
        clear() {
            this.id = null
            this.form.name = ''
            this.files = emptyFiles(this.types)
        },
        save() {
            const { id } = this
            const form = { ...this.form, files: [] }
            const loaders = []

            if (id) {
                Object.values(this.files).forEach(file => {
                    if (file.file && typeof file.file == 'object') {
                        loaders.push(readFile(file.file).then(data => {
                            form.files.push({ ...file, file: data })
                        }))
                    } else if (file.file) {
                        form.files.push({ ...file, file: '', use_standard: false })
                    } else {
                        form.files.push({ ...file, file: '', use_standard: true })
                    }
                })
            }

            this.successAlert = false
            this.saving = true

            return Promise.all(loaders)
                .then(() => {
                    return id
                        ? this.$store.dispatch('endpoint_branding/updateProfile', { id, ...form })
                        : this.$store.dispatch('endpoint_branding/createProfile', form)
                })
                .then(response => {
                    this.$emit('saved')
                    this.handleResponse(response)
                    this.saving = false
                    this.id = response.id

                    if (id) {
                        this.successAlert = true
                    }
                }).catch(e => this.error = e)
        },
        clearForm() {
            this.$emit('cancel')
        },
        handleResponse(profile) {
            this.form = { ...profile, files: emptyFiles(this.types) }
            ;(profile.files || []).forEach(f => {
                this.files[f.type] = { ...f }
            })
        },
        editProfile(id) {
            this.clear()
            this.id = id
            this.loading = true
            return this.$store.dispatch('endpoint_branding/getProfile', id).then(t => {
                this.loading = false
                this.handleResponse(t)
            })
                .catch(e => this.error = e)
        },
        removeProfile(id) {
            return this.$store.dispatch('endpoint_branding/removeProfile', id)
        },
    },
}
</script>
