<template>
    <v-list
        class="white"
        :style="listStyle"
    >
        <v-list-item class="px-0 d-block d-md-flex">
            <v-list-item-content
                v-if="$slots.search"
                :style="searchMaxWidth"
            >
                <slot name="search" />
            </v-list-item-content>
            <div
                v-if="$slots.filter"
                class="ml-auto d-flex align-center flex-wrap"
                :style="filterStyle"
            >
                <slot name="filter" />
            </div>
        </v-list-item>
    </v-list>
</template>

<script>
export default {
    props: {
        searchWidth: { type: String, default: '22rem' },
        filterStyle: { type: Object, default: () => ({}) },
        sticky: { type: Boolean, default: false }
    },
    computed: {
        searchMaxWidth() {
            if (!this.searchWidth) {
                return {}
            }

            return { maxWidth: this.searchWidth }
        },
        listStyle() {
            if (!this.sticky) {
                return null
            }

            return {
                position: 'sticky',
                top: '4rem',
                zIndex: 2,
                boxShadow: 'rgb(0 0 0 / 15%) 0px 10px 10px -10px'
            }
        }
    }
}
</script>
