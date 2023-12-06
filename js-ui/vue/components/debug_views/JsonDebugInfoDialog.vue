<template>
    <v-dialog
        v-if="infoItemIndex !== null"
        value="infoItemIndex"
        width="800px"
        @input="infoItemIndex=null"
    >
        <v-card>
            <v-card-title>
                <v-list-item style="min-width: 0;">
                    <v-list-item-content
                        v-if="structure.key === 'email'"
                        class="mr-3"
                    >
                        <v-list-item-title class="headline">
                            {{ infoItem.subject }}
                        </v-list-item-title>
                        <v-list-item-subtitle>{{ infoItem.sender }}</v-list-item-subtitle>
                    </v-list-item-content>
                    <v-list-item-content
                        v-else-if="structure.key === 'cisco' || structure.key === 'cisco_provision'"
                        class="mr-3"
                    >
                        <v-list-item-title class="headline">
                            {{ infoItem.ip }}
                        </v-list-item-title>
                        <v-list-item-subtitle>{{ infoItem.endpoint }}</v-list-item-subtitle>
                    </v-list-item-content>
                    <v-list-item-content
                        v-else-if="structure.key === 'acanocdr' || structure.key === 'acanocdrspam'"
                        class="mr-3"
                    >
                        <v-list-item-title class="headline">
                            {{ infoItem.ip }}
                        </v-list-item-title>
                    </v-list-item-content>
                    <v-list-item-content
                        v-else-if="structure.key === 'vcs'"
                        class="mr-3"
                    >
                        <v-list-item-title
                            class="headline"
                        >
                            <translate>VCS</translate>
                            {{ infoItem.extra ? infoItem.extra.ip || '' : '' }}
                        </v-list-item-title>
                    </v-list-item-content>
                    <v-btn
                        v-if="infoItemIndex > 0"
                        icon
                        @click="infoItemIndex--"
                    >
                        <v-icon>mdi-arrow-left</v-icon>
                    </v-btn>
                    <v-btn
                        v-if="infoItemIndex < items.length - 1"
                        icon
                        @click="infoItemIndex++"
                    >
                        <v-icon>mdi-arrow-right</v-icon>
                    </v-btn>

                    <v-chip
                        class="ml-auto"
                        color="lime darken-2"
                        text-color="white"
                    >
                        <v-avatar left>
                            <v-icon>mdi-clock</v-icon>
                        </v-avatar>
                        {{ infoItem.ts_created }}
                    </v-chip>
                </v-list-item>
            </v-card-title>
            <v-card-text>
                <v-card
                    v-if="Object.keys(infoItem.extra).length > 0"
                    dark
                    color="grey darken-4"
                    class="mb-4"
                >
                    <v-card-text class="pre-content">
                        {{
                            JSON.stringify(infoItem.extra, null, 2)
                        }}
                    </v-card-text>
                </v-card>

                <v-text-field
                    v-if="structure.contentType === 'parts' && infoItem.content"
                    outlined
                    readonly
                    :value="infoItem.content"
                    :label="$gettext('Full content')"
                    append-icon="mdi-content-copy"
                    @click:append="$refs.copySnackbar.copy(infoItem.content, $event.target)"
                />
                <v-text-field
                    v-else-if="structure.contentType === 'object' && infoItem.content"
                    outlined
                    readonly
                    :value="JSON.stringify(infoItem.content, null, 2)"
                    :label="$gettext('Full content')"
                    append-icon="mdi-content-copy"
                    @click:append="$refs.copySnackbar.copy(infoItem.content, $event.target)"
                />

                <v-expansion-panels
                    v-if="structure.contentType === 'parts'"
                    :value="Object.keys(infoItem.parts).map(p => parseInt(p))"
                    multiple
                >
                    <v-expansion-panel
                        v-for="(part, part_index) in infoItem.parts"
                        :key="`part-${part_index}`"
                    >
                        <v-expansion-panel-header>
                            <strong>{{ part.type }}</strong>
                        </v-expansion-panel-header>
                        <v-expansion-panel-content class="pre-content">
                            {{
                                part.content.replace(/[\r\n]{3,}/g, '\n')
                            }}
                        </v-expansion-panel-content>
                    </v-expansion-panel>
                </v-expansion-panels>

                <div v-else-if="structure.contentType === 'text-list'">
                    <v-card
                        v-for="(c, i) in infoItem.content"
                        :key="`content-${i}`"
                        class="mb-2"
                    >
                        <v-card-text class="pre-content">
                            <div v-if="typeof i == 'string'">
                                <b>{{ i }}:</b>
                            </div>
                            {{ JSON.stringify(c, null, 2) }}
                        </v-card-text>
                    </v-card>
                </div>
                <div v-else-if="structure.contentType === 'object' && typeof infoItem.content === 'object'">
                    <v-card
                        class="mb-2"
                    >
                        <v-simple-table>
                            <tbody>
                                <tr
                                    v-for="(c, i) in infoItem.content"
                                    :key="`content-${i}`"
                                >
                                    <th>{{ i }}</th>
                                    <td>
                                        {{ JSON.stringify(c, null, 2) }}
                                    </td>
                                </tr>
                            </tbody>
                        </v-simple-table>
                    </v-card>
                </div>
                <!-- default -->
                <v-card
                    v-else-if="infoItem.content"
                    class="pre-content"
                >
                    <v-card-text>
                        {{
                            (infoItem.content.replace ? infoItem.content : JSON.stringify(infoItem.content)).replace(
                                /[\r\n]{3,}/g,
                                '\n'
                            )
                        }}
                    </v-card-text>
                </v-card>

                <v-card v-if="infoItem.otherFields">
                    <v-simple-table>
                        <tbody>
                            <tr
                                v-for="(k, i) in infoItem.otherFields"
                                :key="`other-${k}-${i}`"
                            >
                                <th>{{ k }}</th>
                                <td>
                                    <span v-if="typeof infoItem[k] == 'string'">{{ infoItem[k] }}</span>
                                    <span v-else>
                                        {{ JSON.stringify(infoItem[k], null, 2) }}
                                    </span>
                                </td>
                            </tr>
                        </tbody>
                    </v-simple-table>
                </v-card>
            </v-card-text>
            <v-card-actions>
                <v-spacer />
                <v-btn
                    color="lime darken-1"
                    text
                    @click="infoItemIndex = null"
                >
                    <translate>Stäng</translate>
                </v-btn>
            </v-card-actions>
        </v-card>
        <ClipboardSnackbar ref="copySnackbar" />
    </v-dialog>
</template>
<script>
import ClipboardSnackbar from '@/vue/components/ClipboardSnackbar'
export default {
    name: 'JsonDebugInfoDialog',
    components: {ClipboardSnackbar},
    props: {
        items: { type: Array, required: true, default: () => [] },
        structure: { type: Object, required: true, default: () => ({}) },
        value: { type: Number, default: 0 },
    },
    data() {
        return {
            infoItemIndex: this.value,
        }
    },
    computed: {
        infoItem() {
            if (this.infoItemIndex === null) {
                return {}
            }
            const result = this.items[this.infoItemIndex] || {}
            const defaultFields = ['ts_created', 'content', 'extra', 'parts', 'partsCount', 'index', 'url', 'otherFields']
            result.otherFields = Object.keys(result).filter(k => !defaultFields.includes(k))
            return result
        },
    },
    watch: {
        value(newValue) {
            this.infoItemIndex = newValue
        },
        infoItemIndex(newValue) {
            this.$emit('input', newValue)
        },
    }
}
</script>
<style scoped>
.pre-content {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
}
</style>
