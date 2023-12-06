from .response import FakeResponse
from . state import State
from . import state

videocenter_requests = {
    'POST access-token/': (200, '''{"access_token": "12345", "token_type": "default", "expires_in": 86399}'''),
    'POST access-token/?username=servertest&password=test&grant_type=password': (200, '''{"access_token": "12345", "token_type": "default", "expires_in": 86399}'''),
    'POST dialout': (200, '''{"status": "ok", "recording-id": "1234"}'''),
    'GET recordings/1234': (200, '''{"embed_code": "<ifram src></iframe>"}'''),
    'GET calls/1234': State({
        'initial': (200, '''{"recording_id": "1234", "embed_code": "<ifram src></iframe>"}'''),
        'recording-not-found': (404, '''{"error": "Not found"}'''),
    }),
    'GET live-streams/1234': (200, '''{"embed_code": "<ifram src></iframe>"}'''),
    'DELETE calls': (200, '''{}'''),
}


def videocenter_post(self, url, *args, **kwargs):

    method = kwargs.pop('method', '') or 'POST'

    url = url.replace('/api/v1/', '')
    for call, response in list(videocenter_requests.items()):

        if call in '%s %s' % (method, url):
            if isinstance(response, State):
                response = response.get(state.url_state) or response.get('initial')

            if isinstance(response, tuple):
                return FakeResponse(response[1], status_code=response[0])
            else:
                return FakeResponse(response)
    return FakeResponse('''{}''')
