import os
from datetime import timedelta

from django.utils.timezone import now


def run():
    from statistics.cleanup import rewrite_history_chunks

    ts_stop = now() - timedelta(days=7 if not os.environ.get('UNTIL_NOW') else 0)

    rewrite_history_chunks(verbose=True, ts_stop=ts_stop)
