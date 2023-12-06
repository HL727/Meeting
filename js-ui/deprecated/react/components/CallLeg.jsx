
import { $gettext } from '@/i18n'
import React from 'react'
import PropTypes from 'prop-types'
import request from 'superagent'
import MuteButton from './MuteButton'

const StatusInfo = ({ header, info }) => {
    if (info) {
        const objectContent = Object.entries(info).map(([key, value]) => `\n${key}: ${value}`)
        return (
            <pre style={{ marginRight: '10px', float: 'left' }}>
                <strong>{header}:</strong>
                {`\n{${objectContent}\n}`}
            </pre>
        )
    }
    return null
}

export default class CallLeg extends React.PureComponent {
    constructor(props) {
        super(props)
        this.state = {
            leg: this.props.leg,
            isShowingAdvancedInfo: false,
        }

        this.toggleAdvancedInfo = this.toggleAdvancedInfo.bind(this)
        this.handleLayoutChange = this.handleLayoutChange.bind(this)
        this.handleClickHangup = this.handleClickHangup.bind(this)
    }

    componentDidMount() {
        this.fetchCallLegDetails()
    }

    componentDidUpdate(prevProps) {
        if (this.props.leg !== prevProps.leg) {
            this.fetchCallLegDetails()
        }
    }

    fetchCallLegDetails() {
        const { callLegEndpoint, customerId } = this.props

        request
            .get(callLegEndpoint)
            .query({
                call_leg_id: this.props.leg.id,
                customer: customerId,
            })
            .then(res => {
                this.setState({
                    leg: res.body.result,
                })
            })
            .catch(() => {
                // check 404
            })
    }

    toggleAdvancedInfo() {
        this.setState(prevState => ({
            isShowingAdvancedInfo: !prevState.isShowingAdvancedInfo,
        }))
    }

    handleLayoutChange(event) {
        const layout = event.target.value
        const { setLayoutEndpoint, csrfToken, leg, customerId } = this.props
        request
            .post(setLayoutEndpoint)
            .set('X-CSRFToken', csrfToken)
            .type('form')
            .query({ customer: customerId })
            .send({
                leg_id: leg.id,
                layout,
            })
            .end()
    }

    handleClickHangup() {
        const { hangupEndpoint, onHangup, csrfToken, leg, customerId } = this.props
        request
            .post(hangupEndpoint)
            .set('X-CSRFToken', csrfToken)
            .type('form')
            .query({ customer: customerId })
            .send({
                leg_id: leg.id,
            })
            .then(() => {
                onHangup(leg)
            })
    }

    renderAlarms(leg) {
        if (leg.alarms && Object.keys(leg.alarms).length) {
            return (
                <span>
                    <strong>Varningar:</strong> {Object.keys(leg.alarms).join(', ')}
                    <br />
                </span>
            )
        }
    }

    renderTxAudioStatus(leg) {
        return <StatusInfo header={$gettext('Tar emot ljud')} info={leg.status.txAudio} />
    }

    renderTxVideomainStatus(leg) {
        return <StatusInfo header={$gettext('Tar emot video (main)')} info={leg.status.txVideomain} />
    }

    renderTxVideopresentationStatus(leg) {
        return <StatusInfo header={$gettext('Tar emot video (presentation)')} info={leg.status.txVideopresentation} />
    }

    renderRxAudioStatus(leg) {
        return <StatusInfo header={$gettext('Sänder ljud')} info={leg.status.rxAudio} />
    }

    renderRxVideomainStatus(leg) {
        return <StatusInfo header={$gettext('Sänder video (main)')} info={leg.status.rxVideomain} />
    }

    renderRxVideopresentationStatus(leg) {
        return <StatusInfo header={$gettext('Sänder video (presentation)')} info={leg.status.rxVideopresentation} />
    }

    renderAdvancedInfo() {
        const { leg } = this.state
        return (
            <tr key="second-row">
                <td colSpan="4">
                    <strong>{$gettext('Ansluten via')}:</strong> {leg.type} {leg.subtype}.
                    <br />
                    {this.renderAlarms(leg)}
                    {this.renderTxAudioStatus(leg)}
                    {this.renderTxVideomainStatus(leg)}
                    {this.renderTxVideopresentationStatus(leg)}
                    <br style={{ clear: 'both' }} />
                    {this.renderRxAudioStatus(leg)}
                    {this.renderRxVideomainStatus(leg)}
                    {this.renderRxVideopresentationStatus(leg)}
                </td>
            </tr>
        )
    }

    render() {
        const { leg } = this.state
        const { csrfToken, muteVideoEndpoint, muteAudioEndpoint, layoutChoices } = this.props

        const remote = leg.remote.replace(/;gruu;.*/, '')

        return [
            <tr key="first-row">
                <td className="align-middle">
                    {leg.status && leg.status.encryptedMedia && (
                        <span title={$gettext('Krypterad')} className="fa fa-lock"></span>
                    )}
                    {leg.status &&
                        leg.status.txVideopresentation &&
                        leg.status.txVideopresentation.bitRate && (
                            <span className="fa fa-square" title={$gettext('Visar presentation')}></span>
                        )}
                    {leg.status &&
                        leg.status.rxVideopresentation &&
                        leg.status.rxVideopresentation.bitRate && (
                            <span className="fa fa-play" title={$gettext('Sänder presentation')}></span>
                        )}{' '}
                    {leg.name}{' '}
                    {leg.status && (
                        <a onClick={this.toggleAdvancedInfo}>
                            <span title={$gettext('Visa avancerad info')} className="fa fa-info-circle"></span>
                        </a>
                    )}
                </td>
                <td className="align-middle">{remote}</td>
                <td className="align-middle">{leg.status && leg.status.durationMinutes}</td>
                <td className="text-right">
                    <div style={{ minWidth: '200px' }}>
                        <input type="hidden" name="leg_id" value={leg.id} />

                        <div className="input-group">
                            {leg.configuration && (
                                <select
                                    name="layout"
                                    onChange={this.handleLayoutChange}
                                    defaultValue={leg.configuration.chosenLayout}
                                    className="custom-select"
                                    style={{ maxWidth: '100px' }}
                                >
                                    <option value="">Layout</option>
                                    {Object.entries(layoutChoices).map(([k, v]) => (
                                        <option key={k} value={k}>
                                            {v}
                                        </option>
                                    ))}
                                </select>
                            )}
                            <div className="input-group-append input-group-append-space">
                                {leg.configuration && (
                                    <MuteButton
                                        initiallyMuted={leg.configuration.rxVideoMute}
                                        id={leg.id}
                                        endpointUrl={muteVideoEndpoint}
                                        glyphicon="video"
                                        csrfToken={csrfToken}
                                    />
                                )}
                            </div>
                            <div className="input-group-append input-group-append-space">
                                {leg.configuration && (
                                    <MuteButton
                                        initiallyMuted={leg.configuration && leg.configuration.rxAudioMute}
                                        id={leg.id}
                                        endpointUrl={muteAudioEndpoint}
                                        glyphicon="microphone"
                                        csrfToken={csrfToken}
                                    />
                                )}
                            </div>
                            <div className="input-group-append input-group-append-space">
                                <button onClick={this.handleClickHangup} className="btn btn-danger">
                                    <span className="fa fa-fw fa-times"></span>
                                </button>
                            </div>
                        </div>
                    </div>
                </td>
            </tr>,
            this.state.isShowingAdvancedInfo && this.renderAdvancedInfo(),
        ]
    }
}

CallLeg.propTypes = {
    name: PropTypes.string,
    leg: PropTypes.object.isRequired,
    callLegEndpoint: PropTypes.string.isRequired,
    csrfToken: PropTypes.string.isRequired,
    customerId: PropTypes.number.isRequired,
    muteAudioEndpoint: PropTypes.string.isRequired,
    muteVideoEndpoint: PropTypes.string.isRequired,
    setLayoutEndpoint: PropTypes.string.isRequired,
    layoutChoices: PropTypes.object.isRequired,
    hangupEndpoint: PropTypes.string.isRequired,
    onHangup: PropTypes.func,
}

CallLeg.defaultProps = {
    onHangup: () => {},
}
