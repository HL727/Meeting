<template>
    <v-tabs v-bind="$attrs">
        <v-tab
            exact
            :to="{ name: 'cospaces_list' }"
        >
            <translate>Sök</translate>
        </v-tab>
        <v-tab :to="{ name: 'cospaces_changes' }">
            <translate>Spåra ändringar</translate>
        </v-tab>
        <v-tab
            v-if="!this.$store.state.site.isPexip"
            exact
            :to="{ name: 'webinar' }"
        >
            <translate>Webinar</translate>
        </v-tab>
    </v-tabs>
</template>

<script>
export default {
    name: 'CoSpacesTabs',
    inheritAttrs: false,
}
</script>
