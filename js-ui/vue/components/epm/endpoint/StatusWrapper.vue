<template>
    <tr>
        <td>
            <v-checkbox
                v-if="checkbox"
                v-model="active"
                hide-details
                class="my-0 py-0"
                @change="update"
            >
                <template v-slot:label>
                    <span class="black--text">{{ status.name }}s</span>
                </template>
            </v-checkbox>
            <div
                v-else
                class="subtitle-1"
            >
                {{ status.name }}
            </div>
        </td>
        <td class="text-right">
            <span v-if="status.value">{{ status.value }}</span>
            <span
                v-else
                class="grey--text"
            >&lt;<translate>empty</translate>&gt;</span>
        </td>
    </tr>
</template>
<script>
import { getKey } from '@/vue/store/modules/endpoint/helpers'

export default {
    props: {
        status: { required: true, type: Object },
        checkbox: { required: false, type: Boolean, default: false },
    },
    data() {
        return {
            active: !!this.$store.state.endpoint.report[getKey(this.status)],
        }
    },
    methods: {
        update() {
            return this.$store.commit('endpoint/updateReport', { status: this.status, active: this.active })
        },
    },
}
</script>
