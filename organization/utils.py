from typing import TYPE_CHECKING

from django.conf import settings

from .models import UserUnitRelation, OrganizationUnit

if TYPE_CHECKING:
    from datastore.models.acano import User


FIELDS = getattr(settings, 'LDAP_SET_ORGANISATION_FIELDS', None)
CACHE_LIMIT = 5

org_unit_cache = {}


def update_cms_ldap_user(cms_user: 'User', ldap_user):
    from customer.models import Customer

    global org_unit_cache

    if not FIELDS:
        return

    result = []

    for field in FIELDS:
        if field in ldap_user:
            result.append(ldap_user[field])
        elif ldap_user.get('raw') and field in ldap_user['raw']:
            result.extend([f.decode('utf-8') for f in ldap_user['raw'][field]])
        else:
            break

    result = tuple(result)

    if not result:
        return

    if result in org_unit_cache:
        org_unit = org_unit_cache[result]
    else:
        customer = Customer.objects.find_customer(cms_user.tenant.tid if cms_user.tenant else '')
        org_unit, created = OrganizationUnit.objects.get_or_create_by_list(result, customer=customer)

        if len(org_unit_cache) > CACHE_LIMIT:
            org_unit_cache.clear()

        org_unit_cache[result] = org_unit

    UserUnitRelation.objects.update_or_create(user_jid=cms_user.username, defaults=dict(unit=org_unit))

