from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils.encoding import force_text

from ldapauth.utils import check_user_group_member
from supporthelpers.models import CustomerPermission

if TYPE_CHECKING:
    from django_auth_ldap import backend
    from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class LdapUserPermissions:
    def __init__(self, user: User, ldap_user: backend._LDAPUser):
        self.user = user
        self.ldap_user = ldap_user

        self.filters = {
            'is_staff': '',
            'is_superuser': '',
            **(getattr(settings, 'LDAP_ADMIN_FILTERS', None) or {}),
        }

    def populate(self):
        self.populate_superuser()
        self.populate_staff()

    def populate_superuser(self):
        if not self.filters['is_superuser']:
            return

        user = self.user

        if check_user_group_member(user, self.ldap_user, self.filters['is_superuser']):
            user.is_superuser = True
            user.is_staff = True
            logger.info('LDAP user %s is in superuser group. Set as superuser', user.username)
        else:
            user.is_superuser = False
            logger.info('LDAP user %s was not in superuser group', user.username)

    def populate_staff(self):
        if not self.filters['is_staff']:
            return

        user = self.user

        if user.is_superuser:
            return

        if check_user_group_member(user, self.ldap_user, self.filters['is_staff']):
            user.is_staff = True
            logger.info('LDAP user %s is in admin group. Set as admin', user.username)
        else:
            user.is_staff = False
            logger.info('LDAP user %s was not in admin group. Set as regular user', user.username)


class LdapUserCustomerPermissions(LdapUserPermissions):
    def populate(self):
        super().populate()
        self.populate_customers()

    def populate_customers(self):
        group_field = getattr(settings, 'LDAP_GROUP_ATTRIBUTE', None)
        if not group_field:
            return

        logger.info('LDAP customer connection is active using field %s', group_field)
        self.create_customer_connections(group_field)

    def create_customer_connections(self, group_field):
        groups = [force_text(g) for g in self.ldap_user.attrs.get(group_field) or []]
        user = self.user

        if user.is_staff:
            user.is_active = True
            count = CustomerPermission.objects.filter(user=user).delete()
            logger.info(
                'User %s is admin, removed %s explicit connections', user.username, count[0]
            )

        elif groups:
            from customer.models import Customer

            customers = Customer.objects.filter_by_keys(groups)
            if not customers:
                user.is_active = False
                logger.info(
                    'User %s is not admin but has no matching customer. Set as inactive',
                    user.username,
                )
            else:
                user.is_active = True
                logger.info(
                    'User %s is not admin and %s matching customer. Set as active',
                    user.username,
                    len(customers),
                )
            for customer in customers:
                CustomerPermission.objects.get_or_create(user=user, customer=customer)
            CustomerPermission.objects.filter(user=user).exclude(customer__in=customers).delete()
        else:
            user.is_active = False
            logger.info(
                'User %s is not admin and have no values in LDAP attribute. Set as inactive',
                user.username,
            )


