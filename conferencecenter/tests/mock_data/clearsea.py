import json

from conferencecenter.tests.mock_data.response import FakeResponse

clearsea_requests = {
    'POST /service/endpoints/': (201, '''{}'''),
    'GET /service/accounts/': (200, '''{"results":[{"extension":1234}]}'''),
    'POST /service/accounts/': (201, '''{}'''),
    'DELETE /service/accounts/': (204, '''{}'''),
}


def clearsea_post(self, url, *args, **kwargs):
    method = kwargs.pop('method', '') or 'POST'
    for call, response in list(clearsea_requests.items()):

        if call in '%s %s' % (method, url):
            if isinstance(response, tuple):
                return FakeResponse(response[1], status_code=response[0])
            else:
                return FakeResponse(response)
    return FakeResponse(json.dumps({'clearsea': 1, 'status': 'OK', '_rv': 0}))