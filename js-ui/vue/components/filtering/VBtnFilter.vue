<template>
    <v-card
        :outlined="hasFilters"
        flat
        :class="{'pt-2 pl-2': hasFilters}"
    >
        <v-btn
            color="primary"
            class="white--text"
            :class="{'mr-2 mb-2': hasFilters}"
            small
            depressed
            :disabled="disabled || loadIndicator"
            @click.stop="$emit('click', $event)"
        >
            <v-icon
                left
                dark
            >
                {{ icon }}
            </v-icon>
            {{ text }}
        </v-btn>
        <v-progress-circular
            v-if="loadIndicator"
            indeterminate
            color="primary"
            :size="20"
            class="ml-2"
        />
        <v-chip
            v-for="(filter, index) in filters"
            :key="index + filter.title"
            class="mb-2 mr-2"
            small
            :close="!hideClose && !filter.disableClose"
            @click:close="$emit('removeFilter', { filter, index })"
        >
            <div
                class="text-truncate"
                style="max-width:10rem;"
            >
                <strong
                    v-if="filter.title"
                    :class="{ 'mr-1': filter.value && typeof filter.value != 'boolean' }"
                >
                    {{ filter.title }}<template v-if="filter.value && typeof filter.value != 'boolean'">:</template>
                </strong>
                <span v-if="typeof filter.value != 'boolean'">{{ filter.value }}</span>
            </div>
        </v-chip>
        <v-chip
            v-if="(alwaysShowRemoveAll && filters.length > 0) || (showRemoveAll && filters.length > 1)"
            class="mb-2 mr-2"
            small
            dark
            color="red"
            @click="$emit('removeAllFilters')"
        >
            <translate>Ta bort alla</translate>
        </v-chip>
    </v-card>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

export default {
    props: {
        text: { type: String, default: $gettext('Filtrera') },
        disabled: { type: Boolean, default: false },
        filters: { type: Array, default: () => [] },
        hideClose: { type: Boolean, default: false },
        icon: { type: String, default: 'mdi-filter' },
        showRemoveAll: { type: Boolean, default: false },
        alwaysShowRemoveAll: { type: Boolean, default: false },
        loadIndicator: { type: Boolean, default: false },
    },
    computed: {
        hasFilters() {
            return this.filters.length > 0
        }
    },
}
</script>
