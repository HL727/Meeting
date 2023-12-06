<template>
    <v-card>
        <v-card-title class="headline mb-3">
            <span>
                <translate>Spara rumskontroller som samling</translate>
            </span>
        </v-card-title>
        <v-card-subtitle>
            <v-chip-group
                column
                active-class=""
            >
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
            >Macron</span>
        </v-card-subtitle>
        <v-divider />
        <v-card-text>
            <v-text-field
                v-model="form.title"
                :label="$gettext('Namn')"
            />
            <v-textarea
                v-model="form.description"
                outlined
                :hide-details="true"
                :label="$gettext('Beskrivning')"
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
                color="primary"
                :loading="loading"
                :disabled="!formValid"
                @click="createTemplate"
            >
                <translate>Spara samling</translate>
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
                title: '',
                description: ''
            },
            loading: false,
            error: '',
            errorAlert: false
        }
    },
    computed: {
        formValid() {
            if (!this.form.title) {
                return false
            }

            return true
        },
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
        createTemplate() {
            this.error = ''
            this.errorAlert = false
            this.loading = false

            const data = {
                ...this.form,
                controls: this.controls.map(c => c.id)
            }

            this.$store.dispatch('roomcontrol/createTemplate', data).then(() => {
                this.loading = false
                this.$emit('created')
            }).catch(e => {
                this.error = e.toString()
                this.errorAlert = true
                this.loading = false
            })
        }
    }
}
</script>
