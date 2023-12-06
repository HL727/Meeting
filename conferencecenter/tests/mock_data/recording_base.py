import json

from conferencecenter.tests.mock_data.response import FakeResponse


_normal_response = '''
{"videos": []}
    '''.strip()


recording_base_requests = {
    'POST /callback/': (200, _normal_response),
    'POST http://localhost/callback/': (200, _normal_response),
}


def recording_base_post(url, *args, **kwargs):
    method = kwargs.pop('method', '') or 'POST'
    for call, response in list(recording_base_requests.items()):

        if call in '%s %s' % (method, url):
            if isinstance(response, tuple):
                return FakeResponse(response[1], status_code=response[0])
            else:
                return FakeResponse(response)
    return FakeResponse(json.dumps({}), status_code=404)
