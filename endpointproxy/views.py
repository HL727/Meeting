from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from audit.models import AuditLog
from endpoint.models import CustomerSettings
from endpointproxy.forms import EndpointProxyForm, EndpointProxyRegistrationForm
from endpointproxy.models import EndpointProxy


@csrf_exempt
def registration(request):

    form = EndpointProxyRegistrationForm(request.POST)
    if not form.is_valid():
        AuditLog.objects.store_request(request, 'Proxy request verification failed')

        return JsonResponse(
            {
                'status': 'error',
                'server_type': 'Mividas',
                'message': 'Invalid data: {}'.format(list(form.errors.keys())),
                'errors': list(form.errors.keys()),
                'time': now().isoformat(),
            }
        )
    proxy, created = form.save(ip=request.META.get('REMOTE_ADDR'))

    return _proxy_response(request, proxy)


@csrf_exempt
def check_active(request):

    form = EndpointProxyForm(request.POST)
    if not form.is_valid():
        AuditLog.objects.store_request(request, 'Proxy request verification failed')
        return JsonResponse(
            {
                'status': 'error',
                'server_type': 'Mividas',
                'message': 'Invalid data: {}'.format(','.join(form.errors.keys())),
                'errors': list(form.errors.keys()),
                'time': now().isoformat(),
            }
        )

    proxy = form.get_proxy()
    proxy.check_active()
    return _proxy_response(request, proxy)


def _proxy_response(request: HttpRequest, proxy: EndpointProxy):
    from endpointproxy.ssh_helpers import get_remote_host_key

    if proxy.customer:
        c_settings = CustomerSettings.objects.get_for_customer(proxy.customer_id)
        public_ca = c_settings.ca_certificates
    else:
        public_ca = ''

    base = {
        'status': 'OK',
        'proxy_status': 'Unconfirmed',
        'server_type': 'Mividas',
        **proxy.get_hash_params(),
    }
    if not proxy.ts_activated:
        AuditLog.objects.store_request(
            request,
            'Proxy {} ({}) is not approved. Identified using {}'.format(
                proxy.pk, proxy, 'secret key' if request.POST.get('secret_key') else 'ssh_key'
            ),
        )
        return JsonResponse(base)

    AuditLog.objects.store_request(
        request,
        'Proxy {} ({}) identified using {}'.format(
            proxy.pk, proxy, 'secret key' if request.POST.get('secret_key') else 'ssh_key'
        ),
    )

    return JsonResponse(
        {
            **base,
            'proxy_status': 'OK',
            'proxy_name': proxy.name,
            'secret_key': proxy.secret_key,
            'public_ca': public_ca,
            'use_for_firmware': bool(proxy.use_for_firmware),
            'use_for_communication': False,  # TODO
            'ssh_settings': {
                'remote_port': settings.EPM_PROXY_SERVER_PORT,
                'global_connect': True,
                'hostname': None,
                'user': 'epmproxy',
                'known_hosts': get_remote_host_key(),
                'tunnel_port': proxy.reserved_port,
            },
        }
    )
