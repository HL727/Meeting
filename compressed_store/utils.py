import gzip
import io

from django.conf import settings
from django.core.serializers import json as json_s
import os

from django.utils.timezone import localtime


def get_compressed_fd(basename, cur_date=None, output_dir=None):

    cur_date = localtime().date()

    if not output_dir:
        output_dir = settings.LOG_DIR

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    filename = '{}/{}-{}.log.gz'.format(output_dir, basename, cur_date)

    fd = gzip.open(filename, 'ab+')
    try:
        import fcntl
    except ImportError:  # windows has no lock support. probably debug mode anyway
        pass
    else:
        fcntl.lockf(fd, fcntl.LOCK_EX)

    return io.BufferedWriter(fd, 1024 * 1024)


def log_compressed(basename, data, cur_date=None, output_dir=None):

    fd = get_compressed_fd(basename, cur_date=cur_date, output_dir=output_dir)

    serializer = json_s.DjangoJSONEncoder()
    fd.write(serializer.encode(data).encode('utf-8') + b'\n')

    fd.flush()
    fd.close()
