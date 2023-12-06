<template>
    <v-tooltip
        v-if="urlName"
        bottom
    >
        <template v-slot:activator="{ on, attrs }">
            <v-btn
                color="grey"
                class="ml-2"
                fab
                small
                v-bind="attrs"
                :href="url"
                target="_blank"
                outlined
                v-on="on"
            >
                <v-icon>mdi-help-circle</v-icon>
            </v-btn>
        </template>
        <span><translate>Dokumentation</translate></span>
    </v-tooltip>
</template>

<script>
import { replaceQuery } from '@/vue/helpers/url'

export default {
    name: 'DocumentationButton',
    props: {
        docUrl: { type: String, default: '' }
    },
    computed: {
        urlName() {
            if (this.docUrl) return this.docUrl
            return this.$route.name || this.$store.state.site.staticPageUrlName
        },
        url() {
            return replaceQuery('https://docs.mividas.com/redirect/', {
                product: 'core',
                version: this.$store.state.site.version,
                url_name:  this.urlName,
            })
        }
    }
}
</script>

