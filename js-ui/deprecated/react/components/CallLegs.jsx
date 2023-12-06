import React from 'react'
import PropTypes from 'prop-types'
import request from 'superagent'
import Spinner from './Spinner'
import MuteButton from './MuteButton'
import CallLeg from './CallLeg'
import { $gettext } from '@/i18n'

const FETCH_INTERVAL = 5000

export default class CallLegs extends React.PureComponent {
    constructor(props) {
        super(props)
        this.state = {
            callLegs: [],
            isLoading: true,
        }
        this.fetchCallLegsSummaries = this.fetchCallLegsSummaries.bind(this)
        this.handleCallLegHangup = this.handleCallLegHangup.bind(this)
    }

    componentDidMount() {
        this.continuouslyFetchCallLegsSummaries()
        window.addEventListener('reloadCallLegs', this.fetchCallLegsSummaries)
    }

    continuouslyFetchCallLegsSummaries() {
        this.fetchCallLegsSummaries()
        this.timeoutHandle = setTimeout(() => {
            this.continuouslyFetchCallLegsSummaries()
        }, FETCH_INTERVAL)
    }

    componentWillUnmount() {
        clearTimeout(this.timeoutHandle)
        window.removeEventListener('reloadCallLegs', this.fetchCallLegsSummaries)
    }

    fetchCallLegsSummaries() {
        const { callLegsEndpoint, customerId } = this.props

        request
            .get(callLegsEndpoint)
            .query({
                customer: customerId,
            })
            .then(res => {
                return res.body ? res.body.results : []
            })
            .then(callLegs => {
                this.setState({
                    callLegs,
                    isLoading: false,
                })
            })
	    .catch(function() {})
    }

    handleCallLegHangup() {
        this.fetchCallLegsSummaries()
    }

    renderCallLegs(callLegs) {
        const { csrfToken, muteAllVideoEndpoint, muteAllAudioEndpoint, callId } = this.props

        callLegs = callLegs.filter(
            leg =>
                leg.remote.indexOf('app:conf:chat:id') == -1 &&
                leg.remote.indexOf('app:conf:applicationsharing:id') == -1 &&
                leg.remote.indexOf('app:conf:focus:id') == -1
        )

        return (
            <div>
                <div className="alert alert-secondary bg-none d-flex">
                    <div className="align-self-center">
                        {$gettext('Stäng av video eller ljud från samtliga deltagare')}:
                    </div>

                    <div className="input-group w-auto ml-auto">
                        <div className="input-group-prepend input-group-prepend-space">
                            <MuteButton
                                endpointUrl={muteAllVideoEndpoint}
                                id={callId}
                                glyphicon="video"
                                csrfToken={csrfToken}
                                onStateChange={this.fetchCallLegsSummaries}
                            />
                        </div>
                        <div className="input-group-append input-group-append-space">
                            <MuteButton
                                endpointUrl={muteAllAudioEndpoint}
                                id={callId}
                                csrfToken={csrfToken}
                                onStateChange={this.fetchCallLegsSummaries}
                            />
                        </div>
                    </div>
                </div>

                <div className="table-responsive">
                    <table className="table table-striped table-borderless">
                        <thead>
                            <tr>
                                <th>{$gettext('Deltagare')}</th>
                                <th>{$gettext('Adress')}</th>
                                <th>{$gettext('Längd')}</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>{this.renderTableRows(callLegs)}</tbody>
                    </table>
                </div>
            </div>
        )
    }

    renderTableRows(callLegs) {
        const {
            callLegEndpoint,
            csrfToken,
            customerId,
            muteAudioEndpoint,
            muteVideoEndpoint,
            setLayoutEndpoint,
            layoutChoices,
            hangupCallLegEndpoint,
        } = this.props
        return callLegs.map(leg => (
            <CallLeg
                key={leg.id}
                leg={leg}
                callLegEndpoint={callLegEndpoint}
                muteAudioEndpoint={muteAudioEndpoint}
                muteVideoEndpoint={muteVideoEndpoint}
                csrfToken={csrfToken}
                customerId={customerId}
                setLayoutEndpoint={setLayoutEndpoint}
                layoutChoices={layoutChoices}
                hangupEndpoint={hangupCallLegEndpoint}
                onHangup={this.handleCallLegHangup}
            />
        ))
    }

    render() {
        const { callLegs, isLoading } = this.state

        return (
            <div className="call_legs">
                {callLegs.length ? (
                    this.renderCallLegs(callLegs)
                ) : isLoading ? (
                    <div style={{ display: 'inline-block' }}>
                        <Spinner />
                    </div>
                ) : (
                    <p>
                        <i>{$gettext('Just nu finns inga anslutna deltagare till mötet')}</i>
                    </p>
                )}
            </div>
        )
    }
}

CallLegs.propTypes = {
    name: PropTypes.string,
    callId: PropTypes.string.isRequired,
    callLegsEndpoint: PropTypes.string.isRequired,
    muteAllVideoEndpoint: PropTypes.string.isRequired,
    muteAllAudioEndpoint: PropTypes.string.isRequired,
    muteAudioEndpoint: PropTypes.string.isRequired,
    muteVideoEndpoint: PropTypes.string.isRequired,
    callLegEndpoint: PropTypes.string.isRequired,
    setLayoutEndpoint: PropTypes.string.isRequired,
    csrfToken: PropTypes.string.isRequired,
    customerId: PropTypes.number.isRequired,
    layoutChoices: PropTypes.object.isRequired,
    hangupCallLegEndpoint: PropTypes.string.isRequired,
}

CallLegs.defaultProps = {}
