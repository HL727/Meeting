<template>
    <v-dialog
        :value="show"
        scrollable
        :max-width="520"
        @input="$emit('input', null)"
    >
        <v-card>
            <v-card-title><translate>Samtalsinformation</translate></v-card-title>
            <v-divider />
            <v-card-text class="px-0">
                <v-simple-table>
                    <tbody>
                        <tr
                            v-for="item in callInformation"
                            :key="item.key"
                        >
                            <th class="text-capitalize">
                                {{ item.key }}
                            </th>
                            <td>{{ item.title }}</td>
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
</template>

<script>
export default {
    name: 'CallParticipantDetailsDialog',
    props: {
        value: {
            type: Object, default() {
                return {}
            }
        },
    },
    data() {
        return {}
    },
    computed: {
        show() {
            return !!Object.keys(this.value || {}).length
        },
        callInformation() {
            if (!this.value) return []

            return Object.entries(this.value)
                .filter(i => i[0] !== 'loading')
                .map(i => ({key: i[0], title: i[1]}))
        },
    }
}
</script>
