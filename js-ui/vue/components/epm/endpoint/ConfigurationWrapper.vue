<template>
    <tr>
        <td
            width="200"
            style="vertical-align: middle;"
        >
            <v-checkbox
                v-model="active"
                hide-details
                class="my-0 py-0"
            >
                <template v-slot:label>
                    <span class="black--text">{{ name }}</span>
                </template>
            </v-checkbox>
        </td>
        <td class="text-right">
            <v-form ref="form">
                <ArgumentInput
                    v-if="active"
                    v-model="value"
                    :argument="setting"
                    :argument-name="name"
                    :no-label="true"
                />
                <span v-else-if="setting.value">{{ setting.value }}</span>
                <span
                    v-else
                    class="grey--text"
                >&lt;<translate>empty</translate>&gt;</span>
            </v-form>
        </td>
    </tr>
</template>
<script>
import ArgumentInput from './ArgumentInput'
import { getValue } from '@/vue/store/modules/endpoint/helpers'

export default {
    components: { ArgumentInput },
    props: {
        setting: { required: true, type: Object },
    },
    data() {
        return {
            ...this.getActiveValue(),
        }
    },
    computed: {
        activeValue() {
            return this.getActiveValue()
        },
        name() {
            return this.setting.name || this.setting.path[this.setting.path.length - 1]
        },
    },
    watch: {
        activeValue: {
            handler() {
                Object.assign(this, this.activeValue)
            },
            deep: true,
        },
        active() {
            this.commit()
        },
        value() {
            this.commit()
        },
    },
    mounted() {
        Object.assign(this, this.activeValue)
    },
    methods: {
        getActiveValue() {
            const active = getValue(this.setting, this.$store.state)
            return {
                active: active !== undefined,
                value: active !== undefined ? active : this.setting.value || this.setting.default || '',
            }
        },
        commit() {
            if (!this.$refs.form.validate()) return

            this.$store.commit('endpoint/updateConfiguration', {
                setting: this.setting,
                value: this.active ? this.value : null,
            })
        },
    },
}
</script>
