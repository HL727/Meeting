<template>
    <v-card>
        <v-card-title class="headline mb-3">
            <span>
                <translate>Exportera rumskontroller</translate>
            </span>
        </v-card-title>
        <v-card-subtitle>
            <v-chip-group column>
                <v-chip
                    v-for="control in controls"
                    :key="control.id"
                    small
                    dark
                    color="primary"
                >
                    {{ control.title }}
                </v-chip>
            </v-chip-group>
            <v-divider class="mb-2" />
            <v-chip
                class="mr-2"
                small
            >
                {{ controlsSummary.panels }}
            </v-chip> <span
                v-translate
                class="mr-4"
            >Paneler</span>
            <v-chip
                class="mr-2"
                small
            >
                {{ controlsSummary.macros }}
            </v-chip> <span
                v-translate
                class="mr-3"
            >Makron</span>
        </v-card-subtitle>
        <v-divider />
        <v-card-text class="pt-4">
            <v-text-field
                v-model="form.url"
                :disabled="!form.url"
                :loading="loading"
                :hide-details="true"
                :label="$gettext('Hemlig länk')"
            />
        </v-card-text>

        <v-alert
            v-model="errorAlert"
            tile
            dense
            dismissible
            border="top"
            type="error"
            class="mb-0"
        >
            {{ error }}
        </v-alert>
        <v-divider v-if="!errorAlert" />

        <v-card-actions>
            <v-btn
                dark
                color="primary"
                :loading="loading"
                @click="generateUrl"
            >
                <translate>Generera länk</translate>
            </v-btn>
            <v-spacer />
            <v-btn
                text
                color="red"
                @click="$emit('close')"
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
</template>

<script>
export default {
    props: {
        controls: { type: Array, required: true },
    },
    data() {
        return {
            form: {
                url: '',
            },
            loading: false,
            error: '',
            errorAlert: false
        }
    },
    computed: {
        controlsSummary() {
            const summary = {
                total: 0,
                panels: 0,
                macros: 0
            }

            this.controls.map(c => {
                const panels = []
                const macros = []

                c.files.forEach(f => {
                    const ext = f.name.split('.').pop()
                    if (ext.toLowerCase() === 'xml') {
                        panels.push(f)
                    }
                    if (ext.toLowerCase() === 'js') {
                        macros.push(f)
                    }
                })

                summary.total += panels.length + macros.length
                summary.panels += panels.length
                summary.macros += macros.length
            })

            return summary
        },
    },
    methods: {
        generateUrl() {
            this.error = ''
            this.errorAlert = false
            this.loading = true
            this.form.url = ''

            const controls = this.controls.map(c => c.id)
            this.$store.dispatch('roomcontrol/getExportUrl', controls).then((response) => {
                this.loading = false
                this.form.url = response.url
            }).catch(e => {
                this.error = e.toString()
                this.errorAlert = true
                this.loading = false
            })
        }
    }
}
</script>
