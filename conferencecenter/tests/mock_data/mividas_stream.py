import json

from conferencecenter.tests.mock_data.response import FakeResponse


_normal_response = '''
 {"id":2,"title":"test_123_main","description":"","customer":1,"channel":null,
 "channel_name":null,"ts_start":"2019-05-23T15:47:19.084502+02:00",
 "ts_stop":"2019-05-23T15:47:19.084515+02:00",
 "ts_created":"2019-05-23T15:47:19.098045+02:00","play_urls":{},
 "playback_url":"http://127.0.0.1:8010/default/streamkey/play/f7596512dd5a493ab7bd369abfac912b/",
 "publish_rtmp":"rtmp://127.0.0.1:8010/push/20696d7808da401c8f4d9d5636da5be5",
 "secret_key":"20696d7808da401c8f4d9d5636da5be5",
 "republish_rtmp":"rtmp://127.0.0.1:8010/pull/20696d7808da401c8f4d9d5636da5be5",
 "embed_code":"<iframe width=\\"560\\" height=\\"315\\" style=\\"max-width: 100%; max-height: 100%;\\" \\n        src=\\"http://127.0.0.1:8010/default/streamkey/embed/20696d7808da401c8f4d9d5636da5be5/\\" frameborder=\\"0\\" \\n        allow=\\"accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture\\" \\n        allowfullscreen></iframe>",
 "embed_url":"http://127.0.0.1:8010/default/streamkey/embed/20696d7808da401c8f4d9d5636da5be5/"}
    '''.strip()


mividas_stream_requests = {
    'POST book/1234/book/': (201, _normal_response),
    'GET book/1234/': (200, _normal_response),
}


def mividas_stream_post(self, url, *args, **kwargs):
    method = kwargs.pop('method', '') or 'POST'
    for call, response in list(mividas_stream_requests.items()):

        if call in '%s %s' % (method, url):
            if isinstance(response, tuple):
                return FakeResponse(response[1], status_code=response[0])
            else:
                return FakeResponse(response)
    return FakeResponse(json.dumps({}), status_code=404)
