<template>
    <v-form
        v-model="formValid"
        @submit.prevent="updateUnit"
    >
        <v-card :loading="formLoading">
            <v-card-title>
                <translate v-if="unitForm.id">
                    Redigera grupp
                </translate>
                <translate v-else>
                    Lägg till grupp
                </translate>
            </v-card-title>
            <v-divider />
            <v-card-text>
                <v-text-field
                    v-model="unitForm.name"
                    :label="$gettext('Namn')"
                    aria-required
                    :error-messages="errors.name ? errors.name : []"
                    :rules="rules.name"
                />

                <OrganizationPicker
                    v-model="unitForm.parent"
                    single
                    :label="$gettext('Välj förälder')"
                    :error-messages="errors.parent ? errors.parent : []"
                    hide-add-new
                />
            </v-card-text>
            <v-divider />
            <v-alert
                v-if="error"
                type="error"
                tile
            >
                {{ error }}
            </v-alert>
            <v-card-actions>
                <v-btn
                    type="submit"
                    :disabled="!formValid"
                    color="primary"
                >
                    <translate>Spara</translate>
                </v-btn>
                <v-spacer />
                <v-btn
                    v-close-dialog
                    text
                    color="red"
                    @click="clearForm"
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
import { CloseDialogMixin } from '@/vue/helpers/dialog'
import { $gettext } from '@/vue/helpers/translate'
export default {
    components: {
        OrganizationPicker: () => import('@/vue/components/organization/OrganizationPicker'),
    },
    mixins: [CloseDialogMixin],
    props: {
        editId: { type: Number, default: null },
        parent: { type: Number, default: null },
    },
    data() {
        return {
            unitForm: {
                id: this.editId,
                name: '',
                parent: this.parent,
            },
            formValid: false,
            formLoading: false,
            error: '',
            errors: {},
            rules: {
                name: [x => (x ? true : $gettext('Detta fält måste fyllas i'))],
            },
        }
    },
    watch: {
        'form.name': function() {
            this.errors.name = null
        },
        editId(newValue) {
            newValue ? this.editUnit(newValue) : this.clearForm()
        },
        parent(newValue) {
            if (newValue) this.unitForm.parent = newValue
        },
    },
    mounted() {
        if (this.editId) this.editUnit(this.editId)
    },
    methods: {
        updateUnit() {
            const { id } = this.unitForm
            const action = id
                ? this.$store.dispatch('organization/updateUnit', { id, ...this.unitForm })
                : this.$store.dispatch('organization/addUnit', this.unitForm)

            this.formLoading = true
            action
                .then(() => {
                    this.formLoading = false
                    this.$emit('saved')
                    this.closeDialog()
                    this.unitForm.name = ''
                    this.unitForm.id = null
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
        clearForm() {
            this.$emit('cancel')
        },
        editUnit(id) {
            return this.$store.dispatch('organization/getUnit', id).then(unit => (this.unitForm = unit))
        },
    },
}
</script>
