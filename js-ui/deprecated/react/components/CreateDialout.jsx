import { $gettext } from '@/i18n'
import React from 'react'
import PropTypes from 'prop-types'
import request from 'superagent'
import AjaxSelect from './AjaxSelect'
import Spinner from './Spinner'

const ENDPOINT = 'https://search.seevia.me'
const QUERY_NAME = 'query'
const EXTRA_PARAMS = {
    accept: 'application/vnd.seevia.SearchResultV1+json',
    pageSize: 10,
    searchToken: window.MIVIDAS ? window.MIVIDAS.seevia_key || '' : '',
    type: 'contact', // set to 'contact' if only contact results are needed
}

export default class CreateDialout extends React.PureComponent {
    constructor(props) {
        super(props)

        this.submitForm = this.submitForm.bind(this)
        this.handleUriChange = this.handleUriChange.bind(this)

        this.state = {
            isPending: false,
            uri: undefined,
        }
    }

    handleUriChange(value) {
        this.setState({
            uri: value,
        })
    }

    submitForm(event) {
        event.preventDefault()
        if (!this.state.uri) {
            return
        }
        const { endpoint } = this.props
        const form = event.target
        this.setState({
            isPending: true,
        })
        request
            .post(endpoint)
            .send(new FormData(form))
            .then(() => {
                this.setState({
                    uri: null,
                })
                window.dispatchEvent(new Event('reloadCallLegs'))

                setTimeout(() => {
                    this.setState({
                        isPending: false,
                    })
                    window.jQuery('#createDialoutModal').modal('hide')
                    window.dispatchEvent(new Event('reloadCallLegs'))
                }, 3000)
            })
    }

    render() {
        const { csrfToken, layoutChoices } = this.props
        const { isPending, uri } = this.state
        return (
            <div>
                <form onSubmit={this.submitForm} noValidate>
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />

                    <input className="form-control" name="uri" placeholder={$gettext('Ange adress')}
                        onChange={this.handleUriChange} />
                    <br />

                    <div className="form-group">
                        <select className="custom-select" name="layout">
                            <option value="">-- {$gettext('Välj ev. layout')} --</option>
                            {Object.entries(layoutChoices).map(([k, v]) => (
                                <option key={k} value={k}>
                                    {v}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="form-group">
                        <div className="custom-control custom-checkbox">
                            <input
                                name="silent"
                                className="custom-control-input"
                                type="checkbox"
                                value="1"
                                id="silentDialout"
                            />
                            <label className="custom-control-label" htmlFor="silentDialout">
                                {$gettext('Stäng av sändning av ljud/bild')}
                            </label>
                        </div>
                    </div>

                    <button className="btn btn-primary w-100" disabled={!this.state.uri}>
                        {isPending ? <Spinner /> : $gettext('Ring upp')}
                    </button>
                </form>
            </div>
        )
    }
}

CreateDialout.propTypes = {
    layoutChoices: PropTypes.object.isRequired,
    csrfToken: PropTypes.string.isRequired,
    endpoint: PropTypes.string.isRequired,
}

CreateDialout.defaultProps = {}
