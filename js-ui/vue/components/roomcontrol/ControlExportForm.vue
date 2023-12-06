<template>
    <v-card>
        <v-card-title class="headline">
            <span><translate>Exportera</translate> {{ control.title }}</span>
        </v-card-title>
        <v-divider />
        <v-card-text class="px-2">
            <v-list
                v-if="control.isPanel"
                subheader
                flat
            >
                <v-subheader><translate>Paneler</translate></v-subheader>

                <v-list-item-group
                    v-model="form.panels"
                    multiple
                >
                    <v-list-item
                        v-for="file in control.panels"
                        :key="`file-${file.id}`"
                    >
                        <template v-slot:default="{ active, toggle }">
                            <v-list-item-action>
                                <v-checkbox
                                    :input-value="active"
                                    color="primary"
                                    @click="toggle"
                                />
                            </v-list-item-action>

                            <v-list-item-content>
                                <v-list-item-title v-text="file.name" />
                            </v-list-item-content>
                        </template>
                    </v-list-item>
                </v-list-item-group>
            </v-list>
            <v-divider v-if="control.isMacro && control.isPanel" />
            <v-list
                v-if="control.isMacro"
                subheader
                flat
            >
                <v-subheader><translate>Macron</translate></v-subheader>

                <v-list-item-group
                    v-model="form.macros"
                    multiple
                >
                    <v-list-item
                        v-for="file in control.macros"
                        :key="`file-${file.id}`"
                    >
                        <template v-slot:default="{ active, toggle }">
                            <v-list-item-action>
                                <v-checkbox
                                    :input-value="active"
                                    color="primary"
                                    @click="toggle"
                                />
                            </v-list-item-action>

                            <v-list-item-content>
                                <v-list-item-title v-text="file.name" />
                            </v-list-item-content>
                        </template>
                    </v-list-item>
                </v-list-item-group>
            </v-list>
        </v-card-text>
        <v-divider />
        <v-card-actions>
            <v-btn
                color="primary"
                :href="exportUrl"
                target="_blank"
                @click="$emit('exported')"
            >
                <translate>Exportera</translate>
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
        control: { type: Object, required: true },
    },
    data() {
        return {
            form: {
                panels: [],
                macros: []
            }
        }
    },
    computed: {
        exportUrl() {
            const filesXml = this.form.panels.map(f => this.control.panels[f].id)
            const filesJs = this.form.macros.map(f => this.control.macros[f].id)
            const files = filesJs.concat(filesXml)

            return `${this.control.urlExport}?files=${files}`
        },
    },
    mounted() {
        this.form.panels = Object.keys(this.control.panels).map(f => parseInt(f, 10))
        this.form.macros = Object.keys(this.control.macros).map(f => parseInt(f, 10))
    }
}
</script>
