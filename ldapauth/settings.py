import os

import ldap
from django_auth_ldap.config import LDAPSearch

from ldapauth.srvdns import LdapSrvPool


def global_env(key, default=None):
    import os
    return os.environ.get(key) or default


true_values = ('true', 'True', True, '1')
true_or_empty_values = true_values + ('',)
false_values = ('false', 'False', False, '0')
false_or_empty_values = false_values + ('',)


def get_ldap_settings(env=None):

    env = env or global_env

    if not env('LDAP_SERVER', ''):
        return {}

    proto = 'ldaps' if env('LDAP_SSL', '') in true_values else 'ldap'
    AUTH_LDAP_SERVER_URI = LdapSrvPool(proto, env('LDAP_SERVER', ''))

    AUTH_LDAP_BIND_DN = env('LDAP_BIND_DN', '')
    AUTH_LDAP_BIND_PASSWORD = env('LDAP_BIND_PASSWORD', '')

    AUTH_LDAP_GLOBAL_OPTIONS = {
        ldap.OPT_NETWORK_TIMEOUT: 6.06,
        ldap.OPT_TIMEOUT: 30,
    }
    AUTH_LDAP_CONNECTION_OPTIONS = {}

    if env('LDAP_SSL_INSECURE') in true_values:
        AUTH_LDAP_GLOBAL_OPTIONS[ldap.OPT_X_TLS_REQUIRE_CERT] = ldap.OPT_X_TLS_ALLOW
        AUTH_LDAP_CONNECTION_OPTIONS[ldap.OPT_X_TLS_REQUIRE_CERT] = ldap.OPT_X_TLS_NEVER
    else:
        AUTH_LDAP_CONNECTION_OPTIONS[ldap.OPT_X_TLS_REQUIRE_CERT] = ldap.OPT_X_TLS_HARD

    import certifi

    cert_files = [env('SSL_CERT_FILE'), '/etc/ssl/certs/ca-certificates.crt', certifi.where()]
    LDAP_CERT_FILE = [cf for cf in cert_files if cf and os.path.exists(cf)][0]

    AUTH_LDAP_GLOBAL_OPTIONS[ldap.OPT_X_TLS_CACERTFILE] = LDAP_CERT_FILE
    AUTH_LDAP_CONNECTION_OPTIONS[ldap.OPT_X_TLS_CACERTFILE] = LDAP_CERT_FILE

    AUTH_LDAP_CONNECTION_OPTIONS[ldap.OPT_X_TLS_NEWCTX] = 0  # apply tls

    if env('LDAP_ENABLE_REFERRALS') in true_values:
        AUTH_LDAP_CONNECTION_OPTIONS[ldap.OPT_REFERRALS] = 1
    else:
        AUTH_LDAP_CONNECTION_OPTIONS[ldap.OPT_REFERRALS] = 0

    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        env('LDAP_FILTER_BASE', ''), ldap.SCOPE_SUBTREE, env('LDAP_FILTER', "(|(sAMAccountName=%(user)s)(userPrincipalName=%(user)s))")
    )

    LDAP_ENABLE_REFERRALS = env('LDAP_ENABLE_REFERRALS') in true_values

    LDAP_ADMIN_FILTERS = {
        "is_staff": env('LDAP_ADMIN_FILTER', ''),
        "is_superuser": env('LDAP_SUPERUSER_FILTER', ''),
    }

    LDAP_GROUP_ATTRIBUTE = env('LDAP_GROUP_ATTRIBUTE', '')
    LDAP_ENABLE_REFERRALS = env('LDAP_ENABLE_REFERRALS', '') in true_or_empty_values

    AUTH_LDAP_ALWAYS_UPDATE_USER = True

    LDAP_JID_FIELD = env('LDAP_JID_FIELD', '') or ''
    if '/' in LDAP_JID_FIELD:
        LDAP_JID_REPLACE = LDAP_JID_FIELD.split('/')[1:]
        LDAP_JID_FIELD = LDAP_JID_FIELD.split('/')[0]

    AUTHENTICATION_BACKENDS = [
        "axes.backends.AxesBackend",
        "ldapauth.backend.MividasLDAPBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]
    if env('LDAP_ENABLE_LOCAL_ACCOUNTS') in false_or_empty_values:
        AUTHENTICATION_BACKENDS.pop()

    del env
    del proto
    return locals()


