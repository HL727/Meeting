<template>
    <v-combobox
        :search-input.sync="search"
        :items="endpoints"
        item-text="title"
        item-value="sip"
        :return-object="false"
        clearable
        :label="$attrs.label || $gettext('Ange adress')"
        v-bind="$attrs"
        @input="$emit('input', value)"
        @update:search-input="$emit('input', value)"
        v-on="$listeners"
    >
        <template v-slot:prepend>
            <input
                v-if="inputName"
                ref="input"
                type="hidden"
                :name="inputName"
                :value="search"
            >
        </template>
    </v-combobox>
</template>

<script>
import EndpointsMixin from '../../../views/epm/mixins/EndpointsMixin'

export default {
    name: 'SipAddressPicker',
    mixins: [EndpointsMixin],
    inheritAttrs: false,
    props: {
        value: { type: String, required: false, default: null },
        inputName: { type: String, default: '' },
    },
    data() {
        /* search and value cant be updated to the same value for combobox filter to work.
        in this case the value is always the same as search, so dont pass :value to combobox
        to keep combobox value separate.
        */
        return {
            internalValue: this.value,
            search: this.value,
        }
    },
    watch: {
        search(newValue) {
            // on bind with initial value, this will be set to null. dont emit upwards
            if (newValue !== null) this.$emit('input', newValue)
        },
    },
}
</script>
