import random
import math
import uuid
from random import randint

from datetime import timedelta, datetime
from django.utils.timezone import make_aware

from statistics.models import Call, Leg


class DemoCallsGenerator(object):

    def __init__(self, customer, server, endpoint_server, endpoints, cospaces):
        self.customer = customer
        self.endpoints = endpoints
        self.cospaces = cospaces
        self.server = server
        self.endpoint_server = endpoint_server

    def generate_call_leg(self, call, leg_target, is_endpoint=False):
        generated_type = 'legs'

        leg_data = dict(
            guid=uuid.uuid4(),
            call=call,
            target=leg_target,
            ou='',
            ts_start=call.ts_start,
            ts_stop=call.ts_stop,
            tenant=self.customer.tenant_id,
            duration=20 + randint(0, 60),
            server=self.server,
        )

        if is_endpoint:
            leg_data['endpoint'] = random.choice(self.endpoints)
            leg_data['tenant'] = ''
            leg_data['server'] = self.endpoint_server
            generated_type = 'endpoint_legs'

        leg = Leg.objects.create(**leg_data)

        return leg, generated_type

    def generate_call(self, call_date, random_cospace, server):
        cospace = 'default'
        cospace_id = ''

        if random_cospace:
            cospace_item = random.choice(self.cospaces)
            cospace = cospace_item.get('name', '')
            cospace_id = cospace_item.get('id')

        if random.random() < 0.1:
            ts_start = make_aware(datetime.fromordinal(call_date.toordinal()) + timedelta(minutes=randint(0, 24 * 60)))
        else:
            minutes = randint(0, 900)
            probability = None
            while not probability:
                if math.pow(math.sin(math.pi*2*(minutes/900)),4) + 0.2 > random.random():
                    probability = minutes
                else:
                    minutes = randint(0, 900)

            cur_dt = datetime.fromordinal(call_date.toordinal()) + timedelta(hours=20)
            ts_start = make_aware(cur_dt - timedelta(minutes=probability))

        ts = dict(ts_start=ts_start, ts_stop=ts_start + timedelta(minutes=randint(10, 120)))

        return Call.objects.create(
            guid=uuid.uuid4(),
            tenant=self.customer.tenant_id,
            cospace=cospace,
            cospace_id=cospace_id,
            server=server,
            **ts
        )

    def generate_call_statistics(self, start_date, days_back, number_of_calls, participants, endpoint_percent, random_cospace):
        cur = start_date - timedelta(days=days_back)
        total_generated = {
            'calls': 0,
            'endpoint_legs': 0,
            'legs': 0
        }

        while cur < start_date:
            cur += timedelta(days=1)

            for _i in range(number_of_calls):

                if not self.should_generate_call(cur):
                    continue

                server = self.server
                is_endpoint = self.should_be_endpoint_leg(endpoint_percent)
                if is_endpoint:
                    server = self.endpoint_server

                call = self.generate_call(cur, random_cospace, server)
                total_generated['calls'] += 1

                participants_amount = randint(1, participants)
                for participant_index in range(participants_amount):

                    if not self.should_generate_leg():
                        continue

                    leg, leg_type = self.generate_call_leg(
                        call=call,
                        leg_target='demo-user-{}@mividas.com'.format(participant_index),
                        is_endpoint=is_endpoint,
                    )
                    total_generated[leg_type] += 1

        return {
            'customer': self.customer.title,
            'affected_endpoints': len(self.endpoints),
            'total_generated': total_generated
        }

    def should_generate_call(self, call_date):

        # Lower stats saturday and sunday
        if call_date.weekday() > 4 and randint(0, 20) > 5:
            return False

        # Add some noise
        if randint(0, 100) < 20:
            return False

        return True

    def should_generate_leg(self):

        return True

    def should_be_endpoint_leg(self, endpoint_percent):
        return endpoint_percent and random.random() < endpoint_percent
