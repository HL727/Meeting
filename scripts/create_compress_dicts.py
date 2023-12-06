import json
import re
import zlib
from typing import Type, Any, Iterable

from django.db.models import Model


SIZE = 4 * 1024


from compressed_store.models import CompressStoreModel

import zstandard as zstd


clean_res = [
    re.compile(rb'\d+\.\d+\.\d+\.\d+'),
    re.compile(rb'[0-9a-fA-F]+:[0-9a-fA-F]+'),
    re.compile(rb'(?:(SystemName|SerialNumber|URL|Path)>)[^<]+'),
    re.compile(rb'[A-z0-9\.]+@[A-z0-9.]+'),
]


def clean_content(objects: Iterable[CompressStoreModel]):
    for obj in objects:
        content = obj.content
        if not content:
            continue

        for reg in clean_res:
            content = reg.sub(rb'\1' if b'(' in reg.pattern else b'', content)
        if content:
            yield content


def train(model: Type[Model], size: int, **kwargs):
    objects = model.objects.filter(**kwargs).order_by('-ts_created')[:5000]
    dct = zstd.train_dictionary(size, list(clean_content(objects)))

    return dct


def save(basename, model: Type[Model], size: int, **kwargs):

    with open('/tmp/compressdict/{}.bin'.format(basename), 'wb') as fd:

        try:
            result = train(model, size=size, **kwargs).as_bytes()
        except Exception as e:
            print(basename, e)
            return ''
        else:
            print('Finished writing', basename)
        fd.write(result)
        return result


def create_dicts(size=SIZE):
    for log in get_logs():
        save(log.basename, log.model, size=size, **log.filter_kwargs)


class LogType:
    def __init__(self, basename: str, model: Type[Model], **filter_kwargs: Any):
        self.basename = basename
        self.model = model
        self.filter_kwargs = filter_kwargs


def get_logs():
    from debuglog.models import (
        AcanoCDRLog,
        AcanoCDRSpamLog,
        EmailLog,
        VCSCallLog,
        EndpointCiscoEvent,
        EndpointCiscoProvision,
    )
    from debuglog.models import PexipEventLog, PexipHistoryLog
    from endpoint_data.models import EndpointDataContent, EndpointDataFile
    from debuglog.models import PexipPolicyLog

    yield LogType('acanocdr', AcanoCDRLog)
    yield LogType('acanocdrspam', AcanoCDRSpamLog)
    yield LogType('email', EmailLog)
    yield LogType('vcs', VCSCallLog)
    yield LogType('ciscoevent', EndpointCiscoEvent)
    yield LogType('pexip_event', PexipEventLog)
    yield LogType('pexip_history', PexipHistoryLog)
    yield LogType('pexip_policy', PexipPolicyLog)
    yield LogType('ciscoprovision_request', EndpointCiscoProvision, event='tms')
    yield LogType('ciscoprovision_response', EndpointCiscoProvision, event='tms_response')

    yield LogType('cisco_configuration', EndpointDataFile, content_type=0)
    yield LogType('cisco_status', EndpointDataFile, content_type=1)
    yield LogType('cisco_command', EndpointDataFile, content_type=2)
    yield LogType('cisco_valuespace', EndpointDataFile, content_type=3)

    yield LogType('cisco_macro', EndpointDataContent, content_type=10)
    yield LogType('cisco_panels', EndpointDataContent, content_type=11)


def test(use_dict=True):

    result = {}

    for log in get_logs():
        print('Starting', log.basename)

        if use_dict:
            try:
                with open('/tmp/compressdict/{}.bin'.format(log.basename), 'rb') as fd:
                    zdict = fd.read()
            except IOError:
                continue
        else:
            zdict = None

        regular = 0
        with_dict = 0

        for obj in log.model.objects.all()[:5000]:
            if not obj.content:
                continue

            if zdict:
                zobj = zlib.compressobj(zdict=zdict)
            else:
                zobj = zlib.compressobj()
            zobj.compress(obj.content)

            with_dict += len(zobj.flush(zlib.Z_SYNC_FLUSH))
            regular += len(obj.content)

        if regular:
            print(log.basename, regular, with_dict, '%.02f' % ((with_dict / regular) * 100))
            result[log.basename] = (regular, with_dict)

    return result


def run():
    result = {
        None: test(False),
    }
    sizes = (2 * 1024, 4 * 1024, 16 * 1024, 32 * 1024)
    for size in sizes:
        create_dicts(size)
        result[size] = test()

    print('Result\n======')
    for log in get_logs():
        if log.basename not in result[sizes[0]]:
            continue

        regular = result[None][log.basename][1]

        def perc(f):
            return '%.02f' % (f * 100)

        print(
            log.basename,
            *(perc(result[size][log.basename][1] / regular) for size in (None, *sizes))
        )

    print(json.dumps(result))

if __name__ == '__main__':
    run()
