import React from 'react'
import PropTypes from 'prop-types'
import request from 'superagent'
import Spinner from './Spinner'
import { $gettext } from '@/i18n'


export default class DialoutHistory extends React.PureComponent {
    constructor(props) {
        super(props)

        this.state = {
            isPending: '',
            history: props.history,
        }

        this.renderHistory = this.renderHistory.bind(this)
        this.renderHistoryEntry = this.renderHistoryEntry.bind(this)

        this.handleSubmitForm = this.handleSubmitForm.bind(this)
        this.reloadHistory = this.reloadHistory.bind(this)
    }

    componentDidMount() {
        window.addEventListener('reloadCallLegs', this.reloadHistory)
    }

    componentWillUnmount() {
        window.removeEventListener('reloadCallLegs', this.reloadHistory)
    }

    handleSubmitForm(id, event) {
        event.preventDefault()

        this.setState({ isPending: id })
        request
            .post(this.props.endpoint)
            .send(new FormData(event.target))
            .then(() => {
                this.setState({ isPending: '' })
                window.dispatchEvent(new Event('reloadCallLegs'))
            })
    }

    reloadHistory() {
        request.get(this.props.endpoint).then(response => this.setState({ history: response.history }))
    }

    renderHistoryEntry(entry) {
        return (
            <tr key={entry.id} style={{ height: '50px' }}>
                <td>{entry.uri}</td>
                <td>{entry.name}</td>
                <td className="text-right">
                    <form method="post" onSubmit={this.handleSubmitForm.bind(this, entry.id)}>
                        <input name="csrfmiddlewaretoken" type="hidden" value={this.props.csrfToken} />
                        <input name="uri" type="hidden" value={entry.uri} />
                        <input name="name" type="hidden" value={entry.name} />

                        <button className="btn btn-primary btn-sm">
                            {this.state.isPending == entry.id ? <Spinner /> : $gettext('Ring upp')}
                        </button>
                    </form>
                </td>
            </tr>
        )
    }

    renderHistory(history) {
        return (
            <table className="table table-borderless table-text-edge table-top-border">
                <tbody>{history.map(entry => this.renderHistoryEntry(entry))}</tbody>
            </table>
        )
    }

    render() {
        return (
            <div>
                {(this.props.history && this.renderHistory(this.props.history)) || (
                    <i>Ingen historik finns</i>
                )}
            </div>
        )
    }
}

DialoutHistory.propTypes = {
    history: PropTypes.array,
    endpoint: PropTypes.string.isRequired,
    csrfToken: PropTypes.string.isRequired,
}

DialoutHistory.defaultProps = {}
