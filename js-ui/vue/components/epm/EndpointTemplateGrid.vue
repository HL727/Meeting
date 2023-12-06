<template>
    <div>
        <v-data-table
            v-model="selectedTemplate"
            :items="templates"
            :headers="[
                { text: $gettext('Namn'), value: 'name' },
                { text: $gettext('Modell'), value: 'model' },
                { value: 'actions', align: 'end' },
            ]"
            :show-select="!disableSelect"
            single-select
            :loading="loading"
        >
            <template v-slot:item.actions="{ item }">
                <v-btn
                    icon
                    @click="informationTemplate = item"
                >
                    <v-icon>mdi-information</v-icon>
                </v-btn>
                <v-btn-confirm
                    v-if="!hideRemove"
                    :title="$gettext('Ta bort')"
                    icon
                    @click="deleteTemplate(item.id)"
                >
                    <v-icon>mdi-delete</v-icon>
                </v-btn-confirm>
                <slot
                    name="actions"
                    :item="item"
                />
            </template>
        </v-data-table>

        <v-dialog
            :value="informationTemplate !== null"
            max-width="640"
            scrollable
            @input="informationTemplate = null"
        >
            <v-card v-if="informationTemplate">
                <v-card-title>{{ informationTemplate.name }}</v-card-title>
                <v-divider />
                <v-card-text class="pa-0">
                    <v-simple-table v-if="informationTemplateType === 'settings'">
                        <thead>
                            <tr>
                                <th v-translate>
                                    Inställning
                                </th>
                                <th v-translate>
                                    Värde
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="(config, index) in informationTemplate.settings"
                                :key="`setting-${index}`"
                            >
                                <td>
                                    {{ config.path.join(' > ') }}
                                </td>
                                <td>
                                    <small>
                                        {{ config.value }}
                                    </small>
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                    <v-simple-table v-else>
                        <thead>
                            <tr>
                                <th v-translate>
                                    Kommando
                                </th>
                                <th v-translate>
                                    Argument
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="(command, index) in informationTemplate.commands"
                                :key="command.key"
                            >
                                <td>
                                    <v-chip
                                        small
                                        class="mr-2"
                                    >
                                        {{ index + 1 }}
                                    </v-chip>
                                    {{ command.command.join(' > ') }}
                                </td>
                                <td>
                                    <small>
                                        <span
                                            v-for="(value, key, i) in command.arguments"
                                            :key="'command' + i"
                                        >
                                            {{ key }}: {{ value }}
                                        </span>
                                        <span v-if="command.body">{{ command.body.substr(0, 10) }}...</span>
                                    </small>
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                </v-card-text>
                <v-divider />
                <v-card-actions>
                    <v-spacer />
                    <v-btn
                        v-close-dialog
                        text
                        color="red"
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
        </v-dialog>
    </div>
</template>

<script>
import VBtnConfirm from '@/vue/components/VBtnConfirm'

export default {
    name: 'EndpointTemplatePicker',
    components: { VBtnConfirm },
    props: {
        requireCommands: Boolean,
        requireSettings: Boolean,
        loading: Boolean,
        value: { type: Array, default: () => []},
        templates: { type: Array, default: () => []},
        hideRemove: { type: Boolean, default: false },
        disableSelect: { type: Boolean, default: false },
    },
    data() {
        return {
            selectedTemplate: this.value,
            informationTemplate: null,
        }
    },
    computed: {
        informationTemplateType() {
            if (this.informationTemplate.settings && this.informationTemplate.settings.length > 0) {
                return 'settings'
            }
            return 'commands'
        }
    },
    watch: {
        selectedTemplate(newValue) {
            this.$emit('input', newValue)
        },
        value(newValue, oldValue) {
            if (JSON.stringify(newValue) !== JSON.stringify(oldValue)) {
                this.selectedTemplate = newValue
            }
        }
    },
    methods: {
        deleteTemplate(templateId) {
            this.$store.dispatch('endpoint/deleteTemplate', templateId)
                .catch(e => {
                    this.$emit('error', e)
                })
        }
    }
}
</script>
