import React from 'react'
import PropTypes from 'prop-types'
import { $gettext } from '@/i18n'

export default class ButtonWithConfirmation extends React.PureComponent {
    confirm() {
        if (window.confirm($gettext('Är du säker?'))) {
            this.props.onConfirmation()
        }
    }

    render() {
        return (
            <button
                className={this.props.className}
                onClick={() => this.confirm()}
                disabled={this.props.disabled}
            >
                {this.props.children}
            </button>
        )
    }
}

ButtonWithConfirmation.propTypes = {
    onConfirmation: PropTypes.func.isRequired,
    disabled: PropTypes.bool,
}
