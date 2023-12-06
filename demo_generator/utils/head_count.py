from random import randint

from datetime import timedelta, datetime, time
from django.utils.timezone import make_aware

from room_analytics.models import EndpointHeadCount

class DemoHeadCountGenerator(object):
    def __init__(self, customer, endpoints):
        self.customer = customer
        self.endpoints = endpoints

    def generate_endpoint_head_count(self, endpoint, start_date, noise=4):
        capacity = endpoint.room_capacity or 4
        generated = 0

        for i in range(24 * 2):

            # Generate some noise
            if noise and randint(0, noise) != 1:
                continue

            ts = make_aware(datetime.combine(start_date, time(i // 2, 30 if i % 2 else 0)))
            EndpointHeadCount.objects.create(endpoint=endpoint, ts=ts, value=randint(0, capacity))

            generated += 1

        return generated

    def generate_head_count(self, start_date, days_back):
        cur = start_date - timedelta(days=days_back)
        total_generated = 0

        while cur < start_date:
            cur += timedelta(days=1)
            for endpoint in self.endpoints:
                total_generated += self.generate_endpoint_head_count(endpoint, cur)

        return {
            'customer': self.customer.title,
            'affected_endpoints': len(self.endpoints),
            'total_generated': total_generated
        }
