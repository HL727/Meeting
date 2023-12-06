import React from 'react'
import PropTypes from 'prop-types'
import request from 'superagent'
import Spinner from './Spinner'

export default class MuteButton extends React.PureComponent {
    constructor(props) {
        super(props)

        this.state = {
            isPending: false,
            isMuted: props.initiallyMuted,
        }

        this.handleClick = this.handleClick.bind(this)
    }

    componentDidUpdate(prevProps) {
        if (prevProps.initiallyMuted !== this.props.initiallyMuted) {
            this.setState({
                isMuted: this.props.initiallyMuted,
            })
        }
    }

    handleClick(event) {
        event.preventDefault()
        this.setState({ isPending: true })
        request
            .post(this.props.endpointUrl)
            .set('X-CSRFToken', this.props.csrfToken)
            .type('form')
            .send({
                mute: !this.state.isMuted,
                id: this.props.id,
            })
            .then(() => {
                this.setState(
                    prevState => ({
                        isPending: false,
                        isMuted: !prevState.isMuted,
                    }),
                    () => {
                        this.props.onStateChange(this.state.isMuted)
                    }
                )
            })
    }

    render() {
        const extraClass = this.state.isMuted ? 'btn-secondary' : 'btn-success'
        return (
            <button onClick={this.handleClick} className={`btn ${extraClass}`}>
                {this.state.isPending ? (
                    <Spinner />
                ) : (
                    <span className={`fa-fw fa fa-${this.props.glyphicon}`}></span>
                )}
            </button>
        )
    }
}

MuteButton.propTypes = {
    id: PropTypes.string.isRequired,
    endpointUrl: PropTypes.string.isRequired,
    csrfToken: PropTypes.string.isRequired,
    glyphicon: PropTypes.string,
    initiallyMuted: PropTypes.bool,
    onStateChange: PropTypes.func,
}

MuteButton.defaultProps = {
    initiallyMuted: false,
    glyphicon: 'volume-up',
    onStateChange: () => {},
}
