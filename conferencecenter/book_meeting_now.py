from os import environ
environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from django.utils.timezone import now
from datetime import timedelta
import requests

ADD_TIME_INDEX = 0

HOST = environ['HOSTNAME']
SHARED_KEY = environ['SHARED_KEY']


data = {
            'creator': 'test_client',
            'key': SHARED_KEY,
            'internal_clients': 1,
            'external_clients': 2,
            'ts_start': now().strftime('%Y%m%dT%H%M%sZ'),
            'ts_stop': (now() + timedelta(hours=1)).strftime('%Y%m%dT%H%M%sZ'),
        }

print(data)


def get_url(path):
    return 'https://%s/api/v1/%s/?key=%s' % (HOST, path.rstrip('/'), SHARED_KEY)

response = requests.post(get_url('meeting/book/'), data, verify=False)

try:
    json_data = response.json()
except Exception:
    print((response.text))
    raise


from pprint import pprint
pprint(json_data)
meeting_id = json_data.get('meeting_id')
assert meeting_id

print('Klar?')
eval(input())

response = requests.post(get_url('meeting/unbook/%s/' % meeting_id))
pprint(response.text)
