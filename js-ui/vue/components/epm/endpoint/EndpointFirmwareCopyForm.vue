<template>
    <v-form @submit.prevent="submit">
        <v-card>
            <v-card-title><translate>Kopiera</translate></v-card-title>
            <v-divider />
            <v-card-text>
                <v-select
                    v-model="form.models"
                    :label="$gettext('Produkt')"
                    item-text="title"
                    :items="availableProducts"
                    multiple
                    required
                    :rules="rules.models"
                />
                <v-checkbox
                    v-if="displayGlobal"
                    v-model="form.is_global"
                    :label="$gettext('Visa för alla tenants')"
                />
            </v-card-text>
            <v-divider />
            <v-card-actions>
                <v-btn
                    color="primary"
                    type="submit"
                >
                    <translate>Kopiera</translate>
                </v-btn>
                <v-spacer />
                <v-btn
                    v-close-dialog
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
import { closeDialog } from '@/vue/helpers/dialog'
import {matchFilenameFirmwareModels} from '@/vue/store/modules/endpoint/helpers'

export default {
    name: 'EndpointFirmwareCopyForm',
    props: {
        availableProducts: { type: Array, required: true, default: () => []},
        firmware: { type: Object, required: true, default: () => ({}) },
    },
    data() {
        return {
            form: {
                models: [],
                is_global: false,
            }
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
        }
    },
    mounted() {
        this.models = this.matchModels()
    },
    methods: {
        serializeForm() {
            return this.form
        },
        matchModels() {
            return matchFilenameFirmwareModels(this.firmware.orig_file_name || '', this.availableProducts.map(p => p.title))
        },
        async submit() {
            const result = await this.$store.dispatch('endpoint/copyFirmware', { firmwareId: this.firmware.id, ...this.serializeForm()})
            this.$emit('done', result)
            closeDialog(this.$vnode)
        },
    }
}
</script>
