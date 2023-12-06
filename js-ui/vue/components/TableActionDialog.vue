<template>
    <v-snackbar
        :value="count > 0"
        :vertical="true"
        :timeout="-1"
        color="white"
        light
        :elevation="3"
        right
        content-class="align-self-stretch mr-0"
        style="z-index: 200;max-width: 320px;"
    >
        <div class="d-flex align-center mb-5 mt-2">
            <v-avatar
                color="grey grey-400"
                size="30"
                class="mr-4"
            >
                <span class="white--text font-weight-bold">{{ count }}</span>
            </v-avatar>
            <p
                class="overline mb-0"
                style="line-height: 1.5;"
            >
                <span v-if="title">{{ title }}</span>
                <span v-else><translate>Val för samtliga</translate></span>
            </p>
            <v-btn
                v-if="$vuetify.breakpoint.xsOnly && mobileToggle"
                icon
                class="ml-auto"
                @click="mobileToggle = false"
            >
                <v-icon>mdi-close</v-icon>
            </v-btn>
        </div>

        <div
            v-if="$vuetify.breakpoint.xsOnly && !mobileToggle"
            key="mobileToggle"
        >
            <v-divider class="mb-3" />
            <v-btn
                color="primary"
                depressed
                small
                @click="mobileToggle = true"
            >
                <translate>Visa åtgärder</translate>
            </v-btn>
        </div>
        <div
            v-else
            key="measures"
        >
            <slot />
        </div>
    </v-snackbar>
</template>

<script>
export default {
    props: {
        count: { type: Number, default: 0 },
        title: { type: String, default: '' },
    },
    data() {
        return {
            mobileToggle: false
        }
    }
}
</script>
