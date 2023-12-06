from django.conf import settings
from django.utils.module_loading import import_string
from django.utils.timezone import now

from datastore.models.ldap import LdapOU
from provider.exceptions import AuthenticationError

LDAP_JID_REPLACE = getattr(settings, 'LDAP_JID_REPLACE', None)


def update_ldap_user(user, ldapconn=None, commit=None):

    if not ldapconn:
        try:
            from provider.ext_api.ldapconn import LDAPConnection
        except ImportError:
            return False, ldapconn  # no ldap

        try:
            ldapconn = LDAPConnection.from_django_settings()
        except AttributeError:
            try:
                search = settings.LDAP_USER_SEARCH
                ldapconn = LDAPConnection(settings.AUTH_LDAP_SERVER_URI.split('//')[1],
                                          search.base_dn,
                                          settings.AUTH_LDAP_BIND_DN,
                                          settings.AUTH_LDAP_BIND_PASSWORD,
                                          )
            except (AttributeError, IndexError):
                pass

        if not ldapconn or not ldapconn.server_ip:
            return False, ldapconn

    get_user_from_cms_user = getattr(settings, 'LDAP_GET_USER_FROM_CMS_USER', None)

    if get_user_from_cms_user:
        if isinstance(get_user_from_cms_user, str):
            get_user_from_cms_user = import_string(get_user_from_cms_user)
    else:
        def get_user_from_cms_user(user, ldapconn):
            username = user.username.split('@')[0]
            result = ldapconn.get_user(username)
            if not result and LDAP_JID_REPLACE:
                return ldapconn.get_user(user.username.replace(LDAP_JID_REPLACE[1], LDAP_JID_REPLACE[0]))
            return result

    ldap_user = get_user_from_cms_user(user, ldapconn)

    user.last_synced_ldap = now()

    if ldap_user:
        user.ldap_username = ldap_user['username']
        if not user.email and ldap_user.get('email'):
            user.email = ldap_user['email']
        if not user.name and ldap_user.get('name'):
            user.name = ldap_user['name']
        user.ldap_ou = LdapOU.objects.get_from_ldap_string(ldap_user['dn'])

    if commit is not False:
        user.save()

    if ldap_user:
        callback = getattr(settings, 'LDAP_USER_MATCHED_CALLBACK', None)
        if callback:
            if isinstance(callback, str):
                callback = import_string(callback)
            callback(user, ldap_user)

    return user, ldapconn


def sync_ldap_ous_from_ldap(ldapconn=None):

    try:
        from provider.models.provider import LdapProvider
    except ImportError:
        return False  # no ldap
    from provider.ext_api.ldapconn import LDAPConnection

    try:
        ldapconn = LDAPConnection.from_django_settings()
    except (AttributeError, AuthenticationError):
        pass
    else:
        for ou in ldapconn.list_groups():
            LdapOU.objects.get_from_ldap_string(ou['dn'])

    try:
        ldapconn = ldapconn or LdapProvider.objects.all()[0].get_api()
    except (IndexError, AuthenticationError):
        return

    try:
        for ou in ldapconn.list_groups():
            LdapOU.objects.get_from_ldap_string(ou['dn'])
    except AuthenticationError:
        return
