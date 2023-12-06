from collections import Counter

from django.core.cache import cache

from django.db.models import Q

import re
from django.conf import settings

import sys


RERAISE_ERRORS = settings.DEBUG or getattr(settings, 'TEST_MODE', False)
STATS_PHONE_DOMAINS = set(settings.STATS_PHONE_DOMAINS or [])


ou_map = None

def check_change(title):
    def inner(fn):
        def inner2(guid):
            res = fn(guid)
            if res != guid:
                print(title, guid, '->', res)

            return res
        if not settings.DEBUG or 'manage.py' not in sys.argv:
            return fn
        return inner2

    return inner


@check_change('user')
def get_user(target):

    from datastore.models import acano as ds

    if not target:
        return ''

    return ds.User.objects.filter(Q(username=target) | Q(email=target)).values_list('username', flat=True).first()


@check_change('owner')
def get_owner(cospace_id):
    from meeting.models import Meeting

    from datastore.models.acano import CoSpace
    owner = CoSpace.objects.filter(cid=cospace_id)\
        .values_list('owner__username', flat=True).first()

    if owner:
        return owner
    return Meeting.objects.filter(provider_ref2=cospace_id).order_by('-ts_created').values_list('creator', flat=True).first()


@check_change('ou')
def get_ou(target):
    from datastore.models.ldap import LdapOU
    from provider.models.acano import CoSpace
    from statistics.models import DomainTransform
    global ou_map
    if not ou_map:
        ou_map = {}
        ou_map.update((df.domain, df.ou) for df in DomainTransform.objects.all())
        ou_map.update(CoSpace.objects.exclude(group='').values_list('uri', 'group'))

    if target in ('guest', 'streaming', 'recording') or not target:
        return ''

    target = target.lower()

    if '@' in target:
        user, domain = target.split('@', 1)
        if domain in ou_map:
            return ou_map[domain]

    if target in ou_map:
        return ou_map[target]

    if '@' in target:
        ou = LdapOU.objects.filter(Q(users__username=target) | Q(users__email=target)).values_list('name', flat=True).first()
        if ou:
            return ou

    if '.' in target and LdapOU.objects.filter(name=target.split('.')[0]):
        return target.split('.')[0]

    return ''


def get_internal_domains():
    from provider.models.provider import Provider
    from statistics.models import DomainRewrite

    cached = cache.get('stats.internal_domains')
    if cached is not None:
        return cached

    rewrites = dict(DomainRewrite.objects.all().values_list('alias_domain', 'transform__domain'))

    for domain in set(rewrites.values()):
        if domain not in rewrites:
            rewrites[domain] = ''

    for domain in Provider.objects.values_list('hostname', flat=True):
        if domain and domain not in rewrites:
            rewrites[domain] = ''

    cache.set('stats.internal_domains', rewrites, 30)
    return rewrites


def is_internal_leg(target):

    if '@' in target:
        return get_domain(target) in get_internal_domains()
    return target and target.isdigit()


def rewrite_internal_domains(target, only_internal=False, default_domain=None, internal_domains=None):

    domain = get_domain(target)

    if internal_domains is None:
        internal_domains = get_internal_domains()

    new_domain = internal_domains.get(domain, '').strip()

    if not new_domain and '@' not in target and is_internal_leg(target):
        new_domain = default_domain
    if not new_domain:
        return None if only_internal else target
    return '{}@{}'.format(target.split('@')[0], new_domain)


def get_ou_from_members(cospace_id):
    from datastore.models.ldap import LdapOU
    ous = LdapOU.objects.filter(users__cospaces__cid=cospace_id).values_list('name', flat=True)

    return Counter(ous).most_common(1)[0][0] if ous else None


def get_org_unit(target):
    "target is cospace_id or user jid"
    from organization.models import CoSpaceUnitRelation, UserUnitRelation
    from endpoint.models import Endpoint
    from statistics.models import DomainTransform

    if target in ('guest', 'streaming', 'recording') or not target:
        return None

    if '@' not in target or is_internal_leg(target):
        try:
            return CoSpaceUnitRelation.objects.filter(
                provider_ref=target.split('@')[0]).only('unit__id').get().unit
        except CoSpaceUnitRelation.DoesNotExist:
            pass

    try:
        return Endpoint.objects.get_from_uri(target, only='org_unit__id').org_unit
    except AttributeError:
        pass

    if '@' not in target:
        return

    try:
        return DomainTransform.objects.filter(domain=get_domain(target), org_unit__isnull=False).only('org_unit__id').first().org_unit
    except AttributeError:
        pass

    try:
        return UserUnitRelation.objects.filter(user_jid=target).only('unit__id').get().unit
    except UserUnitRelation.DoesNotExist:
        pass


def clean_target(target) -> str:
    if not target:
        return str(target) if target is not None else ''

    target = re.sub(r'^(sip|sips|h323|[a-z]{3,4}):', '', str(target))

    target = target.split(';', 1)[0]

    without_port = target[0].split(':', 1)[0]
    return without_port if '@' in without_port else target


def get_domain(target):

    try:
        return target.strip(';@').split(';')[0].split('@')[-1].split(':')[0].lower()
    except IndexError:
        return ''


PHONE_RE = re.compile(r'^(\+\d\d|00\d\d|0)\d{8,11}@[\d\.]+$')


def is_phone(target):

    if target.split('@')[0] == 'phone':
        return target

    if target.startswith('0') or target.startswith('+'):
        if '@' in target and get_domain(target) in STATS_PHONE_DOMAINS:
            return 'phone@{}'.format(get_domain(target))

    if PHONE_RE.match(target):
        return 'phone@{}'.format(get_domain(target))
    return ''



remote_re = re.compile(r'<remoteParty>([^<]+)')
local_re = re.compile(r'<localAddress>([^<]+)')


def check_spam(xml, ip=None):
    """
    basic first spam check.
    often bots use the same local as remote and endswith server ip
    or 1000@<hostname> as remote, NoAuth@<hostname> or aaaa...@<hostname>.

    returns number of finished spam calls or None if any record is not spam
    """
    record_count = xml.count('<record ')

    if '<call>' in xml or '<direction>outgoing' in xml or '<ivr' in xml:
        return

    unknown_count = xml.count('<reason>unknownDestination</reason>')
    spam_count = unknown_count

    local = local_re.findall(xml)
    remote = remote_re.findall(xml)

    if len(local) != len(remote):
        return

    for l, r in zip(local, remote):

        if get_domain(l) == get_domain(r):
            remote_user = r.split('@')[0]
            if remote_user in ('1000', 'NoAuth') or set(remote_user) == set('a'):
                spam_count += 1
            elif ip and get_domain(r) == ip:
                spam_count += 1

    if spam_count == record_count:
        return unknown_count
