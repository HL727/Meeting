import json

import exchangelib
from jsonfield import JSONField


class AutodiscoverEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, exchangelib.Version):
            return {'build': str(obj.build), 'api_version': str(obj.api_version)}
        return json.JSONEncoder.default(self, obj)


class AutodiscoverDecoder(json.JSONDecoder):

    def __init__(self, *args, **kwargs):
        kwargs['object_hook'] = load_version
        super().__init__(*args, **kwargs)


def load_version(dct):
    if 'version' not in dct:
        return dct

    parts = [int(x) for x in dct['version']['build'].split('.')]
    assert len(parts) == 4
    dct['version'] = exchangelib.Version(build=exchangelib.Build(*parts),
                               api_version=dct['version']['api_version'])
    return dct


class AutoDiscoverJSONField(JSONField):

    def __init__(self, *args, **kwargs):

        kwargs['encoder_class'] = AutodiscoverEncoder
        kwargs['decoder_kwargs'] = {'cls': AutodiscoverDecoder}
        super().__init__(*args, **kwargs)

    @staticmethod
    def _decode(s):
        return json.loads(s, object_hook=load_version)
