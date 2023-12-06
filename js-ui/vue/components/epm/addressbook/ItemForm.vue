<template>
    <v-card>
        <v-card-title>
            <span>
                <translate v-if="editId">Redigera inlägg</translate>
                <translate v-else>Lägg till inlägg</translate>
            </span>
        </v-card-title>
        <v-divider />
        <v-card-text>
            <v-text-field
                v-model="itemForm.title"
                :label="$gettext('Namn')"
            />
            <v-text-field
                v-model="itemForm.description"
                :label="$gettext('Beskrivning')"
            />

            <GroupPicker
                v-model="itemForm.group"
                :label="$gettext('Grupp')"
                :items="groups"
            />

            <v-text-field
                v-model="itemForm.sip"
                :label="$gettext('SIP')"
            />
            <v-text-field
                v-model="itemForm.h323"
                :label="$gettext('H323')"
            />
            <v-text-field
                v-model="itemForm.h323_e164"
                :label="$gettext('H323 E164-alias')"
            />
            <v-text-field
                v-model="itemForm.tel"
                :label="$gettext('Telefonnummer')"
            />
        </v-card-text>
        <v-divider />
        <ErrorMessage :error="error" />
        <v-card-actions>
            <v-btn
                color="primary"
                @click="updateItem"
            >
                <translate v-if="editId">
                    Spara
                </translate>
                <translate v-else>
                    Lägg till
                </translate>
            </v-btn>
            <v-spacer />
            <v-btn
                v-close-dialog
                color="red"
                text
                @click="clearItem"
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
</template>

<script>
import GroupPicker from '@/vue/components/epm/addressbook/GroupPicker'
import { CloseDialogMixin } from '@/vue/helpers/dialog'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

export default {
    components: {
        ErrorMessage,
        GroupPicker,
    },
    mixins: [CloseDialogMixin],
    props: {
        groups: { type: Array, default: () => [] },
        editId: { type: Number, default: null },
        group: { type: Number, default: null },
    },
    data() {
        return {
            itemForm: this.emptyForm(),
            error: null,
        }
    },
    watch: {
        editId(newValue) {
            newValue ? this.editItem(newValue) : this.clearForm()
        },
        group(newValue) {
            if (newValue) this.itemForm.group = newValue
        },
    },
    mounted() {
        if (this.editId) this.editItem(this.editId)
    },
    methods: {
        emptyForm() {
            const firstGroup = this.groups && this.groups.length && !this.editId ? this.groups[0].id : null
            return {
                id: null,
                title: '',
                description: '',
                group: this.group ? this.group : firstGroup,
                sip: '',
                h323: '',
                h323_e164: '',
                tel: '',
            }
        },
        clearForm() {
            this.itemForm = this.emptyForm()
        },
        updateItem() {
            const { id } = this.itemForm
            const action = id
                ? this.$store.dispatch('addressbook/updateItem', { id, ...this.itemForm })
                : this.$store.dispatch('addressbook/addItem', this.itemForm)

            action.then(() => {
                this.$emit('saved')
                this.clearForm()
                this.closeDialog()
            }).catch(e => {
                this.error = e
            })
        },
        clearItem() {
            this.$emit('cancel')
        },
        editItem(id) {
            return this.$store.dispatch('addressbook/getItem', id).then(item => (this.itemForm = item))
        },
    },
}
</script>
