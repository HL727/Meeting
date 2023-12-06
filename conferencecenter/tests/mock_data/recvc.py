import json
from . import state

from conferencecenter.tests.mock_data.response import FakeResponse

# TODO guessed data below

recvc_requests = {
    'POST recorder/1recorderid2/session': (
        200,
        {
            'stream': '1streamid2',
            'session_id': '1sessionid2',
            'filename': 'abc.mp4',
        },
    ),
    'DELETE recorder/1recorderid2/session': (204, ''),
    'POST recorder/1recorderid2/stream': (
        200,
        {
            'stream_id': '1streamid2',
        },
    ),
    'DELETE stream/1streamid2': (204, ''),
    'GET recorder/1recorderid2/sessionstatus': state.State(
        {
            'recording-not-found': (200, {}),
            'initial': (
                200,
                {
                    'sessionlist': [
                        {
                            'stream': '1streamid2',
                            'session_id': '1sessionid2',
                            'filename': 'abc.mp4',
                        }
                    ],
                },
            ),
        }
    ),
}


def recvc_post(self, url, *args, **kwargs):
    method = kwargs.pop('method', '') or 'POST'
    for call, response in list(recvc_requests.items()):

        if call in '%s %s' % (method, url):
            if isinstance(response, state.State):
                response = response.get(state.url_state) or response.get('initial')

            if isinstance(response, tuple):
                return FakeResponse(response[1], status_code=response[0], url=url)
            else:
                return FakeResponse(response, url=url)
    return FakeResponse(json.dumps({}), status_code=404, url=url)
