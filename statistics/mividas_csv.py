import csv
import os
from multiprocessing.pool import Pool
from time import time
from typing import Iterator, Sequence, Union, List, Tuple, Optional

from django.conf import settings
from django.core.files import File
from sentry_sdk import capture_exception

from statistics.models import Server
from statistics.parser.mividas import MividasCSVImportExport


RERAISE_ERRORS = settings.DEBUG or getattr(settings, 'TEST_MODE', False)


def chunk_iterator(it: Iterator[Sequence[str]], size=100):
    """Chunk iterator to `size` items each yield"""
    queue = []
    for _i, item in enumerate(it):
        queue.append(item)
        if len(queue) >= size:
            items, queue = queue, []
            yield items
    if queue:
        yield queue


def mividas_csv_import_multiprocess(
    server_id: int,
    data_type: str,
    rows: Union[str, File, Iterator[Sequence[str]]],  # filename/file or rows
    cols: Optional[Sequence[str]] = None,
    chunk_size=2000,
    processes=3,
) -> Iterator[Tuple[int, int, float]]:
    """
    Import csv using multiple processes.
    Return streaming results with tuple containing (successful rows, total rows, duration in seconds)
    """

    if cols is None and isinstance(rows, (File, str)):
        fd = rows if isinstance(rows, File) else File(open(rows, 'r'))
        rows = csv.reader(fd)
        cols = next(rows)

    if cols is None:
        raise ValueError('Cols must be provided unless importing file')

    def _chunk_and_create_args():
        for chunk in chunk_iterator(rows, chunk_size):
            yield (server_id, data_type, list(chunk), cols)

    if settings.TEST_MODE:
        for chunk in map(mividas_csv_import_star, _chunk_and_create_args()):
            yield chunk
    else:
        assert isinstance(server_id, int)
        with Pool(processes or os.cpu_count()) as pool:
            for chunk in pool.imap_unordered(mividas_csv_import_star, _chunk_and_create_args()):
                yield chunk


def mividas_csv_import_star(args) -> Tuple[int, int, float]:
    """Call import function with args as star args (used as multiprocess target)"""
    return mividas_csv_import(*args)


def mividas_csv_import(
    server_id: Union[int, Server],
    data_type: str,
    rows: Iterator[Sequence[str]],
    cols: List[str],
) -> Tuple[int, int, float]:
    """
    Worker to import rows from csv. Reopens db connection and django setup to work in a forked process
    Return tuple containing (successful rows, total rows, duration in seconds)
    """
    if not settings.TEST_MODE:
        from django.db import connection
        connection.close()

        from django import setup
        setup()

    server = Server.objects.get(pk=server_id) if isinstance(server_id, int) else server_id

    parser = MividasCSVImportExport(server)

    def _inner():
        if data_type == 'call':
            for chunk in chunk_iterator(rows, 100):
                yield parser.import_calls([dict(zip(cols, row)) for row in chunk])
        elif data_type == 'leg':
            for chunk in chunk_iterator(rows, 100):
                yield parser.import_legs([dict(zip(cols, row)) for row in chunk])
            parser.merge_calls()

    start = time()
    try:
        valid, total = 0, 0
        for chunk in _inner():
            for item in chunk:
                total += 1
                if bool(item):
                    valid += 1
        return valid, total, time() - start
    except Exception:
        capture_exception()
        raise
