<template>
    <PageContainer>
        <PageHeader
            v-if="title || $slots.title || actions || $slots.actions"
            :icon="icon"
            :actions="actions"
            :doc-url="docUrl"
            :loading="loading"
        >
            <template
                v-if="title"
                slot="title"
            >
                <h1>{{ title }}</h1>
            </template>
            <template
                v-else-if="$slots.title"
                slot="title"
            >
                <slot name="title" />
            </template>
            <template
                v-if="$slots.actions"
                slot="actions"
            >
                <slot name="actions" />
            </template>
        </PageHeader>
        <template v-if="$slots.tabs">
            <slot name="tabs" />
            <v-divider />
        </template>
        <PageSearchFilter
            v-if="$slots.search || $slots.filter"
            :search-width="searchWidth"
        >
            <template slot="search">
                <slot name="search" />
            </template>
            <template slot="filter">
                <slot name="filter" />
            </template>
        </PageSearchFilter>
        <slot name="content">
            <slot />
        </slot>
    </PageContainer>
</template>

<script>
import PageContainer from '@/vue/views/layout/page/PageContainer'
import PageHeader from '@/vue/views/layout/page/PageHeader'
import PageSearchFilter from '@/vue/views/layout/page/PageSearchFilter'

export default {
    name: 'Page',
    components: { PageContainer, PageHeader, PageSearchFilter },
    props: {
        icon: { type: String, default: '' },
        title: { type: String, default: '' },
        searchWidth: { type: String, default: '22rem' },
        actions: { type: Array, default() { return [] } },
        docUrl: { type: String, default: '' },
        loading: { type: Boolean, default: false }
    },
}
</script>
