<template>
    <div>
        <div v-if="loading">
            <v-progress-circular indeterminate />
        </div>
        <v-form
            v-if="!loading"
            ref="form"
            v-model="formValid"
            @submit.prevent="submit"
        >
            <v-text-field
                v-model="form.title"
                :error-messages="errors.title ? errors.title : []"
                :rules="rules.title"
                :label="$gettext('Namn')"
            />

            <v-checkbox
                v-model="isExternal"
                :label="$gettext('Extern adressbok')"
            />
            <div v-if="isExternal">
                <v-text-field
                    v-model="form.external_url"
                    :label="$gettext('URL för sökning (TMS SOAP)')"
                />
                <v-text-field
                    v-model="form.external_edit_url"
                    :label="$gettext('URL för extern redigering')"
                />
            </div>
        </v-form>
    </div>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

export default {
    props: {
        id: { type: Number, default: null, required: false },
    },
    data() {
        const initialData = { title: '', type: 0, external_url: '', external_edit_url: '' }

        return {
            loading: false,
            error: '',
            formLoading: false,
            isExternal: false,
            formValid: false,
            initialData,
            form: { ...initialData },
            rules: {
                title: [v => !!v || $gettext('Värdet måste fyllas i')],
            },
            errors: {},
        }
    },
    watch: {
        id() {
            this.loadObject()
        },
    },
    mounted() {
        this.loading = true
        return this.loadObject()
    },
    methods: {
        submit() {
            if (!this.$refs.form.validate()) return
            this.formLoading = true
            const { id } = this

            const formData = {
                ...this.form,
                type: this.isExternal ? 1 : 0,
            }

            const action = !id
                ? this.$store.dispatch('addressbook/createAddressBook', formData)
                : this.$store.dispatch('addressbook/updateAddressBook', {
                    id,
                    data: formData,
                })
            action
                .then(addressbook => {
                    this.formLoading = false
                    this.errors = {}
                    this.$emit('complete', addressbook)
                })
                .catch(e => {
                    this.formLoading = false
                    if (e.errors) {
                        this.errors = e.errors
                    } else {
                        this.error = e
                    }
                })
        },
        loadObject() {
            this.loading = true
            return (this.id
                ? this.$store.dispatch('addressbook/getAddressBook', this.id)
                : Promise.resolve(this.initialData || {})
            ).then(book => {
                this.form = { ...this.form, ...book }
                this.isExternal = this.form.type === 1
                this.error = null
                this.loading = false
            }).catch(e => {
                this.loading = false
                this.error = e
            })
        },
    },
}
</script>
