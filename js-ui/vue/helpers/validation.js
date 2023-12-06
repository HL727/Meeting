
export class Validator {
    constructor(rules, isRequired = false) {
        this.rules = rules
        this.isRequired = isRequired
    }

    validate(value) {
        if (this.isRequired && !value) return 'This field is required'

        if (value === null || value === undefined) return true  // not required and unset

        let error
        if ((error = this.validateString(value.toString())) !== null) return error
        if ((error = this.validateNumber(parseInt(value, 10), value)) !== null) return error

        return true

    }

    validateString(strVal) {
        const limitations = this.rules.limitations
        if (limitations.max_length && strVal.length > limitations.max_length) return `This field must be max ${limitations.max_length} characters`
        if (limitations.min_length && strVal && strVal.length < limitations.min_length) return `This field must be min ${limitations.min_length} characters`
        return null
    }

    validateNumber(intVal, origVal) {
        const limitations = this.rules.limitations
        if (limitations.number && typeof origVal !== 'number' && isNaN(intVal)) return 'This field must be a number'
        if (limitations.max && intVal > limitations.max) return `This field must be max ${limitations.max}`
        if (limitations.min && intVal < limitations.min) return `This field must be min ${limitations.min}`
        return null
    }

    getValidator() {
        return (v => this.validate(v))
    }
}
