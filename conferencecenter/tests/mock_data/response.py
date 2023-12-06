import json


class FakeResponse:

    def __init__(self, body, status_code=200, url=None):
        self.body = body
        if isinstance(body, str):
            self.body = body.strip()
        self.status_code = status_code
        self.url = url

    def get(self, k):
        if isinstance(self.body, dict):
            return self.body.get(k)
        return None

    def json(self):
        try:
            return json.loads(self.text)
        except Exception:
            raise

    @property
    def request(self):
        return FakeRequest(self.url)

    @property
    def content(self):
        return self.text.encode('utf-8')

    @property
    def text(self):
        if isinstance(self.body, (dict, list)):
            return json.dumps(self.body)
        return self.body

    @property
    def headers(self):
        if isinstance(self.body, dict):
            return self.body
        return {}

    def to_dict(self):
        return {
            'type': 'FakeRequest',
            'data': self.body,
            'status': self.status_code,
        }


class FakeRequest:
    def __init__(self, url: str):
        self.url = url
        self.method = 'GET'  # TODO
        self.headers = {}
        self.body = b''
