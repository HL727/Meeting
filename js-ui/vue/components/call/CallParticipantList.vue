<template>
    <v-chip-group>
        <v-chip
            v-for="part in activeItems"
            :key="'part' + part.id"
            small
            :title="title(part)"
        >
            {{ displayName(part) }}
        </v-chip>
        <v-chip
            v-if="showToggle && !toggle"
            small
            dark
            @click="toggle = !toggle"
        >
            +{{ hidden }}
        </v-chip>
        <v-chip
            v-else-if="showToggle"
            small
            dark
            @click="toggle = !toggle"
        >
            -
        </v-chip>
    </v-chip-group>
</template>
<script>
export default {
    name: 'CallParticipantList',
    props: {
        participants: { type: Array, required: true, default() { return [] } },
        limit: { type: Number, default: 2 },
    },
    data() {
        return {
            toggle: false,
        }
    },
    computed: {
        showToggle() {
            return this.participants.length > this.limit
        },
        hidden() {
            return this.participants.length - this.limit
        },
        activeItems() {
            if (!this.participants) return []

            if (this.showToggle && !this.toggle) {
                return this.participants.slice(0, this.limit)
            }
            return this.participants
        }
    },
    methods: {
        trim(s, limit=20) {
            if (s.length > limit) {
                return s.substr(0, limit - 3) + '...'
            }
            return s
        },
        displayName(participant) {
            if (!participant) return '-'
            if (participant.name && participant.remote) {
                return this.trim(participant.name, 30) + ' (' + this.trim(participant.remote, 30) + ')'
            }
            return this.trim(participant.remote, 60)
        },
        title(participant) {
            let result = ''
            if (participant.name && participant.remote) {
                result = participant.name + ' (' + participant.remote + ')'
            } else {
                result = this.remote
            }
            return (result !== this.displayName(participant)) ? result : null
        }
    }
}
</script>
