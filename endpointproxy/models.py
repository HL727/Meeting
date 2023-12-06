import hmac
import uuid
from datetime import datetime
from random import randint
from time import sleep
from typing import Dict, Optional, Union

import requests
from django.conf import settings
from django.db import models
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from customer.models import Customer
from provider.exceptions import NotFound, ResponseError

PORT_INTERVAL = settings.EPM_PROXY_PORT_INTERVAL


def new_key():
    return uuid.uuid4().hex


class EndpointProxyManager(models.Manager):

    def update_authorized_keys(self):

        content = self.get_authorized_keys()
        if not settings.EPM_PROXY_AUTHORIZED_KEYS:
            return

        try:
            with open(settings.EPM_PROXY_AUTHORIZED_KEYS, 'w') as fd:
                fd.write(content)
        except IOError:
            pass

    def get_authorized_keys(self):

        result = []
        for proxy in self.get_queryset().all():

            options = [
            '''command="echo 'No shell allowed'"''',
            'no-agent-forwarding',
            'no-X11-forwarding',
            'no-pty',
            'permitopen="none:65530"',
            'permitlisten="{}"'.format(proxy.reserved_port),
            ]

            name = '{} {} {}'.format(proxy.first_ip, proxy.last_connect_ip, slugify(proxy.name))
            result.append('{} ssh-rsa {} {}'.format(','.join(options), proxy.ssh_key, name))

        return '\n'.join(result)

    def get_for_ip(self, ip, customer=None):

        for net in EndpointProxyIPNet.objects.all():
            if net.contains(ip):
                if not customer or customer.pk == net.proxy.customer_id:
                    return net.proxy

        return None

    def get_customers_for_password(self, password: str):
        return Customer.objects.filter(epm_settings__proxy_password=password)


class EndpointProxy(models.Model):

    customer = models.ForeignKey(Customer, null=True, on_delete=models.CASCADE)
    name = models.CharField(_('Namn'), max_length=100, blank=True)

    ts_created = models.DateTimeField(auto_now_add=True, editable=False)
    ts_activated = models.DateTimeField(null=True, blank=True, editable=False)

    first_ip = models.GenericIPAddressField(unpack_ipv4=True, blank=True, null=True)

    is_online = models.BooleanField(default=False)

    last_active = models.DateTimeField(null=True, blank=True, editable=False)
    last_connect = models.DateTimeField(null=True, blank=True, editable=False)
    last_connect_ip = models.GenericIPAddressField(unpack_ipv4=True, blank=True, null=True)

    secret_key = models.CharField(max_length=256, unique=True, default=new_key)
    ssh_key = models.TextField()
    proxy_version = models.CharField(max_length=10, blank=True)

    use_for_firmware = models.BooleanField(null=True, default=False, blank=True)
    internal_hostname = models.CharField(max_length=200, null=True, blank=True)
    override_rooms_hostname = models.CharField(max_length=200, null=True, blank=True)

    reserved_port = models.IntegerField(null=True, unique=True)

    objects = EndpointProxyManager()

    new_key = new_key

    @property
    def http_proxy_settings(self):
        # TODO https mode to proxy. traffic is always ssh tunneled though
        # probably needs different insecure flag for proxy connection
        return {
                'http': 'http://{}'.format(self.proxy_uri),
                'https': 'http://{}'.format(self.proxy_uri),
            }

    @property
    def proxy_uri(self):
        return '{}:{}'.format(settings.EPM_PROXY_HOST, self.reserved_port)

    def activate(self, commit=True):
        self.ts_activated = self.ts_activated or now()
        if not self.reserved_port:
            self.reserve_port(commit=False)
        if commit:
            self.save()

    def _post(self, url):
        response = requests.post('http://proxy.local.mividas.com/{}'.format(url),
                                 proxies=self.http_proxy_settings,
                                 timeout=10)

        data = response.json()
        if response.status_code == 404:
            raise NotFound('URL not found', response)
        if data.get('status') != 'OK':
            raise ResponseError('Invalid status', response)
        return data

    def check_active(self):

        was_online = self.is_online

        self.is_online = is_online = False

        try:
            self._post('status/')
        except NotFound:  # old version without status endpoints
            is_online = True
        except Exception:
            try:
                self._post('')
            except NotFound:  # old version with broken status endpoints
                is_online = True
            except Exception:
                pass
        else:
            is_online = True

        if is_online:
            self.last_active = now()
            self.is_online = True

        self.save()

        if was_online != self.is_online:
            EndpointProxyStatusChange.objects.create(proxy=self, is_online=self.is_online)

        if self.is_online and not was_online:
            self.initialize_endpoints()

    def initialize_endpoints(self):
        from endpoint.models import Endpoint
        from endpoint.tasks import sync_endpoint_bookings_locked_delay, update_all_endpoint_status

        update_all_endpoint_status.delay({'proxy': self.id})

        for endpoint_id in Endpoint.objects \
                .filter(meetings__ts_stop__gt=now(), meetings__backend_active=True, proxy=self)\
                .values_list('id', flat=True):
            sync_endpoint_bookings_locked_delay(endpoint_id)

    def restart(self):
        try:
            self._post('restart/')
        except Exception:
            pass
        else:
            if not settings.TEST_MODE:
                sleep(2)
            self.check_active()

    def reserve_port(self, commit=True):

        for _i in range(100):

            port = randint(*PORT_INTERVAL)
            if not EndpointProxy.objects.filter(reserved_port=port):
                self.reserved_port = port
                if commit:
                    self.save()
                return True

        raise ValueError('Could not reserve port')

    def get_valid_hash(self, ts: Union[str, datetime]) -> str:

        if isinstance(ts, datetime):
            ts = ts.isoformat()

        return hmac.new(self.ssh_key.encode(), ts.encode(), 'sha256').hexdigest()

    def get_hash_params(self, ts: Union[datetime, None] = None) -> Dict[str, str]:

        ts = (ts or now()).isoformat()
        return {'ts': ts, 'hash': self.get_valid_hash(ts)}

    def validate_hash_timestamp(self, ts: Union[datetime, str, None]) -> Optional[datetime]:
        try:
            ts_parsed = parse_datetime(ts)
        except Exception:
            ts_parsed = None

        if not ts_parsed:
            return None

        if abs((ts_parsed - now()).total_seconds()) > 5 * 60:
            return None

        return ts_parsed

    def validate_hash(self, hash: str, ts: Union[datetime, str, None] = None) -> bool:
        if not ts:
            return False

        ts_parsed = self.validate_hash_timestamp(ts)

        return hmac.compare_digest(hash, self.get_valid_hash(ts_parsed))

    def __str__(self):
        return self.name


class EndpointProxyStatusChange(models.Model):
    proxy = models.ForeignKey(EndpointProxy, on_delete=models.CASCADE, related_name='changes')
    ts_created = models.DateTimeField(default=now)
    is_connect = models.BooleanField(default=False)
    is_online = models.BooleanField(null=True, default=None)


class EndpointProxyIPNet(models.Model):

    proxy = models.ForeignKey(EndpointProxy, on_delete=models.CASCADE, related_name='ip_nets')
    ip_net = models.CharField(max_length=100)

    def __str__(self):
        return self.ip_net

    def contains(self, ip):

        from ipaddress import IPv4Interface
        return IPv4Interface(ip).ip in IPv4Interface(self.ip_net).network


class CustomerProxyIpNet(models.Model):

    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, editable=False)
    ip_net = models.CharField(max_length=100)


def keys_callback(sender, **kwargs):
    EndpointProxy.objects.update_authorized_keys()


models.signals.post_save.connect(keys_callback, sender=EndpointProxy)
models.signals.post_delete.connect(keys_callback, sender=EndpointProxy)
