<template>
    <v-card>
        <v-card-title>
            {{ limit.name }}
        </v-card-title>
        <v-progress-linear
            :color="limit.color"
            :buffer-value="limit.over_percentage || 100"
            :value="limit.over_percentage || limit.percentage"
            :stream="!!limit.over_percentage"
        />
        <v-card-subtitle>
            <v-chip
                class="ma-2 ml-0"
                :dark="!!limit.over_percentage"
                :color="limit.over_percentage ? 'red' : ''"
            >
                <v-tooltip bottom>
                    <template v-slot:activator="{ on }">
                        <span v-on="on">
                            {{ limit.usage.participant_value }}
                        </span>
                    </template>
                    <span>
                        <translate :translate-params="{active_participants: limit.usage.active_participants}">%{active_participants} deltagare</translate>
                    </span>
                </v-tooltip>
            </v-chip>
            <translate>Just nu</translate>

            <span v-if="limit.over_percentage && limit.participant_hard_limit">
                <v-chip
                    class="ma-2 ml-5"
                    :dark="limit.over_hard_limit"
                    :color="limit.over_hard_limit ? 'black' : ''"
                >
                    {{ limit.participant_hard_limit }} ({{ limit.participant_limit }})
                </v-chip>
                <translate>Hard (soft) limit</translate>
            </span>
            <span v-else-if="limit.participant_limit">
                <v-chip class="ma-2 ml-3">{{ limit.participant_limit }}</v-chip>
                <translate>Soft limit</translate>
            </span>
        </v-card-subtitle>
    </v-card>
</template>
<script>
export default {
    name: 'CustomerUsageCard',
    props: {
        limit: { type: Object, required: true },
    },
}
</script>
