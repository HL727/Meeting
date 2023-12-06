<template>
    <v-icon v-if="!proxy.ts_activated">
        mdi-new-box
    </v-icon>
    <span
        v-else
        :style="style"
    />
</template>

<script>

export default {
    props: {
        proxy: { type: Object, required: true },
    },
    computed: {
        style() {
            return {
                backgroundColor: this.proxy.is_online ? '#2196F3' : '#F44336',
            }
        },
    },
}
</script>

<style scoped>
span {
    border-radius: 16px;
    display: inline-block;
    width: 16px;
    height: 16px;
    margin-right: 5px;
    vertical-align: middle;
}
</style>
