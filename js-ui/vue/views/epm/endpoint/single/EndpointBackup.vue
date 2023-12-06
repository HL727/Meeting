<template>
    <div>
        <v-data-table
            :headers="headers"
            :loading="loading"
            sort-by="ts_created"
            sort-desc
            :items="items"
        >
            <template v-slot:item.action="{ item }">
                <v-btn
                    :title="$gettext('Ladda hem')"
                    icon
                    @click="downloadBackup(item)"
                >
                    <v-icon>mdi-download</v-icon>
                </v-btn>
                <v-btn
                    :title="$gettext('Återställ')"
                    icon
                    @click="restoreBackup(item)"
                >
                    <v-icon>mdi-cube-send</v-icon>
                </v-btn>
                <v-btn-confirm
                    :title="$gettext('Ta bort')"
                    icon
                    :dialog-text="$gettext(`Är du säker på att du vill ta bort denna backup?`) + ' (' + item.slug + ')'"
                    @click="deleteBackup(item)"
                >
                    <v-icon>mdi-delete</v-icon>
                </v-btn-confirm>
            </template>
            <template v-slot:item.ts_created="{ item }">
                {{ item.ts_created|timestamp }}
            </template>
        </v-data-table>

        <v-snackbar v-model="createdSnackbar">
            <translate>En ny backup körs i bakgrunden</translate>
        </v-snackbar>
    </div>
</template>

<script>
import { GlobalEventBus } from '@/vue/helpers/events'
import { $gettext } from '@/vue/helpers/translate'

import VBtnConfirm from '@/vue/components/VBtnConfirm'

import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'

export default {
    components: {VBtnConfirm},
    mixins: [SingleEndpointMixin],
    data() {
        return {
            emitter: new GlobalEventBus(this),
            loading: true,
            headers: [
                {
                    text: $gettext('Namn'),
                    value: 'slug',
                },
                {
                    text: $gettext('Skapades'),
                    value: 'ts_created',
                },
                {
                    text: $gettext('Checksum'),
                    value: 'hash',
                },
                {
                    text: $gettext('Fel'),
                    value: 'error',
                    sortable: false,
                },
                { text: '', value: 'action', align: 'end', sortable: false },
            ],
            createdSnackbar: null,
        }
    },
    computed: {
        items() {
            return Object.values(this.$store.state.endpoint.backups || {}).filter(b => b.endpoint == this.id)
        },
    },
    mounted() {
        this.emitter.on('refresh', () => this.loadBackups())
        this.emitter.on('add', () => this.backup())

        this.loadBackups()
    },
    methods: {
        backup() {
            this.createdSnackbar = true
            return this.$store.dispatch('endpoint/backupEndpoint', this.id).then(() => {
                setTimeout(() => {
                    this.loadBackups()
                }, 3000)
            })
        },
        downloadBackup(item) {
            return this.$store.dispatch('endpoint/downloadBackup', item.id)
        },
        restoreBackup(item) {
            this.loading = true
            this.emitter.emit('loading', true)
            return this.$store.dispatch('endpoint/restoreBackup', item.id).then(() => {
                this.loading = false
                this.emitter.emit('loading', false)
            })
        },
        deleteBackup(item) {
            this.loading = true
            return this.$store
                .dispatch('endpoint/deleteBackup', item.id)
                .then(() => this.loadBackups())
        },
        loadBackups() {
            this.loading = true
            this.emitter.emit('loading', true)
            return this.$store.dispatch('endpoint/getBackups', this.id).then(() => {
                this.loading = false
                this.emitter.emit('loading', false)
            })
        },
    }
}
</script>
