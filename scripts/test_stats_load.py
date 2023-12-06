import json
import os
import subprocess
import sys
from random import randint
from time import time, sleep
from django.utils.translation import gettext_lazy as _

import django
import requests

'''
Simple concurrent load test for pexip statistics handler

local (creates provider/customers):

    python test_stats_load.py

remote (to server cdr uri):

    python test_stats_load.py https://example.org/cdr/pexip/...
'''



def test_load(cdr_url, threads=30, requests_count=140):
    from multiprocessing.pool import ThreadPool
    from conferencecenter.tests.mock_data.pexip import eventsink_events
    assert '/cdr/pexip/' in cdr_url

    # init data

    def _replace(obj, suffix='', offset=0):
        end_time = time() - int(60 * 30 * offset)
        start_time = end_time - 60 * 60

        result = json.dumps(obj)
        for k, v in {
            'meet.webapp': str(suffix) + 'meet.webapp',
            '1559897886': str(int(start_time)),
            '1559898886': str(int(end_time)),
            'ac58a572-33e5-4b19-ac1c-f0b1d22215e6': 'ac58a572-33e5-4b19-ac1c-' + str(suffix),
        }.items():
            result = result.replace(k, v)

        return result

    conference = ([], [])
    participant = ([], [])
    for i in range(20):
        suffix = '{}.{}'.format(i, time())
        conference[0].append(_replace(eventsink_events['conference_started'], suffix, offset=i))
        conference[1].append(_replace(eventsink_events['conference_ended'], suffix, offset=i))

        participant[0].append(_replace(eventsink_events['participant_connected'], suffix, offset=i))
        participant[1].append(_replace(eventsink_events['participant_disconnected'], suffix, offset=i))

    # run
    pool = ThreadPool(processes=threads)

    def _run_thread(num):
        data_index = num % len(conference[0])
        print('Start {}, index {}'.format(num, data_index))
        sleep(randint(0, 1000) / 1000)

        timing = []
        def _post(*args, **kwargs):
            start = time()
            try:
                response = requests.post(*args, **kwargs, headers={'Content-Type': 'text/json', 'Accept': 'text/json'}, verify=False)
            except Exception as e:
                print(e)
            else:
                timing.append(time() - start)
                if response.status_code != 200:
                    print('Error', response.content)

        _post(cdr_url, conference[0][data_index])
        _post(cdr_url, conference[0][data_index])
        for _i in range(2):
            _post(cdr_url, participant[0][data_index])
            _post(cdr_url, participant[0][data_index].replace('ac58a572', '666666'))
        for _i in range(2):
            _post(cdr_url, participant[1][data_index])
            _post(cdr_url, participant[1][data_index].replace('ac58a572', '666666'))

        print(num, 'Avg', sum(timing) / len(timing))

    pool.map(_run_thread, range(requests_count))


def init_environment():
    from statistics.models import Server
    from provider.models.provider import Provider
    from customer.models import CustomerMatch, Customer

    provider = Provider.objects.get_or_create(title=_('Load test'), subtype=Provider.SUBTYPES.pexip)[0]
    server = Server.objects.get_or_create(type=Server.PEXIP, name=_('Load test'), cluster=provider.cluster)[0]
    customer = Customer.objects.first() or Customer.objects.get_or_create(title='defaults')[0]
    customer2 = Customer.objects.exclude(pk=customer.pk).first() or Customer.objects.get_or_create(title='defaults2')[0]

    CustomerMatch.objects.get_or_create(cluster=provider.cluster, regexp_match=r'^[0-3]', customer=customer)
    CustomerMatch.objects.get_or_create(cluster=provider.cluster, regexp_match=r'^[4-6]', customer=customer2)

    cdr_url = 'http://localhost:8765{}'.format(server.get_cdr_path())
    return cdr_url


def run():

    if len(sys.argv) > 1:
        cdr_url = sys.argv[1]
    else:
        cdr_url = init_environment()

    p = subprocess.Popen(['gunicorn', 'conferencecenter.wsgi:application', '-b', ':8765', '-w', '4'], stdout=subprocess.PIPE, stdin=None)
    sleep(3)
    try:
        test_load(cdr_url)
    finally:
        p.kill()
    sleep(2)


if __name__ == '__main__':
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conferencecenter.settings')
    django.setup()
    run()
