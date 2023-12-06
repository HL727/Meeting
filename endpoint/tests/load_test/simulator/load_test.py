import re
import unicodedata
from binascii import hexlify
from datetime import datetime
from ipaddress import IPv4Address
from random import choice, seed
from threading import Thread
from time import sleep

import requests

from . import mock_data

seed(0x934874578348734)


def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)


with open('/usr/share/dict/words') as fd:
    words = list(slugify(line.strip()).title() for line in fd)


class FakeEndpoint:
    def __init__(self, index=0, base_url='', base_status='', base_configuration=''):

        mac = '000000000000{}'.format(hexlify(chr(index).encode()).decode())[-12:].upper()
        self.mac = ':'.join(mac[i : i + 2] for i in range(0, 6 * 2, 2))
        self.serial = mac
        self.ip = IPv4Address('192.168.99.2') + index
        self.sip_uri = '{}@mocksystem.dev.mividas.com'.format(
            ('000000000000' + hexlify(chr(index).encode()).decode())[-12:].upper()
        )
        self.tick = 0
        self.base_url = base_url

        self.base_status = base_status
        self.base_configuration = base_configuration

        self.system_name = '{} {} {}'.format(choice(words), choice(words), choice(words))

    def base_replace(self, content: str):
        result = content.replace('1234@example.org', self.sip_uri)
        result = result.replace('sip@example.org', self.sip_uri)
        result = result.replace('1234567890', self.serial)
        result = result.replace('11:22:33:44:55:66', self.mac)
        result = result.replace('System name', self.system_name)
        result = result.replace(
            '2019-03-11T15:33:53+0000', datetime.now().replace(microsecond=0).isoformat()
        )
        return result

    def get_status(self):

        self.tick += 1

        result = self.base_replace(self.base_status)
        result = result.replace(
            '<Current>-1</Current>', '<Current>{}</Current>'.format(str(self.tick % 6))
        )

        return result

    def get_configuration(self):

        self.tick += 1

        result = self.base_replace(self.base_configuration)
        result = result.replace('System name', self.system_name)

        return result

    def send_call_event(self):

        self.tick += 1

        call_event = self.base_replace(mock_data.call_successful)
        disconnect_event = self.base_replace(mock_data.call_disconnect)

        if self.tick % 3 == 0:
            self.post('tms/event/', call_event)
        elif self.tick % 3 == 0:
            self.post('tms/event/', disconnect_event)

    def send_people_count(self):

        self.tick += 1

        if '<PeopleCount>' not in self.base_status:
            return

        head_count_request = self.base_replace(mock_data.head_count_request)
        head_count_request = head_count_request.replace(
            '<Current>-1</Current>', '<Current>{}</Current>'.format(str(self.tick % 6))
        )

        if self.tick % 3 == 0:
            self.post('tms/event/', head_count_request)

    def send_presence(self):

        self.tick += 1

        if '<PeoplePresence>' not in self.base_status:
            return

        presence_request = self.base_replace(mock_data.presence_request)
        presence_request = presence_request.replace(
            '<PeoplePresence>Yes</PeoplePresence>',
            '<PeoplePresence>{}</PeoplePresence>'.format('Yes' if self.tick % 3 == 0 else 'No'),
        )

        if self.tick % 3 == 0:
            return self.post('tms/event/', presence_request)

    def send_provision_beat(self):

        if self.tick % 3 == 0:
            self.post('tms/', self.base_replace(mock_data.provision_beat))

    def post(self, url, data):
        return requests.post(self.base_url + url, data)


class Manager:
    def __init__(self, num_endpoints: int, base_url=''):
        from .mock_data import configuration, status

        self.base_url = base_url
        self.endpoints = [
            FakeEndpoint(
                index=i,
                base_url=base_url,
                base_status=status[i % len(status)],
                base_configuration=configuration[i % len(configuration)],
            )
            for i in range(num_endpoints)
        ]
        self.count = num_endpoints
        self.tick = 0
        self.done = False

    def start_event_thread(self):
        def _run():
            while not self.done:
                sleep(1)
                self.send_event()

        thread = Thread(target=_run)
        thread.start()

    def get_endpoint(self, resolve_index: str) -> FakeEndpoint:
        index = sum(ord(s) for s in resolve_index) % self.count
        return self.endpoints[index]

    def send_event(self):
        self.tick += 1
        for i, endpoint in enumerate(self.endpoints):

            if i % self.tick == 0:
                endpoint.send_call_event()
            elif i % self.tick == 1:
                endpoint.send_people_count()
            elif i % self.tick == 2:
                endpoint.send_presence()
            elif i % self.tick == 3:
                endpoint.send_provision_beat()
