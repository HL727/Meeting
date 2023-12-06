from typing import Optional

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.encoding import force_text
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from sentry_sdk import capture_exception

from customer.view_mixins import CustomerMixin, LoginRequiredMixin
from endpoint.ext_api.parser.tms_event import TMSEvent
from endpoint.models import Endpoint
from provider.exceptions import AuthenticationError


class DashboardView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'base_vue.html'

    def get(self, request, *args, **kwargs):
        if not settings.ENABLE_EPM or (self.customer and not self.customer.enable_epm):
            return redirect('/')
        return super().get(request, *args, **kwargs)


@csrf_exempt
def tms_event(request, customer_secret=None, endpoint_secret=None):

    if not request.body or b'<' not in request.body:
        _log_event(request.body, request.META.get('REMOTE_ADDR'))
        return HttpResponse(status=400)

    from . import tasks

    if not customer_secret and settings.EPM_EVENT_CUSTOMER_SECRET:
        return HttpResponse(status=403)

    if not endpoint_secret and settings.EPM_EVENT_ENDPOINT_SECRET:
        _log_event(
            request.body, request.META.get('REMOTE_ADDR'), error='No endpoint secret specified'
        )
        return HttpResponse(status=403)

    handle_endpoint_event = tasks.handle_endpoint_event

    if settings.ASYNC_CDR_HANDLING and not settings.TEST_MODE:
        handle_endpoint_event = handle_endpoint_event.delay  # type: ignore

    handle_endpoint_event(
        force_text(request.body),
        request.META.get('REMOTE_ADDR'),
        customer_secret=customer_secret,
        endpoint_secret=endpoint_secret,
    )

    return HttpResponse('<Ok />', status=200)


def _log_event(payload, remote_ip, endpoint=None, event='http'):
    try:
        from debuglog.models import EndpointCiscoEvent
        EndpointCiscoEvent.objects.store(ip=remote_ip, content=payload,
                                         event=event, endpoint=endpoint)
    except Exception:
        capture_exception()


def handle_tms_event(
    payload: bytes, remote_ip: Optional[str], customer_secret=None, endpoint_secret=None
):

    if customer_secret:
        customer = Endpoint.objects.get_customer_for_key(customer_secret, raise_exception=False)
        if not customer:
            raise Http404()
    elif settings.EPM_EVENT_CUSTOMER_SECRET:
        return HttpResponse('<Forbidden error="missing_customer_key" />', status=403)
    else:
        customer = None

    try:
        event = TMSEvent(payload, customer=customer, endpoint_secret=endpoint_secret)
        endpoint = event.handle_event()
    except (AuthenticationError, Endpoint.DoesNotExist):
        if settings.TEST_MODE or settings.DEBUG:
            raise
        _log_event(payload, remote_ip)
        return HttpResponse('<Error message="Invalid identification" />', status=403)
    else:
        _log_event(payload, remote_ip, endpoint, event=event.get_event_path().lower())


