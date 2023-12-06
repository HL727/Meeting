<template>
    <v-card>
        <v-card-title>
            <translate v-if="groupForm.id">
                Redigera grupp
            </translate>
            <translate v-else>
                Lägg till grupp
            </translate>
        </v-card-title>
        <v-divider />
        <v-card-text>
            <v-text-field
                v-model="groupForm.title"
                :label="$gettext('Namn')"
            />

            <GroupPicker
                v-model="groupForm.parent"
                :items="groups"
                single
                :label="$gettext('Välj förälder')"
            />
        </v-card-text>
        <v-divider />
        <v-card-actions>
            <v-btn
                color="primary"
                @click="updateGroup"
            >
                <translate>Spara</translate>
            </v-btn>
            <v-spacer />
            <v-btn
                v-close-dialog
                color="red"
                text
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
</template>

<script>
import { CloseDialogMixin } from '@/vue/helpers/dialog'

export default {
    name: 'GroupForm',
    components: {
        GroupPicker: () => import('@/vue/components/epm/addressbook/GroupPicker'),
    },
    mixins: [CloseDialogMixin],
    props: {
        groups: { type: Array, default: () => [] },
        editId: { type: Number, default: null },
        parent: { type: Number, default: null },
    },
    data() {
        return {
            groupForm: {
                id: this.editId,
                title: '',
                parent: this.parent,
            },
        }
    },
    watch: {
        editId(newValue) {
            newValue ? this.editGroup(newValue) : this.clearForm()
        },
        parent(newValue) {
            if (newValue) this.groupForm.parent = newValue
        },
    },
    mounted() {
        if (this.editId) this.editGroup(this.editId)
    },
    methods: {
        updateGroup() {
            const { id } = this.groupForm
            const action = id
                ? this.$store.dispatch('addressbook/updateGroup', { id, ...this.groupForm })
                : this.$store.dispatch('addressbook/addGroup', this.groupForm)

            return action.then(() => {
                this.$emit('saved')
                this.closeDialog()
            })
        },
        clearForm() {
            this.$emit('cancel')
        },
        editGroup(id) {
            return this.$store.dispatch('addressbook/getGroup', id).then(group => (this.groupForm = group))
        },
    },
}
</script>
