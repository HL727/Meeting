<template>
    <transition>
        <v-alert
            v-if="display"
            type="error"
            v-bind="$attrs"
            fa
        >
            <ul v-if="errorList.length > 1">
                <li
                    v-for="(error, i) in errorList"
                    :key="i"
                >
                    {{ error }}
                </li>
            </ul>
            <template v-else>
                {{ errorList[0] }}
            </template>
        </v-alert>
    </transition>
</template>

<script>
export default {
    inheritAttrs: false,
    props: {
        error: {
            type: [Error, Object, String, null],
            default: null
        },
        timeout: {
            type: Number,
            default: null,
        },
    },
    data() {
        return {
            display: !!this.getError(this.error),
            timeoutRef: null,
        }
    },
    computed: {
        realError() {
            return this.getError(this.error)
        },
        errorList() {
            if (Array.isArray(this.realError)) {
                return this.realError.map(this.errorString)
            } else if (this.realError && typeof this.realError == 'object') {
                const entries = Object.entries(this.realError).map(er => `${er[0]}: ${this.errorString(er[1])}`)
                return entries.length ? entries : [this.errorString(this.realError)]
            }
            return [this.errorString(this.realError)]
        }
    },
    watch: {
        error(newValue) {
            if (this.getError(newValue)) {
                this.display = true
            }
            else {
                this.display = false
            }
        },
        display(newValue) {
            clearTimeout(this.timeoutRef)
            if (newValue && this.timeout) {
                this.timeoutRef = setTimeout(() => {
                    this.display = false
                }, this.timeout)
            }
        }
    },
    methods: {
        errorString(error) {
            if (typeof error == 'string' && error.substr(0, 50).match(/<html/i)) return 'HTML response: ' + error.substr(0, 100)
            if (typeof error == 'string') return error
            if (typeof error == 'number') return error.toString()
            return error ? JSON.stringify(error) : ''
        },
        getError(error) {
            if (!error) return null

            if (error.errors) {
                if (error.errors.length) return error.errors
                if (typeof error.errors == 'object' && Object.keys(error.errors).length) return error.errors
            }
            if (error.error) {
                return error.error
            } else if (error.toString) {
                return error.toString()
            }


            return error
        }
    }

}
</script>
