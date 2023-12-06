from datetime import date, timedelta, datetime, time
import sys
import django
import os
from random import randint

from django.utils.timezone import make_aware



def run():
    from django.conf import settings
    from endpoint.models import Endpoint
    from room_analytics.models import EndpointHeadCount
    from customer.models import Customer

    if not settings.DEBUG:
        print('DEBUG disabled. exiting...')
        return

    if not Endpoint.objects.all():
        print('Created test endpoint')
        Endpoint.objects.create(title='test', ip='test', customer=Customer.objects.first(), connection_type=Endpoint.CONNECTION.PASSIVE)

    today = date.today()
    cur = today - timedelta(days=30)
    while cur < today:
        cur += timedelta(days=1)
        for endpoint in Endpoint.objects.all():

            count = endpoint.room_capacity or 4

            for i in range(24 * 2):
                if randint(0, 4) != 1:
                    continue

                try:
                    ts = make_aware(datetime.combine(cur, time(i // 2, 30 if i % 2 else 0)))
                except Exception:  # summer time
                    continue
                EndpointHeadCount.objects.create(endpoint=endpoint, ts=ts, value=randint(0, count))


if __name__ == '__main__':
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conferencecenter.settings')
    django.setup()
    run()
