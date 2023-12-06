import { $gettext } from '@/i18n'
import React from 'react'
import PropTypes from 'prop-types'
import request from 'superagent'
import Spinner from './Spinner'

export default class FoldedCallLegs extends React.PureComponent {
    constructor(props) {
        super(props)
        this.state = {
            callLegs: [],
            isUnfolded: false,
            isLoading: true,
        }

        this.toggleFolding = this.toggleFolding.bind(this)
        this.renderLegs = this.renderLegs.bind(this)
    }

    componentDidMount() {
        this.fetchCallLegs()
    }

    fetchCallLegs() {
        const { endpointUrl, customerId } = this.props

        request
            .get(endpointUrl)
            .query({
                customer: customerId,
            })
            .end((err, res) => {
                if (!err) {
                    const callLegs = res.body.results.filter(
                        leg =>
                            leg.remote.indexOf('app:conf:chat:id') == -1 &&
                            leg.remote.indexOf('app:conf:applicationsharing:id') == -1 &&
                            leg.remote.indexOf('app:conf:focus:id') == -1
                    )

                    this.setState({
                        callLegs,
                        isLoading: false,
                    })
                }
            })
    }

    toggleFolding(event) {
        event.preventDefault()

        this.setState(previousState => ({
            isUnfolded: !previousState.isUnfolded,
        }))
    }

    renderLegs() {
        return (
            <ul>
                {this.state.callLegs.map(leg => (
                    <li key={leg.id}>
                        {leg.name} ({leg.remote})
                    </li>
                ))}
            </ul>
        )
    }

    render() {
        const { callLegs, isUnfolded, isLoading } = this.state

        if (callLegs.length == 1) {
            return (
                <div>
                    {callLegs[0].name} ({callLegs[0].remote})
                </div>
            )
        } else if (callLegs.length > 1) {
            if (isUnfolded) {
                return (
                    <div>
                        <a href="#" onClick={this.toggleFolding}>
                            {callLegs.length} {$gettext('st')}
                        </a>
                        {this.renderLegs()}
                    </div>
                )
            }
            return (
                <div>
                    <span>{callLegs[0].name} {$gettext('och')} </span>{' '}
                    <a href="#" onClick={this.toggleFolding}>
                        {callLegs.length - 1} {$gettext('andra')}
                    </a>
                </div>
            )
        } else if (isLoading) {
            return (
                <div style={{ display: 'inline-block' }}>
                    <Spinner />
                </div>
            )
        } else {
            return (
                <div>
                    <i>{$gettext('Inga')}</i>
                </div>
            )
        }
    }
}

FoldedCallLegs.propTypes = {
    endpointUrl: PropTypes.string.isRequired,
    customerId: PropTypes.number.isRequired,
}
