import { $gettext } from '@/i18n'
import React from 'react'
import PropTypes from 'prop-types'
import request from 'superagent'
import AsyncSelect from 'react-select/lib/Async'
import SyncSelect from 'react-select'

export default class AjaxSelect extends React.PureComponent {
    constructor(props) {
        super(props)
        this.state = {
            value: props.initialValue || props.value,
            inputValue: props.initialInputValue,
            ignoreChange: false,
        }

        this.handleChange = this.handleChange.bind(this)
        this.handleInputChange = this.handleInputChange.bind(this)
        this.loadOptions = this.loadOptions.bind(this)
        this.onBlur = this.onBlur.bind(this)
        this.onKeyDown = this.onKeyDown.bind(this)
    }

    componentDidUpdate(prevProps) {
        if (prevProps.value !== this.props.value) {
            this.setState({ value: this.props.value })
        }
    }

    handleChange(value) {
        this.setState({ value }, () => {
            this.props.onChange(value)
        })
    }

    handleInputChange(inputValue) {
        if (this.state.ignoreChange) {
            this.setState({ ignoreChange: false })
            if (inputValue == '') {
                return
            }
        }
        this.setState({ inputValue: inputValue || '' })
    }

    onKeyDown(event) {
        if (typeof event.target.value != 'undefined' && event.key == 'Enter') {
            if (!this.props.prefixForMatchAll) return

            if (this.inputValue && this.inputValue != event.target.value) {
                event.target.value = this.inputValue
            }
        }
    }

    onBlur() {
        if (this.props.keepValue) {
            this.state.ignoreChange = true
            this.setState({ ignoreChange: true })
        }
    }

    loadOptions(input) {
        const q = input || this.state.inputValue
        if (!q) {
            return Promise.resolve([])
        }

        const query = Object.assign({}, { [this.props.queryName]: q }, this.props.extraParams)
        return request
            .get(this.props.endpointUrl)
            .query(query)
            .then(res => {
                let resultBody = res.body
                const data = resultBody[this.props.resultsKey]
                const options = this.buildOptionsFromData(data)

                let count = resultBody.count
                if (!!this.props.prefixForMatchAll && count > 1) {
                    options.unshift({
                        value: `${this.props.prefixForMatchAll}${q}`,
                        label: `Välj alla ${count} träffar för '${q}'`,
                    })
                } else if (this.props.isTypedValueAllowed) {
                    options.unshift({
                        value: q,
                        label: q,
                    })
                }

                return options
            })
    }

    buildOptionsFromData(data) {
        if (!data) {
            return []
        }
        return data.map(item => ({
            value: item[this.props.optionValueKey],
            label: item[this.props.optionLabelKey || this.props.optionValueKey],
        }))
    }

    render() {
        const { name, isMulti, placeholder, data, isClearable } = this.props
        const { value, inputValue } = this.state

        const placeholderToUse = placeholder || (isMulti ? $gettext('Välj en eller flera...') : $gettext('Välj...'))

        const SelectComponent = data ? SyncSelect : AsyncSelect

        return (
            <span>
                <SelectComponent
                    name={name}
                    value={value}
                    onChange={this.handleChange}
                    loadOptions={this.loadOptions}
                    options={this.buildOptionsFromData(data)}
                    placeholder={placeholderToUse}
                    loadingMessage={() => $gettext('Hämtar...')}
                    noOptionsMessage={({ inputValue }) =>
                        inputValue ? $gettext('Inga träffar för') + ` '${inputValue}'` : $gettext('Skriv för att söka')
                    }
                    isMulti={isMulti}
                    onInputChange={this.handleInputChange}
                    onBlur={this.onBlur}
                    onKeyDown={this.onKeyDown}
                    inputValue={inputValue}
                    defaultOptions
                    cacheOptions
                    isClearable={isClearable}
                />
            </span>
        )
    }
}

AjaxSelect.propTypes = {
    name: PropTypes.string,
    prefixForMatchAll: PropTypes.string,
    queryName: PropTypes.string,
    optionValueKey: PropTypes.string.isRequired,
    optionLabelKey: PropTypes.string,
    endpointUrl: PropTypes.string,
    initialValue: PropTypes.object,
    value: PropTypes.object,
    initialInputValue: PropTypes.string,
    isMulti: PropTypes.bool,
    isClearable: PropTypes.bool,
    isTypedValueAllowed: PropTypes.bool,
    onChange: PropTypes.func,
    placeholder: PropTypes.string,
    resultsKey: PropTypes.string,
    extraParams: PropTypes.object,
    data: PropTypes.array,
    keepValue: PropTypes.bool,
}

AjaxSelect.defaultProps = {
    queryName: 'q',
    resultsKey: 'results',
    initialInputValue: '',
    isMulti: false,
    isClearable: true,
    isTypedValueAllowed: false,
    onChange: () => {},
    extraParams: {},
    keepValue: true,
}
