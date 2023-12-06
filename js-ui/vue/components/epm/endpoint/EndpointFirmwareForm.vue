<template>
    <v-form
        ref="form"
        v-model="formValid"
        @submit.prevent="submit"
    >
        <v-card>
            <v-card-title>
                <translate>Ladda upp firmware</translate>
            </v-card-title>
            <v-divider />
            <v-card-text>
                <v-file-input
                    v-model="form.file"
                    display-size
                    required
                    :label="$gettext('Välj fil')"
                    :rules="rules.required"
                />

                <v-select
                    v-if="!endpoint"
                    v-model="form.models"
                    :label="$gettext('Modell', 'Modeller', 2)"
                    item-text="title"
                    :items="availableProducts"
                    multiple
                    required
                    :rules="rules.models"
                />

                <v-text-field
                    v-model="form.version"
                    :label="$gettext('Version')"
                    required
                    :rules="rules.required"
                />

                <v-alert
                    v-if="fileInvalid"
                    type="warning"
                >
                    <translate>
                        Filnamn bör ha ändelse .pkg eller .cop.sgn för att kunna installeras korrekt
                    </translate>
                </v-alert>

                <v-checkbox
                    v-if="displayGlobal"
                    v-model="form.is_global"
                    :label="$gettext('Visa för alla tenants')"
                />
            </v-card-text>

            <v-divider />
            <v-progress-linear
                :active="!!uploading"
                :value="uploading"
            />
            <v-card-actions>
                <v-btn
                    :disabled="!!uploading"
                    color="primary"
                    type="submit"
                >
                    <translate>Ladda upp</translate>
                </v-btn>
                <v-spacer />
                <ErrorMessage :error="error" />
                <v-btn
                    v-close-dialog
                    :disabled="!!uploading"
                    text
                    color="red"
                >
                    <translate>Avbryt</translate>
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
import { $gettext } from '@/vue/helpers/translate'
import {
    matchFilenameFirmwareModels,
} from '@/vue/store/modules/endpoint/helpers'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

export default {
    name: 'EndpointFirmwareForm',
    components: {ErrorMessage},
    props: {
        endpoint: { type: Object, required: false, default: null },
    },
    data() {
        const defaultForm = () => {
            return {
                manufacturer: this.endpoint ? this.endpoint.manufacturer : 10,
                models: this.endpoint ? [this.endpoint.product_name] : [],
                version: '',
                file: null,
                is_global: false,
            }
        }
        return {
            formValid: false,
            availableProducts: [],
            error: null,
            uploading: 0,
            form: { ...defaultForm() },
            defaultForm
        }
    },
    computed: {
        rules() {
            return {
                required: [value => (value ? true : $gettext('Det här fältet måste fyllas i'))],
                models: [value => (value && value.length ? true : $gettext('Det här fältet måste fyllas i'))],
            }
        },
        displayGlobal() {
            if (!this.$store.state.site.perms.staff) {
                return false
            }
            if (Object.values(this.$store.state.site.customers).length <= 1) {
                return false
            }
            return true
        },
        fileInvalid() {
            if (!this.form.file || !this.form.file.name) return false

            return !this.form.file.name.match(/\.pkg|(\.cop\.sgn)$/)
        },
        filnameVersion() {
            const m = this.form.file?.name?.match(/(tc|ce)([\d_]+)/)
            if (!m) return ''
            return m[2].replace(/_/g, '.')
        },
    },
    watch: {
        'form.file'(newValue) {
            if (newValue?.name && !this.form.version) this.form.version = this.filnameVersion
            if (newValue?.name && !this.form.models.length) this.form.models = this.matchModels()
        },
    },
    mounted() {
        return this.loadProducts()
    },
    methods: {
        matchModels() {
            return matchFilenameFirmwareModels(this.form.file?.name || '', this.availableProducts.map(p => p.title))
        },
        loadProducts() {
            return this.$store.dispatch('endpoint/getFilters').then(values => {
                this.availableProducts = values.product_name
                    .map(p => ({ id: p, title: p }))
                    .filter(p => !!p.title)
            })
        },
        submit() {
            if (!this.$refs.form.validate()) return
            return this.uploadFirmware()
        },
        resetForm() {
            this.form = { ...this.defaultForm() }
            this.$refs.form.resetValidation()
        },
        uploadFirmware() {
            const formData = new FormData()
            formData.append(
                'manufacturer',
                this.endpoint ? this.endpoint.manufacturer : this.form.manufacturer,
            )
            this.form.models.forEach(m => formData.append('models', m))
            formData.append('version', this.form.version)
            formData.append('file', this.form.file)
            if (this.form.is_global) {
                formData.append('is_global', '1')
            }

            const progress = percent => {
                this.uploading = percent * 100
            }

            return this.$store.dispatch('endpoint/uploadFirmware', { form: formData, progress }).then(() => {
                this.$emit('done')
                this.resetForm()
                this.uploading = 0
                this.createdSnackbar = true
            }).catch(e => {
                this.uploading = 0
                this.error = e
            })
        },
    },
}
</script>
