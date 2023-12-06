<template>
    <div>
        <!-- support for null value in input -->
        <div v-if="limitations.type == 'String'">
            <v-text-field
                v-model="internalValue"
                :label="label"
                :counter="limitations.limitations.max_length"
                :clearable="!argument.required"
                :rules="rules"
                :placeholder="nullValue ? '<not sent>' : argument.default"
                :append-outer-icon="argument.required || value ? null : 'mdi-format-clear'"
                @click:append-outer="nullValue = !nullValue"
            />
        </div>
        <div v-else-if="limitations.type == 'Integer'">
            <v-text-field
                v-model.number="internalValue"
                type="number"
                :clearable="!argument.required"
                :label="label"
                :rules="rules"
                :placeholder="argument.default"
            />
        </div>

        <template v-if="!argument.required && separateNullToggle">
            <v-checkbox
                v-if="!value"
                v-model="nullValue"
                :label="$gettextInterpolate($gettext(`Skicka inte något värde värde för option '%{argumentName}'`), {
                    argumentName })"
            />
        </template>

        <template v-if="!separateNullToggle || nullValue">
            <!-- no widget for null -->
        </template>
        <div v-else-if="limitations.type == 'Toggle'">
            <v-switch
                v-model="internalValue"
                :label="label"
                :rules="rules"
            />
        </div>
        <div v-else-if="limitations.type == 'Literal'">
            <v-select
                v-model="internalValue"
                :items="limitations.limitations.choices"
                :label="label"
                :rules="rules"
                :placeholder="argument.default"
                :clearable="!argument.required"
                @click:clear="nullValue = true"
            />
        </div>
        <div v-else-if="limitations.type === undefined">
            <translate>Kunde inte hitta metadata för inställning. Använder textfält.</translate>
            <v-text-field
                v-model="internalValue"
                type="text"
                :label="label"
                :placeholder="argument.default"
            />
        </div>
        <div v-else>
            <div><translate>Invalid type</translate>: {{ limitations.type }} for {{ argumentName }}</div>
        </div>
    </div>
</template>
<script>
import { Validator } from '@/vue/helpers/validation'

export default {
    name: 'ArgumentInput',
    props: {
        argument: {
            type: Object,
            default() {
                return {}
            },
        },
        value: { type: null, required: false, default: undefined },
        argumentName: { type: String, required: true },
        noLabel: { type: Boolean, default: false },
    },
    data() {
        return {
            internalValue: this.value !== undefined ? this.value : this.argument.default || '',
            nullValue: false, // changed in mounted
        }
    },
    computed: {
        resultValue() {
            if (this.limitations.type === 'Integer' && this.internalValue === '') return undefined
            if (this.argument.required || this.internalValue) return this.internalValue || ''

            return this.nullValue || this.internalValue === null ? null : this.internalValue
        },
        separateNullToggle() {
            return !['String', 'Integer'].some(t => t === this.limitations.type)
        },
        limitations() {
            return this.argument.limitations?.limitations ? this.argument.limitations : {...this.argument.limitations, limitations: {}}
        },
        label() {
            if (this.noLabel) {
                return ''
            }

            if (this.argument.required) {
                return `${this.argumentName} (*)`
            }
            return this.argumentName
        },
        rules() {
            return [new Validator(this.limitations, this.argument.required).getValidator()]
        },
    },
    watch: {
        value(newValue) {
            if (newValue !== null && this.nullValue) this.nullValue = false
            this.internalValue = newValue
        },
        resultValue(newValue) {
            this.$emit('input', newValue)
        },
    },
    mounted() {
        if (!this.argument.required && this.internalValue === null) {
            this.nullValue = true
        }
    },
}
</script>
