from __future__ import annotations
import json
import logging
import re
from typing import TYPE_CHECKING

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from audit.models import AuditLog


logger = logging.getLogger('audit')


if TYPE_CHECKING:
    from customer.models import Customer


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):

        request.audit_logged = False

        if request.method in ('HEAD', 'GET'):
            return self.get_response(request)

        self.data_keys = self.parse_data_keys(request)
        response = None  # noqa

        try:
            response = self.get_response(request)
        finally:
            self.log(request, response)

        return response

    def parse_data_keys(self, request: HttpRequest):

        data_keys = 'unknown: {}'.format(request.content_type)

        from conferencecenter.sentry import redact_values

        if request.content_type.endswith('json') or (
            request.content_type != 'multipart/form-data' and request.body.startswith(b'{')
        ):
            try:
                if request.body:
                    return redact_values(json.loads(request.body))
            except Exception:
                pass
        elif request.POST:
            return redact_values(request.POST)

        return data_keys

    def log(self, request: HttpRequest, response: HttpResponse = None):
        try:
            if request.audit_logged:  # type: ignore  # noqa
                return
        except AttributeError:
            pass

        try:
            return self._real_log(request, response)
        except Exception as e:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            try:
                logger.warn('Exception when storing audit log: %s', str(e))
            except Exception:
                logger.warn('Exception when storing audit log: %s', str(e.__class__.__name__))

    def _real_log(self, request: HttpRequest, response: HttpResponse = None):

        # ignore events
        if re.match(r'^/(tms/|cdr/(cms|pexip)/[^/]+/$|epm/proxy/check_active/)', request.path):
            return

        try:
            from customer.utils import get_customer_from_request
            customer = get_customer_from_request(request)
        except Exception:
            customer = None

        cluster = None
        if customer and AuditLog.objects.get_scope(request) == 'http':
            cluster = self._get_cluster(request, customer)

        AuditLog.objects.store_request(
            request,
            response=response,
            data_keys=self.data_keys,
            customer=customer,
            cluster=cluster,
        )

    def _get_cluster(self, request: HttpRequest, customer: Customer = None):

        cluster = None

        if request.user.is_staff:
            cluster_id = request.GET.get('provider') or request.POST.get('provider') or None
            if cluster_id and cluster_id.isdigit():
                from provider.models.provider import Cluster

                cluster = Cluster.objects.filter(pk=cluster_id).only('id').first()

        if not cluster:
            try:
                api = customer.get_api()
                return api.cluster
            except Exception:
                pass

        return None

