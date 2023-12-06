import json
import os
from typing import Sequence

from django.conf import settings

from theme.utils import get_theme_settings
from .menu import MenuBuilder
from customer.models import Customer


def menu(request):

    if request.GET.get('customer'):
        customer = Customer.objects.get(pk=request.GET['customer'])
    else:
        customer = None

    if not request.resolver_match:
        return {}

    top_menu, sub_menu = MenuBuilder(request.path, request.resolver_match.func, customer).get_menu()

    return {
            'top_menu': top_menu,
            'sub_menu': sub_menu,
            }


def global_settings(request):

    return {
        'allow_sentry': settings.ALLOW_SENTRY,
        'has_organization': bool(settings.ENABLE_ORGANIZATION),
        'settings_json': json.dumps(get_javascript_settings(request)),
        'ldap_authentication': settings.LDAP_SERVER,
        'version': settings.VERSION,
        'release': settings.RELEASE,
        'http_host_without_port': request.get_host().split(':')[0],
        **get_prefetch_files(request),
    }


def check_license_flag(*flag_choices: Sequence[str]):
    for flag in flag_choices:
        if flag in settings.FLAGS:
            return True

    return False


def get_javascript_settings(request):
    from json_api.views import get_version_hash

    return {
        'enable_core': settings.ENABLE_CORE,
        'enable_epm': settings.ENABLE_EPM,
        'enable_organization': bool(settings.ENABLE_ORGANIZATION),
        'enable_group': bool(settings.ENABLE_GROUPS),
        'hostname': settings.HOSTNAME,
        'sentry_release': settings.RELEASE,
        'epm_hostname': settings.EPM_HOSTNAME,
        'enable_branding': check_license_flag('core:enable_branding', 'core:branding'),
        'enable_demo': check_license_flag('core:enable_demo', 'core:demo'),
        'enable_analytics': check_license_flag('core:enable_analytics') and request.user.is_staff,
        'enable_obtp': settings.EPM_ENABLE_OBTP,
        'enable_calendar': settings.EPM_ENABLE_CALENDAR,
        'customer_has_provider': False,
        'customer_has_calendar': False,
        'ldap_authentication': bool(settings.LDAP_SERVER),
        'license': get_license_status(request),
        'perms': {},
        'themes': settings.VUETIFY_THEMES,
        'theme_settings': get_theme_settings(),
        'version': settings.VERSION,
        'release': settings.COMMIT,
        'version_hash': get_version_hash(False),
        **get_user_settings(request),
        **get_customer_settings(request),
    }


def get_license_status(request):
    from license import get_license

    not_admin = not request.user.is_staff
    license = get_license()

    return {
        'status': {s: status.as_dict(not_admin) for s, status in license.get_full_status().items()},
        'warnings': license.get_warnings(),
    }


def get_prefetch_files(request):
    del request

    try:
        with open(os.path.join(settings.STATIC_ROOT, 'staticfiles.json')) as fd:
            paths = json.load(fd)['paths']
    except OSError:
        return {}

    prefixes = ['dist/']
    exts = ['.css', '.js']
    excludes = ['plotly']

    result = []

    for f in paths:
        if not any(f.startswith(prefix) for prefix in prefixes):
            continue
        if not any(f.endswith(ext) for ext in exts):
            continue
        if any(exclude in f for exclude in excludes):
            continue

        result.append(f)

    return {'prefetch_files': result}


def get_customer_settings(request):

    if not request.user.is_authenticated:
        return {}

    customer_id = request.session.get('customer_id')
    customer = None

    if customer_id:
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            pass

    if request.user.is_authenticated:
        customers = Customer.objects.get_for_user(request.user)
    else:
        customers = []

    if not customer and request.user.is_authenticated:
        for c in customers:
            if c.get_provider():
                customer = c
                break

    if not customer:
        return {}

    provider = customer.get_provider()

    from calendar_invite.models import Credentials
    have_calendar = bool(Credentials.objects.filter(customer=customer).exists())

    return {
        'customer_id': customer.pk,
        'provider_id': provider.pk if provider else None,
        'customers': [
            {
                'pk': customer.pk,
                'title': customer.title,
                'acano_tenant_id': customer.acano_tenant_id,
                'pexip_tenant_id': customer.pexip_tenant_id,
                'provider': customer.lifesize_provider_id,
            } for customer in customers],
        'is_pexip': provider.is_pexip if provider else False,
        'seevia_key': customer.seevia_key,
        'customer_has_provider': bool(provider),
        'customer_has_calendar': bool(have_calendar),
    }


def get_user_settings(request):
    return {
        'enable_debug_views': request.user.is_staff,
        'username': request.user.username,
        'perms': {
            'api': request.user.has_perm('provider.api_client'),
            'tenant': request.user.has_perm('provider.supporthelpers.tenants'),
            'staff': request.user.is_staff,
            'policy': request.user.is_staff,  # FIXME
            'admin': request.user.is_superuser,
        },
    }

