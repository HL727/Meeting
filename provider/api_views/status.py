# -*- coding: utf-8
import os
import shutil
import time
from threading import Thread
from collections import OrderedDict
from typing import Callable, Sequence, Tuple, TYPE_CHECKING, Dict, Any

import psutil
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.views import APIView
from sentry_sdk import capture_exception

from requests.exceptions import Timeout

from provider.exceptions import ResponseConnectionError, AuthenticationError, ResponseError
from provider.models.vcs import VCSEProvider
from django.urls import reverse

from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta

from customer.view_mixins import CustomerMixin
from django.http import Http404

from supporthelpers.views.mixins import get_product_name

if TYPE_CHECKING:
    from customer.models import Customer
    from provider.models.provider import Provider


def iter_timeout(it, timeout=10):

    result = {}
    limit = time.monotonic() + timeout

    try:
        for dct in it:
            result.update(dct)
            if time.monotonic() > limit:
                return {**result, 'error': 'Timeout error'}
    except (Timeout, ResponseError, ResponseConnectionError, AuthenticationError) as e:
        return {**result, 'error': str(e) or e.__class__.__name__}
    except Exception as e:
        if settings.DEBUG:
            raise
        else:
            capture_exception()
        return {**result, 'error': str(e)}
    return result


class ProviderStatusAPIView(CustomerMixin, APIView):

    def get(self, request, *args, **kwargs):

        provider_type = request.GET.get('type')

        if provider_type == 'acano':
            return Response(self.get_acano_status())
        if provider_type == 'server':
            return Response(self.get_server_status())
        if provider_type == 'pexip':
            return Response(self.get_pexip_status())
        if provider_type == 'vcs':
            return Response(self.get_vcs_status())

        raise Http404()

    def get_server_status(self) -> Dict[str, Any]:
        default = {
            'product_name': get_product_name(),
            'version': settings.VERSION,
            'release': settings.COMMIT,
        }
        if not self._has_all_customers():
            return default

        root = shutil.disk_usage('/')
        check = [('/', root)]

        cdr_root = os.path.join(settings.BASE_DIR, 'cdrdata')
        try:
            cdr = shutil.disk_usage(cdr_root)
        except OSError:
            pass
        else:
            if root.total != cdr.total:
                check.append((cdr_root, cdr))

        def _human(size):
            if size > 1024 * 1024:
                return '%.02f GB' % (size / (1024 * 1024 * 1024))
            return '%.02f MB' % (size / (1024 * 1024))

        limit = 10 * 1024 * 1024 * 1024

        memory = psutil.virtual_memory()

        return {
            **default,
            'warnings': [
                {
                    'type': 'disk',
                    'path': path,
                    'message': 'Low disk space: {} / {} free'.format(
                        _human(free.free), _human(free.total)
                    ),
                }
                for path, free in check
                if free.free < limit
            ],
            'cpu_percent': psutil.cpu_percent(),
            'memory': {'available': _human(memory.available), 'total': _human(memory.total)},
        }

    def get_status(self,
                   get_status_fn: Callable[['Provider', 'Customer', bool], Dict[str, Any]],
                   customer_providers: Sequence[Tuple['Customer', Sequence['Provider']]]):
        queue = OrderedDict()
        result = {}

        has_all_customers = self._has_all_customers()

        def _thread(provider: 'Provider', customer: 'Customer'):
            def _inner():
                cache_key = 'provider.status.{}.{}.{}'.format(provider.pk, provider.cluster_id, customer.pk if not has_all_customers else '0')
                lock = None
                if hasattr(cache, 'lock'):
                    lock = cache.lock(cache_key + 'lock', timeout=10)
                    lock.acquire(blocking_timeout=10)

                cached = cache.get(cache_key)
                if cached is not None:
                    result[provider.pk] = cached
                else:
                    result[provider.pk] = get_status_fn(provider, customer, has_all_customers)
                    cache.set(cache_key, result[provider.pk], 3)
                if lock:
                    try:
                        lock.release()
                    except Exception:
                        pass
            cur = Thread(target=_inner)
            cur.start()
            return cur

        for customer, providers in customer_providers:

            for provider in providers:
                if provider.pk not in queue:
                    queue[provider.pk] = _thread(provider, customer)

        for thread in queue.values():
            thread.join()

        return {pk: result[pk] for pk in queue if result.get(pk)}

    def get_acano_status(self):

        return self.get_status(self._single_acano_status, self.get_customer_providers('is_acano'))

    def get_pexip_status(self):

        return self.get_status(self._single_pexip_status, self.get_customer_providers('is_pexip'))

    def get_vcs_status(self):
        customer_providers = []
        for vcs_provider in VCSEProvider.objects.filter_for_user(self.request.user):
            customer = vcs_provider.customer or self._get_customer()

            providers = vcs_provider.get_clustered(include_self=True)
            customer_providers.append((customer, providers))

        return self.get_status(self._single_vcs_status, customer_providers)

    def _single_acano_status(self, provider, customer, has_all_customers=False):

        result = {
            'web_host': provider.web_host,
            'name': provider.title,
            'title': provider.title,
            'id': provider.id,
            'calls_url': reverse('calls'),
            'is_service_node': provider.is_service_node,
            'cluster_id': provider.cluster_id,
        }
        if has_all_customers:
            result['calls_url'] = '{}?provider={}&customer='.format(reverse('calls'), provider.pk)

        if provider.is_service_node:
            result.pop('calls_url', None)

        def _iter():
            api = provider.get_api(customer)
            status = api.get_status(timeout=5)

            if not has_all_customers:
                return {
                    'timesince': str(timedelta(seconds=int(status['uptimeSeconds']))),
                }

            yield {
                **status,
                'start': now().replace(microsecond=0) - timedelta(seconds=int(status['uptimeSeconds'])),
                'timesince': str(timedelta(seconds=int(status['uptimeSeconds']))),
            }
            alarms = api.get_alarms()

            if not provider.is_service_node and not api.check_cdr_enabled():
                alarms.append({'type': 'Found no CDR receiver matching this installation'})

            def _convert_time(alarms):
                result = []
                for a in alarms:
                    result.append({
                        **a,
                        'timesince': str(timedelta(seconds=int(a['timesince']))) if a.get('timesince') else '',
                    })
                return result

            yield {'alarms': _convert_time(alarms)}

            if provider.is_service_node:  # no calls
                return

            tenant_kwargs = {'tenant': customer.acano_tenant_id} if not self._has_all_customers() else {}

            yield {
                'call_count': api.get_calls(limit=1, **tenant_kwargs)[1],
            }
            yield {
                'call_leg_count': api.get_participants(only_internal=True, **tenant_kwargs, limit=1)[1],
            }

        result.update(iter_timeout(_iter()))

        return result

    def _single_pexip_status(self, provider, customer, has_all_customers=False):

        result = {
            'web_host': provider.web_host,
            'name': provider.title,
            'title': provider.title,
            'id': provider.id,
            'calls_url': reverse('calls'),
            'licenses': {},
        }
        if has_all_customers:
            result['calls_url'] = '{}?provider={}&customer='.format(reverse('calls'), provider.pk)

        def _iter():
            api = provider.get_api(customer, allow_cached_values=not has_all_customers)
            status = api.get_status(timeout=5)
            if not has_all_customers:
                return {
                    'uptime': status.get('uptime'),
                }

            yield {
                **status,
            }
            yield {'alarms': api.get_alarms()}

            tenant_kwargs = {'tenant': customer.pexip_tenant_id} if not self._has_all_customers() else {}

            yield {
                'call_count': api.get_calls(limit=1, **tenant_kwargs)[1],
            }
            yield {
                'call_leg_count': api.get_participants(only_internal=True, **tenant_kwargs, limit=1)[1],
            }

        result.update(iter_timeout(_iter()))
        return result

    def _single_vcs_status(self, provider, customer, has_all_customers=False):
        result = {
            'title': provider.title,
            'id': provider.id,
            'calls_url': '',
        }
        if has_all_customers:
            result['calls_url'] = '{}?provider={}'.format(reverse('calls'), provider.cluster_id)

        api = provider.get_api(customer)

        def _iter():
            status = api.get_status(timeout=5)
            yield {
                'uptime': status['uptime'],

            }
            yield {'alarms': api.get_alarms()}
            yield {'licenses': api.get_license_usage()}
            protocols = api.get_call_protocol_stats()
            yield {
                'protocols': protocols,
                'count': sum(protocols.values()),
            }
            yield {'cdr_enabled': api.check_cdr_enabled()}

        result.update(iter_timeout(_iter()))
        return result

    def get_customer_providers(self, type_check_attr: str) -> Sequence[Tuple['Customer', Sequence['Provider']]]:
        customer_providers = []

        for customer in self._get_customers():
            customer_provider = customer.get_provider()
            if not customer_provider or not getattr(customer_provider, type_check_attr):
                continue

            providers = customer_provider.get_clustered(include_self=True, only_call_bridges=False)
            customer_providers.append((customer, providers))

        return customer_providers
