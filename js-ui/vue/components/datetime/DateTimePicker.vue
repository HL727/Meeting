<template>
    <v-dialog
        v-model="display"
        :fullscreen="$vuetify.breakpoint.xsOnly"
        :width="320"
    >
        <template v-slot:activator="{ on }">
            <v-text-field
                v-model="fullValue"
                :name="inputName"
                v-bind="{ ...inputAttrs, ...$attrs }"
                :label="label"
                hide-details
                append-icon="mdi-calendar-clock"
                @click:append="on.click"
                @keydown.down="on.click"
                @blur="setValue(fullValue)"
            />
        </template>

        <v-card>
            <v-card-text style="padding: 0;">
                <v-tabs
                    v-model="activeTab"
                    fixed-tabs
                >
                    <v-tab key="calendar">
                        <slot name="dateIcon">
                            <v-icon>mdi-calendar</v-icon>
                        </slot>
                    </v-tab>
                    <v-tab
                        key="timer"
                        :disabled="!date"
                    >
                        <slot name="timeIcon">
                            <v-icon>mdi-clock</v-icon>
                        </slot>
                    </v-tab>
                    <v-tab-item key="calendar">
                        <v-date-picker
                            v-model="date"
                            v-bind="datePickerProps"
                            full-width
                            @input="showTimePicker"
                        />
                    </v-tab-item>
                    <v-tab-item key="timer">
                        <v-time-picker
                            ref="timer"
                            v-model="time"
                            class="v-time-picker-custom"
                            format="24hr"
                            v-bind="timePickerProps"
                            full-width
                            @change="okHandler"
                        />
                    </v-tab-item>
                </v-tabs>
            </v-card-text>
            <v-card-actions>
                <v-btn-toggle dense>
                    <v-btn
                        small
                        @click="setValue(new Date())"
                    >
                        <translate>Nu</translate>
                    </v-btn>
                    <v-btn
                        small
                        @click="subDays(1)"
                    >
                        -1d
                    </v-btn>
                    <v-btn
                        small
                        @click="subDays(7)"
                    >
                        -7d
                    </v-btn>
                    <v-btn
                        small
                        @click="subDays(14)"
                    >
                        -14d
                    </v-btn>
                </v-btn-toggle>
                <v-spacer />
                <slot
                    name="actions"
                    :parent="this"
                >
                    <v-btn
                        color="green darken-1"
                        text
                        @click="okHandler"
                    >
                        <translate>OK</translate>
                    </v-btn>
                </slot>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { format } from 'date-fns'
import { parseDateString } from '@/vue/helpers/datetime'
import { subDays, startOfDay } from 'date-fns'

const DEFAULT_DATE = ''
const DEFAULT_TIME = '00:00:00'
const DEFAULT_DATE_FORMAT = 'yyyy-MM-dd'

export default {
    name: 'VDatetimePicker',
    inheritAttrs: false,
    props: {
        inputName: { type: String, default: '' },
        inputAttrs: {
            type: Object,
            default() {
                return {}
            },
        },
        value: {
            type: [Date, String],
            default: null,
        },
        valueType: {
            type: String,
            default: 'object',
        },
        disabled: {
            type: Boolean,
            default: false
        },
        loading: {
            type: Boolean,
            default: false
        },
        label: {
            type: String,
            default: '',
        },
        dateFormat: {
            type: String,
            default: DEFAULT_DATE_FORMAT,
        },
        timeFormat: {
            type: String,
            default: 'HH:mm',
        },
        textFieldProps: {
            type: Object,
            default() { return {} },
        },
        datePickerProps: {
            type: Object,
            default() { return {} },
        },
        timePickerProps: {
            type: Object,
            default() { return {} },
        },
    },
    data() {
        return {
            display: false,
            activeTab: 0,
            date: DEFAULT_DATE,
            time: DEFAULT_TIME,
            fullValue: this.value,
        }
    },
    computed: {
        dateTimeFormat() {
            return this.dateFormat + ' ' + this.timeFormat
        },
        datetimeString() {
            return this.dateObject ? format(this.dateObject, this.dateTimeFormat) : ''
        },
        dateObject() {
            if (this.date && this.time) {
                let datetimeString = this.date + ' ' + this.time
                if (this.time.length === 5) {
                    datetimeString += ':00'
                }
                return parseDateString(datetimeString).obj
            } else {
                return null
            }
        },
        result() {
            return this.valueType === 'string' ? this.datetimeString : this.dateObject
        },
    },
    watch: {
        value(value) {
            this.setValue(value, true)
        },
    },
    created() {
        if (this.value) this.setValue(this.value)
    },
    methods: {
        setValue(input, manual = false) {
            const lastValue = this.datetimeString
            if (!input) {
                this.date = this.time = ''
                if (!manual && lastValue != this.datetimeString) this.$emit('input', this.result)
                return
            }
            if (input.getYear) input = format(input, this.dateTimeFormat)
            let result
            try {
                result = parseDateString(input)
            } catch (e) {
                return this.setValue('', manual)
            }
            this.date = result.date
            this.time = result.time
            this.fullValue = this.datetimeString
            if (!manual && lastValue != this.datetimeString) this.$emit('input', this.result)
        },
        subDays(count=0) {
            this.setValue(startOfDay(subDays(new Date(), count)))
        },
        okHandler() {
            this.resetPicker()
            this.setValue(this.dateObject)
            this.$emit('input', this.result) // force in case of lastValue update before
        },
        clearHandler() {
            this.resetPicker()
            this.date = DEFAULT_DATE
            this.time = DEFAULT_TIME
            this.setValue(null)
        },
        resetPicker() {
            this.display = false
            this.activeTab = 0
            if (this.$refs.timer) {
                this.$refs.timer.selectingHour = true
            }
        },
        showTimePicker() {
            this.activeTab = 1
        },
    },
}
</script>
