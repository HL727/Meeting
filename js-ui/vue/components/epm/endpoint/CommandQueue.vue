<template>
    <v-select
        v-if="countedQueue.length > 0"
        :value="countedQueue[0].text"
        :items="countedQueue"
        item-text="text"
        item-value="text"
        :label="label"
        class="mx-4"
        style="max-width:20rem;"
        outlined
        dense
        hide-details
    >
        <template v-slot:selection="{ item, index }">
            <span
                v-if="index === 0"
                class="d-flex align-center"
                style="max-width: 99%;overflow: hidden;"
            >
                <v-chip small>
                    <span>{{ item.text }}</span>
                </v-chip>
                <span
                    v-if="item.othersCount > 0"
                    class="grey--text text-caption"
                    style="white-space: nowrap;"
                >
                    (+{{ item.othersCount }} {{ $ngettext('annan', 'andra', item.othersCount) }})
                </span>
            </span>
        </template>
    </v-select>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

export default {
    props: {
        queue: { type: Array, default: () => [] },
        label: { type: String, default: $gettext('Kommandon i kö') },
    },
    computed: {
        countedQueue() {
            return this.queue.map(c => {
                const commandPath = c.displayPath || c.path
                const count = this.queue.filter(command => command.displayPath === c.displayPath).length

                return {
                    ...c,
                    count,
                    othersCount: this.queue.length - count,
                    text: commandPath + (count > 1 ? ` (${count})` : '')
                }
            })
        }
    }
}
</script>
