<template>
    <div>
        <v-dialog
            v-model="dialogs.updateTemplate"
            max-width="520"
        >
            <TemplateUpdateForm
                v-if="dialogs.updateTemplate"
                :template="dialogTemplate"
                @close="dialogs.updateTemplate = false"
            />
        </v-dialog>


        <v-card v-if="!templates.length">
            <v-card-text class="text-center">
                <translate>Hittar inga samlingar på din filtrering.</translate>
            </v-card-text>
        </v-card>
        <div v-if="templates.length">
            <v-row>
                <v-col
                    v-for="template in templates"
                    :key="template.id"
                    class="d-flex"
                    cols="12"
                    sm="6"
                    md="4"
                    lg="3"
                >
                    <v-card
                        elevation="1"
                        class="d-flex flex-column flex-grow-1 align-self-stretch"
                    >
                        <v-progress-linear
                            color="grey darken-4"
                            :active="true"
                            :value="100"
                        />
                        <v-card-title>{{ template.title }}</v-card-title>
                        <v-card-subtitle>{{ template.description }}</v-card-subtitle>
                        <v-spacer />
                        <v-list-item
                            class="grey lighten-4 flex-grow-0 flex-shrink-1"
                            style="flex-basis: auto;"
                        >
                            <v-chip
                                class="px-2"
                                color="grey darken-4"
                                small
                                dark
                            >
                                <strong class="mr-1">{{ template.controls.length }}</strong>
                                <span v-translate>kontroller</span>
                            </v-chip>
                            <v-spacer />
                            <v-chip
                                class="ml-auto px-2"
                                outlined
                                small
                                light
                            >
                                <strong class="mr-1">{{ template.fileCount }}</strong>
                                <span v-translate>filer</span>
                            </v-chip>
                        </v-list-item>
                        <v-divider />
                        <v-card-actions class="white">
                            <v-btn
                                color="primary"
                                icon
                                @click="showUpdateTemplateDialog(template)"
                            >
                                <v-icon>mdi-pencil</v-icon>
                            </v-btn>
                            <v-btn
                                color="primary"
                                :href="template.url_export"
                                target="_blank"
                                icon
                            >
                                <v-icon>mdi-download</v-icon>
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-col>
            </v-row>
        </div>
    </div>
</template>
<script>
import TemplateUpdateForm from '../../components/roomcontrol/TemplateUpdateForm'
export default {
    name: 'RoomControlTemplates',
    components: { TemplateUpdateForm },
    props: {
        templates: { type: Array, default() { return [] } },
    },
    data() {
        return {
            dialogs: {
                updateTemplate: false,
            },
            dialogTemplate: null,
        }
    },
    methods: {
        showUpdateTemplateDialog(template) {
            this.dialogs.updateTemplate = true
            this.dialogTemplate = template
        },
    }
}
</script>
