import logging
from os import environ

import ldap
import re
import ldap.modlist as modlist
from ldap.filter import escape_filter_chars
from ldap.controls import SimplePagedResultsControl

from ldap.ldapobject import ReconnectLDAPObject

from provider.exceptions import AuthenticationError, ResponseConnectionError

logger = logging.getLogger(__name__)


def escape(s):
    result = escape_filter_chars(s)
    return result


def get_ou_list(ou_str):
    "get ldap-query for nested ous from comma separated string"

    if isinstance(ou_str, bytes):
        ou_str = ou_str.decode('utf-8')

    parts = ou_str.split(',')

    return ','.join('ou={}'.format(escape(ou)) for ou in parts)


def utf8_format(dct):

    result = []
    for k, v in dct.items():
        if isinstance(v, str):
            v = v.encode('utf-8')
        elif isinstance(v, (list, tuple)):
            v = [vv.encode('utf-8') if isinstance(vv, str) else vv for vv in v]
        result.append((k, v))
    return dict(result)


class LDAPConnection:

    ADD_USERPASSWORD = False
    override_bind = None

    def __init__(
        self,
        server_ip,
        domain,
        username,
        password,
        add_user_password=None,
        override_ssl=False,
        visible_domain='',
        is_active_directory=False,
        enable_referrals=False,
        verify_certificates=False,
    ):

        self.server_ip = str(server_ip)
        self.username = username
        self.password = password

        if 'dc=' in domain.lower():
            self.dn = domain
            domain = '.'.join(re.split(r'dc=', domain, flags=re.IGNORECASE)[1:]).replace(',', '')
        else:
            self.dn = 'dc=%s' % ',dc='.join(domain.split('.'))
        self.domain = domain
        self.visible_domain = visible_domain or domain

        self.ldap_client = None
        self.has_ssl = False
        self.enable_referrals = enable_referrals
        self.verify_certificates = verify_certificates

        if add_user_password is None:
            self.add_user_password = self.ADD_USERPASSWORD
        else:
            self.add_user_password = add_user_password

        self.override_ssl = override_ssl

        self.is_active_directory = is_active_directory

    def bind(self, use_dn=False, require_ssl=False):

        if self.override_bind:  # for tests
            result = self.override_bind(use_dn=False, require_ssl=False)
            if result is not None:
                return result

        if self.ldap_client:
            if not require_ssl or self.has_ssl:
                return self.ldap_client

        if '://' in self.server_ip:
            server = self.server_ip
            self.has_ssl = 'ldaps://' in server
        elif require_ssl and not self.override_ssl:
            server = 'ldaps://{}'.format(self.server_ip)
            self.has_ssl = True
        else:
            server = 'ldap://{}'.format(self.server_ip)

        if '@' in self.username:  # AD/email
            username_full = self.username
        elif ',' in self.username:  # LDAP DN
            username_full = self.username
        elif '\\' in self.username:  # AD/Domain
            username_full = self.username
        elif use_dn:
            username_full = 'cn={},{}'.format(self.username, self.dn)
        else:
            username_full = '{}@{}'.format(self.username, self.domain)

        if self.verify_certificates:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_HARD)
        else:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)

        ldap_client = ReconnectLDAPObject(server)

        if environ.get('SSL_CERT_FILE'):
            ldap_client.set_option(ldap.OPT_X_TLS_CACERTFILE, environ.get('SSL_CERT_FILE'))

        if self.verify_certificates:
            ldap_client.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_HARD)
        else:
            ldap_client.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

        ldap_client.set_option(ldap.OPT_X_TLS_NEWCTX, 0)  # apply tls

        if self.enable_referrals:
            ldap_client.set_option(ldap.OPT_REFERRALS, 1)
        else:
            ldap_client.set_option(ldap.OPT_REFERRALS, 0)

        if not self.has_ssl:
            try:
                ldap_client.start_tls_s()
            except Exception:
                logger.warning('Could not start TLS. Trying to continue anyway')

        try:
            ldap_client.simple_bind_s(username_full, self.password)
        except ldap.INVALID_CREDENTIALS as e:
            ldap_client.unbind()
            if not use_dn and username_full != self.username:
                try:
                    return self.bind(use_dn=True)
                except ldap.INVALID_CREDENTIALS:
                    pass
            try:
                msg = e.args[0]['desc']
            except (IndexError, AttributeError, KeyError):
                msg = str(e)

            logger.warning('Could not bind with user %s', username_full)
            raise AuthenticationError('LDAP Bind failed: {}'.format(msg), e)
        except ldap.SERVER_DOWN as e:
            raise ResponseConnectionError('LDAP server not available', e)
        except ldap.INVALID_DN_SYNTAX:
            ldap_client.unbind()

            if not use_dn:
                if username_full == self.username:
                    raise
                return self.bind(use_dn=True)

        self.ldap_client = ldap_client

        return ldap_client

    def unbind(self):
        if self.ldap_client:
            self.ldap_client.unbind()
        self.ldap_client = None

    @classmethod
    def from_django_settings(cls, **kwargs):
        from django.conf import settings as s

        connection_settings = {
            'server_ip': s.LDAP_SERVER,
            'domain': s.LDAP_DOMAIN,
            'visible_domain': s.LDAP_DOMAIN_ALIAS,
            'username': s.LDAP_USERNAME,
            'password': s.LDAP_PASSWORD,
            'override_ssl': getattr(s, 'LDAP_OVERRIDE_SSL', False),
            'enable_referrals': s.LDAP_ENABLE_REFERRALS,
            'verify_certificates': not s.LDAP_SSL_INSECURE,
            'is_active_directory': getattr(s, 'LDAP_IS_ACTIVE_DIRECTORY', True),
        }

        for k, v in list(kwargs.items()):
            if v:
                connection_settings[k] = v
        return cls(**connection_settings)

    def _format_user(self, data, raw=False):

        user_name = ''
        user_login = ''
        user_email = ''

        def decode(s):
            if isinstance(s, bytes):
                return s.decode('utf-8')
            return s or ''

        if data[1]:
            user_name = decode(data[1].get('displayName', [b''])[0])
            user_login = decode(data[1].get('sAMAccountName', [b''])[0])
            user_email = decode(data[1].get('mail', [b''])[0] or b'')

        ous = re.findall(r'(?:ou|,cn)=([^,]+)', decode(data[0]), re.IGNORECASE)

        cn = re.search(r'(?:uid=|cn)=([^,]+)', decode(data[0]), re.IGNORECASE)

        result = {
            'name': user_name,
            'sAMAccountName': user_login or cn.group(1) if cn else '',
            'username': user_login or cn.group(1) if cn else '',
            'group': '',
            'ou': '',
            'ous': '',
            'full_username': '{}@{}'.format(user_login or cn.group(1) if cn else '', self.visible_domain),
            'cn': cn.group(1) if cn else data[0],
            'dn': data[0],
            'email': user_email,
        }

        if raw:
            result['raw'] = data[1]

        if ous:
            result.update({
                'group': ous[0],
                'ou': ous[0],
                'ous': ','.join(ous),
            })
        return result

    def _format_group(self, data):
        if not data[1]:
            return {}

        name = data[1].get('name')
        if not name:
            name = data[0].split(',')[0].split('=')[0]  # attr=<name>,attr2=other,dc=example

        ous = re.findall(r'ou=([^,]+)', data[0], re.IGNORECASE)

        cached = [None]

        def get_user_count(force=False):
            if cached[0] is not None and not force:
                return cached[0]

            cached[0] = len(self.list_users(','.join(ous), scope=ldap.SCOPE_ONELEVEL) if ous else name[0])
            return cached[0]

        return {
            'name': name[0],
            'dn': data[0],
            'ou': ous[0] if ous else '',
            'ous': ','.join(ous),
            'get_user_count': get_user_count,
        }

    def get_user(self, username=None, base_query=None, raw=False, extra_attrs=None):

        if username is None:
            username = self.username

        username = username.split('@', 1)[0]  # TODO
        if ',' in username:
            username = username.split(',', 1)[0].split('=', 1)[-1]

        if base_query and not base_query.startswith('('):
            base_query = '({})'.format(base_query)

        ldap_filter = ('(&(|(sAMAccountName={})(userPrincipalName={})(uid={}))'
                       '(|(objectClass=user)(objectClass=inetOrgPerson)){})'
                       ).format(escape(username),
                                escape('{}@{}'.format(username, self.domain)),
                                escape(username), base_query or '')

        attrs = ['objectGUID', 'objectSid', 'displayName', 'objectClass', 'sAMAccountName', 'mail']
        if extra_attrs:
            attrs.extend(extra_attrs)

        result = self.filter(ldap_filter, attrs)

        if result and result[0][0]:
            return self._format_user(result[0], raw=raw)

        return None

    def get_group(self, group_name):

        ldap_filter = '(&({})(objectClass=organizationalUnit))'.format(get_ou_list(group_name))

        result = self.filter(ldap_filter, ['name'])

        if result and result[0][0] and result[0][1]:
            return self._format_group(result[0])

        return None

    def list_groups(self, scope=ldap.SCOPE_SUBTREE):

        result = self.filter('objectClass=organizationalUnit', ['name'], scope=scope)

        if result and result[0][0]:
            return [self._format_group(r) for r in result if r[0]]
        return []

    def list_users(self, org_unit, scope=ldap.SCOPE_SUBTREE):

        attrs = ['objectGUID', 'objectSid', 'displayName', 'objectClass', 'sAMAccountName']
        result = self.filter('objectClass=user', attrs, base_dn=get_ou_list(org_unit), scope=scope)

        if result and result[0][0]:
            return [self._format_user(r) for r in result if r[0]]
        return []

    def search_users(self, username, org_unit=None):

        attrs = ['objectGUID', 'objectSid', 'displayName', 'objectClass', 'sAMAccountName']

        result = self.filter(
            '(&('
                '(objectClass=user)'
                '(|('
                    '(sAMAccountName=*{}*)'
                    '(userPrincipalName=*{}*)'
                    '(displayName=*{}*)'
                '))'
            '))'.format(escape(username), escape(username), escape(username)),
                attrs, base_dn=get_ou_list(org_unit) if org_unit else None)

        if result[0][0]:
            return [self._format_user(r) for r in result if r[0]]
        return []

    def filter(self, ldap_filter, attrs=None, base_dn=None, scope=ldap.SCOPE_SUBTREE):

        attrs = attrs or []

        if not ldap_filter.startswith('('):
            ldap_filter = '(%s)' % ldap_filter

        base_dn = '{},{}'.format(base_dn or '', self.dn).strip(',')

        try:
            result = self.bind().search_s(base_dn,
                                          scope, ldap_filter, attrs)
        except ldap.SIZELIMIT_EXCEEDED:
            result = list(self._iter_filter(ldap_filter, attrs, base_dn, scope))

        return result

    def _get_password(self, password):

        return ('"%s"' % escape(password)).encode("utf-16-le")

    def add_user(self, org_unit, username, name, password, email=''):

        if self.is_active_directory:
            return self.add_ad_user(org_unit, username, name, password, email)
        else:
            return self.add_simple_user(org_unit, username, name, password, email)

    def add_simple_user(self, org_unit, username, name, password=None, email=''):

        display_name = name or username

        attrs = {}
        attrs['objectclass'] = ['top', 'person', 'inetOrgPerson']
        attrs['cn'] = username
        attrs['sn'] = display_name
        attrs['ou'] = org_unit
        attrs['displayName'] = display_name

        if email:
            attrs['mail'] = email

        ldif = modlist.addModlist(utf8_format(attrs))

        dn = 'cn={},ou={},{}'.format(escape(username), escape(org_unit), self.dn)

        result = self.bind().add_s(dn, ldif)

        if result and password:
            self.change_password(org_unit, username, password)

        return result

    def add_ad_user(self, org_unit, username, name, password, email=''):

        display_name = name or username
        last_name = name.split()[-1] if name else ''

        attrs = {}
        attrs['objectClass'] = ['top', 'person', 'organizationalPerson', 'user']
        attrs['cn'] = username
        attrs['sn'] = last_name
        attrs['ou'] = org_unit.split(',')[0]
        attrs['displayName'] = display_name
        attrs['name'] = display_name
        attrs['userAccountControl'] = str(65536 | 512 | 2)
        attrs['sAMAccountName'] = username[:20]
        if self.add_user_password:
            attrs['userPassword'] = password
        attrs['userPrincipalName'] = '{}@{}'.format(username, self.domain)

        if email:
            attrs['mail'] = email

        ldif = modlist.addModlist(utf8_format(attrs))

        dn = 'cn={},{},{}'.format(escape(username), get_ou_list(org_unit), self.dn)

        result = self.bind().add_s(dn, ldif)

        if result:
            self.change_password(org_unit, username, password)

        # activate user
        ldif = [(ldap.MOD_REPLACE, 'userAccountControl', str(65536 | 512).encode('utf-8'))]

        dn = 'cn={},{},{}'.format(escape(username), get_ou_list(org_unit), self.dn)
        self.bind().modify_s(dn, ldif)

        return result

    def delete_user(self, org_unit, cn):

        dn = 'cn={},{},{}'.format(escape(cn), get_ou_list(org_unit), self.dn)

        return self.bind().delete_s(dn)

    def move_group(self, org_unit, new_ou):

        dn = '{},{}'.format(get_ou_list(org_unit), self.dn)

        return self.bind().rename_s(dn, 'ou={}'.format(escape(org_unit.split(',')[0])), '{},{}'.format(get_ou_list(new_ou), self.dn))

    def move_user(self, org_unit, cn, new_ou):

        dn = 'cn={},{},{}'.format(escape(cn), get_ou_list(org_unit), self.dn)

        return self.bind().rename_s(dn, 'cn={}'.format(escape(cn)), '{},{}'.format(get_ou_list(new_ou), self.dn))

    def update_field(self, org_unit, cn, field, value):

        dn = 'cn={},{},{}'.format(escape(cn), get_ou_list(org_unit), self.dn)

        ldif = [(ldap.MOD_REPLACE, field, value.encode('utf-8'))]

        return self.bind().modify_s(dn, ldif)

    def change_password(self, org_unit, cn, new_password):

        pad = self._get_password(new_password)

        ldif = [(ldap.MOD_REPLACE, 'unicodePwd', pad)] * 2  # needs two, otherwise old one is working
        if self.add_user_password:
            ldif += [(ldap.MOD_REPLACE, 'userPassword', new_password.encode('utf-8'))]

        dn = 'cn={},{},{}'.format(escape(cn), get_ou_list(org_unit), self.dn)

        return self.bind(require_ssl=True).modify_s(dn, ldif)

    def add_org_unit(self, group_name):

        attrs = {}
        attrs['objectClass'] = ['top', 'organizationalUnit']
        attrs['ou'] = group_name.split(',')[0]
        # attrs['name'] = group_name

        ldif = modlist.addModlist(utf8_format(attrs))

        dn = '{},{}'.format(get_ou_list(group_name), self.dn)

        return self.bind().add_s(dn, ldif)

    def delete_org_unit(self, group_name):

        dn = '{},{}'.format(get_ou_list(group_name), self.dn)

        return self.bind().delete_s(dn)

    def _iter_filter(self, ldap_filter, attrs, base_dn, scope=ldap.SCOPE_SUBTREE, pagesize=1000):

        conn = self.bind()

        pcontrol = SimplePagedResultsControl(True, size=pagesize, cookie='')

        while True:
            try:
                msgid = conn.search_ext(base_dn, ldap.SCOPE_ONELEVEL, ldap_filter,
                                     attrs, serverctrls=[pcontrol])
            except ldap.LDAPError:
                raise

            try:
                rtype, rdata, rmsgid, serverctrls = conn.result3(msgid)
            except ldap.LDAPError:
                raise

            yield from rdata

            pcontrols = [c for c in serverctrls
                        if c.controlType == SimplePagedResultsControl.controlType]

            if pcontrols and pcontrols[0].cookie:
                pcontrol.cookie = pcontrols[0].cookie
            else:
                break
