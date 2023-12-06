from __future__ import annotations


def dn_is_member(dn, base_dn) -> bool:
    """
    Check if dn is base_dn or a subgroup thereof
    """
    if not dn or not base_dn:
        return False

    if dn.lower().endswith(',{}'.format(base_dn).lower()):
        return True
    return False


def check_user_group_member(user, ldap_user, group_dn: str) -> bool:
    if ldap_user.attrs.get('memberOf'):
        if group_dn in ldap_user.attrs['memberOf']:
            return True

    if dn_is_member(ldap_user.dn, group_dn):
        return True

    return False
