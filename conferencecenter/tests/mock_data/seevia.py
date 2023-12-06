from conferencecenter.tests.mock_data.response import FakeResponse

seevia_requests = {
    'POST organizations/123/contacts': (201, '''
    {
    "id": "123entry-id",
    "name": "Roger Wilson",
    "numbers": [{
            "protocol": "sip",
            "number": "r.wilson@demo.seevia.no"
        }
    ],
    "type": "contact",
    "visibility": "usefolderrules",
    "enableQR": false
    }
    '''),
    'GET contacts/123entry-id': '''
    {
    "id": "123entry-id",
    "name": "Roger Wilson",
    "numbers": [{
            "protocol": "sip",
            "number": "r.wilson@demo.seevia.no"
        }
    ],
    "type": "contact",
    "visibility": "usefolderrules",
    "enableQR": false
    }
    ''',
    'DELETE contacts/123entry-id': '''
    {"status": "OK"}
    ''',
    'GET organizations/123/contacts': '''
    {"items": [
    {
    "id": "123entry-id",
    "name": "Roger Wilson",
    "numbers": [{
            "protocol": "sip",
            "number": "r.wilson@demo.seevia.no"
        }
    ],
    "type": "contact",
    "visibility": "usefolderrules",
    "enableQR": false
    }
    ]
    }
    ''',
}


def seevia_post(self, url, *args, **kwargs):

    method = kwargs.pop('method', '') or 'POST'

    url = url.replace('/api/v1/', '')
    for call, response in list(seevia_requests.items()):

        if call in '%s %s' % (method, url):
            if isinstance(response, tuple):
                return FakeResponse(response[1], status_code=response[0])
            else:
                return FakeResponse(response)
    return FakeResponse('''{}''')