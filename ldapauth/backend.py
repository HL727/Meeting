from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.dispatch import receiver
from django.utils.encoding import force_text
from django_auth_ldap import backend
from django_auth_ldap.backend import _LDAPUser

from ldapauth.permissions import LdapUserCustomerPermissions

if TYPE_CHECKING:
    from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class MividasLDAPBackend(backend.LDAPBackend):
    pass


@receiver(backend.populate_user)
def populate_user(user, ldap_user, **kwargs):

    LdapUserAttributes(user, ldap_user).populate()
    LdapUserCustomerPermissions(user, ldap_user).populate()


_orig_ldapuser_get_connection = _LDAPUser._get_connection


def _override_ldapuser_get_connection(self, *args, **kwargs):
    """Monkey patch django_auth_ldap.backend._LDAPUser to allow soft error for start_tls call"""
    connection = _orig_ldapuser_get_connection(self, *args, **kwargs)
    if getattr(settings, 'AUTH_LDAP_START_TLS', False) or 'ldaps://' in getattr(
        connection, '_uri', settings.LDAP_SERVER
    ):
        return connection

    if getattr(connection, 'has_tls', None):
        return connection

    try:
        connection.start_tls_s()
        connection.has_tls = True
    except Exception as e:
        if settings.LDAP_SSL_INSECURE:
            logger.info('Could not run START_TLS. Continuing anyway: %s', e)
        else:
            raise
    return connection


# Monkey patch
_LDAPUser._get_connection = _override_ldapuser_get_connection


class LdapUserAttributes:
    def __init__(self, user: User, ldap_user: backend._LDAPUser):
        self.user = user
        self.ldap_user = ldap_user
        self.mappings = {
            'email': ['email', 'mail'],
            'first_name': ['givenName', 'cn'],
            'last_name': ['familyName', 'sn'],
        }

    def populate(self):

        for user_attr, ldap_attrs in self.mappings.items():
            for ldap_attr in ldap_attrs:
                values = [v for v in self.ldap_user.attrs.get(ldap_attr, []) if v]
                if not values:
                    continue
                setattr(self.user, user_attr, force_text(values[0]))
                break
