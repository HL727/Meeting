<template>
    <v-tabs v-bind="$attrs">
        <v-tab
            exact
            :to="{ name: 'user_list' }"
        >
            <translate>Sök</translate>
        </v-tab>
        <v-tab :to="{ name: 'user_changes' }">
            <translate>Spåra ändringar</translate>
        </v-tab>
    </v-tabs>
</template>

<script>
export default {
    name: 'UserTabs',
    inheritAttrs: false,
}
</script>
