import json
import os
import subprocess
import sys
from random import randint
from time import time, sleep
from django.utils.translation import gettext_lazy as _

import django
import requests

def init_environment():
    from statistics.models import Server
    from provider.models.provider import Provider
    from customer.models import CustomerMatch, Customer

    provider = Provider.objects.get_or_create(title=_('Load test'), subtype=Provider.SUBTYPES.pexip)[0]
    server = Server.objects.get_or_create(type=Server.PEXIP, name=_('Load test'), cluster=provider.cluster)[0]
    customer = Customer.objects.first() or Customer.objects.get_or_create(title='defaults')[0]
    customer2 = Customer.objects.exclude(pk=customer.pk).first() or Customer.objects.get_or_create(title='defaults2')[0]

    CustomerMatch.objects.get_or_create(cluster=provider.cluster, regexp_match=r'^[0-3]', customer=customer)
    CustomerMatch.objects.get_or_create(cluster=provider.cluster, regexp_match=r'^[4-6]', customer=customer2)

    cdr_url = 'http://localhost:8765{}'.format(server.get_cdr_path())
    return cdr_url


def run(argv=None):

    argv = argv or sys.argv

    if len(argv) < 2:
        raise ValueError('argv is empty. ')

    from provider.models.provider import Provider
    provider = Provider.objects.get(pk=sys.argv[1])

    from customer.models import Customer
    api = provider.get_api(Customer.objects.first())

    if not os.environ.get('LDAP_PASSWORD'):
        print('LDAP_PASSWORD needed')
        return


    for i in range(100):
        _create(api, i + 1)


def _create(api, i):

    server_id = api._create_object('ldapServers', {
        'address': 'ldap-dev.int.mividas.com',
        'name': 'TEST ldap-dev.int.mividas.com',
        'username': 'uid=svc,ou=people,dc=dev,dc=mividas,dc=com',
        'password': os.environ.get('LDAP_PASSWORD'),
        'portNumber': '636',
        'secure': 'true',
    })
    print('server', server_id)

    mapping_id = api._create_object('ldapMappings', {
        'jidMapping': '$uid$@acano29.dev.mividas.com',
        'nameMapping': '$cn$',
        'coSpaceNameMapping': '$cn$ cospace',
        'coSpaceUriMapping': '$uid$.cospace',
    })
    print('mapping', mapping_id)

    ivr_branding_profile_id = api._create_object('ivrBrandingProfiles', {
        'resourceLocation': 'http://127.0.0.1/ivrtest/'
    })
    print('ivr_branding_profile', ivr_branding_profile_id)

    call_branding_profile_id = api._create_object('callBrandingProfiles', {
        'resourceLocation': 'http://127.0.0.1/calltest/'
    })
    print('call_branding_profile', call_branding_profile_id)

    call_leg_profile_id = api._create_object('callLegProfiles', {
    })
    print('call_leg_profile', call_leg_profile_id)

    call_profile_id = api._create_object('callProfiles', {
    })
    print('call_profile', call_profile_id)

    tenant_id = api._create_object('tenants', {
        'name': 'MT test tenant {}'.format(i),
        'ivrBrandingProfile': ivr_branding_profile_id,
        'callBrandingProfile': call_branding_profile_id,
        'callLegProfile': call_leg_profile_id,
        'callProfile': call_profile_id,
    })
    print('tenant', tenant_id)

    source_id = api._create_object('ldapSources', {
        'server': server_id,
        'mapping': mapping_id,
        'tenant': tenant_id,
        'baseDn': 'ou=tenant{},ou=people,dc=dev,dc=mividas,dc=com'.format(i),
        'filter': '(objectClass=person)',
        'nonMemberAccess': 'true',
    })
    print('source', source_id)

    return server_id, mapping_id, source_id, tenant_id


if __name__ == '__main__':
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conferencecenter.settings')
    django.setup()
    run()
