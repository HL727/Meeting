import json
from collections import Counter
from datetime import timedelta
from typing import Union

import typing

from cacheout import Cache
from django.db import models
from django.db.models.functions import Cast
from django.utils.timezone import now

from customer.models import Customer, CustomerMatch
from datastore.models.pexip import Email, Conference, ConferenceAlias, ConferenceAutoParticipant, EndUser, \
    Theme
from provider.models.pexip import PexipSpace
from shared.utils import partial_update_or_create, partial_update, SyncBatcher
from . import bulk_iter, sync_method
from ..models.base import ProviderSync
from ..models.customer import Tenant
from .ldap import update_ldap_user
from provider.exceptions import NotFound
import logging


if typing.TYPE_CHECKING:
    from provider.ext_api.pexip import PexipAPI

logger = logging.getLogger(__name__)

DEFAULT_INCREMENTAL = 5


def _get_conference_customer(conference, provider):
    overridden_space = PexipSpace.objects.filter(cluster=provider, external_id=conference['id'])\
        .select_related('customer').first()

    if overridden_space and overridden_space.customer_id:
        return overridden_space.customer


def _get_conference_tenant(conference, provider):

    customer = _get_conference_customer(conference, provider)
    if customer:
        tenant_id = customer.get_pexip_tenant_id()
        if not tenant_id:
            return None
        return _get_tenant_obj(tenant_id, provider)

    return _get_tenant(conference, provider)


def _get_user_customer(user, provider):
    from provider.models.pexip import PexipEndUser
    overridden_user = PexipEndUser.objects.filter(cluster=provider, external_id=user['id']) \
        .select_related('customer').first()

    if overridden_user and overridden_user.customer_id:
        return overridden_user.customer


def _get_user_tenant(user, provider):
    customer = _get_user_customer(user, provider)
    if customer:
        tenant_id = customer.get_pexip_tenant_id()
        if not tenant_id:
            return None
        return _get_tenant_obj(tenant_id, provider)
    return _get_tenant(user, provider)


def _get_tenant(obj, provider):
    match = _get_match(obj, provider)
    if not match:
        return None

    tenant_id = match.customer.get_pexip_tenant_id() if match.customer_id else match.tenant_id
    if tenant_id:
        return _get_tenant_obj(tenant_id, provider)

    return None


tenant_cache = Cache(ttl=30)


def _get_tenant_obj(tenant_id, provider):
    cached = tenant_cache.get((tenant_id, provider.pk))
    if cached:
        return cached
    result = Tenant.objects.get_or_create(tid=tenant_id, provider=provider)[0]
    tenant_cache.set((tenant_id, provider.pk), result)
    return result


def _get_match(obj, provider, only_existing=False):

    result = CustomerMatch.objects.get_match(obj, cluster=provider)
    if result and only_existing and not result.pk:
        return None
    return result


def _get_email(email, provider):

    if not email:
        return None
    try:
        return Email.objects.get_or_create(email=email, provider=provider)[0]
    except IndexError:
        return None


def _extract_id_from_url(url):
    if not isinstance(url, str):
        return url
    if url.isdigit():
        return int(url)

    if not url.startswith('/'):
        return None

    parts = url.strip('/').rsplit('/', 1)
    return parts[-1] if parts else None


theme_cache = Cache(ttl=30)


def _get_theme(tid, provider):

    tid = _extract_id_from_url(tid)

    if not tid:
        return None

    cached = theme_cache.get((tid, provider.pk))
    if cached:
        return cached

    result = Theme.objects.get_or_create(tid=tid, provider=provider).order_by('-last_synced')[0]
    theme_cache.set((tid, provider.pk), result)
    return result


def _get_conference(conference_id, provider, data=None) -> Union[Conference, None]:

    conference_id = _extract_id_from_url(conference_id)

    if not conference_id and not data:
        return None

    try:
        return Conference.objects.get(cid=conference_id, provider=provider)
    except Conference.DoesNotExist:
        return Conference.objects.get_or_create(cid=conference_id, provider=provider, defaults={'name': data['name']} if data else {})[0]


def sync_all_pexip(provider, customer=None, incremental=False):
    return list(sync_all_pexip_iter(provider, customer=customer, incremental=incremental))


def sync_all_pexip_iter(provider, customer=None, incremental=False):

    cluster = provider.cluster if provider.cluster_id else provider

    if not customer:
        customer = Customer.objects.all()[0]

    if not cluster.is_pexip:
        return

    partial_update_or_create(ProviderSync, provider=cluster, defaults={
        ('last_incremental_sync' if incremental else 'last_full_sync'): now(),
    })

    all_start = now()

    api = cluster.get_api(customer)
    api.is_syncing = True

    def _log_and_run(step, fn):
        start = now()
        result = fn(api, incremental=incremental)
        if incremental:
            logger.info('Incremental sync of {} for cluster %s in %s secs'.format(step), cluster, (now() - start).total_seconds())
        else:
            logger.info('Full sync of {} for cluster %s in %s secs'.format(step), cluster, (now() - start).total_seconds())
        return step, result

    yield _log_and_run('version', sync_pexip_version)
    yield _log_and_run('tenants', sync_tenants_from_pexip)
    yield _log_and_run('users', sync_users_from_pexip)
    yield _log_and_run('conferences', sync_conferences_from_pexip)

    if incremental:
        yield _log_and_run('automatic_participants', sync_automatic_participants_from_pexip)
        yield _log_and_run('conference_aliases', sync_conference_aliases_from_pexip)
        yield _log_and_run('conferences', sync_conferences_from_pexip)  # make sure new ones are fully populated
    else:
        yield _log_and_run('themes', sync_themes_from_pexip)

    api.is_syncing = False

    if incremental:
        logger.info('Incremental sync of cluster %s in %s secs', cluster,
                    (now() - all_start).total_seconds())
    else:
        logger.info('Full sync of cluster %s in %s secs', cluster,
                    (now() - all_start).total_seconds())


@sync_method
def sync_pexip_version(api: 'PexipAPI', incremental=False):

    version = api.get_version() or ''
    if version != api.provider.software_version:
        api.provider.software_version = version
        api.provider.save(update_fields=['software_version'])


@sync_method
def sync_users_from_pexip(api: 'PexipAPI', incremental=False):

    i = 0

    provider = api.cluster
    start = now()

    batcher = SyncBatcher(time_update_fields=['last_synced'], defaults={'is_active': True})

    filter_kwargs = {}
    if incremental:
        last_sync = ProviderSync.objects.filter(provider=api.cluster).values_list('users_last_sync', flat=True).first()
        if not last_sync:
            last_sync = now() - timedelta(hours=DEFAULT_INCREMENTAL)
        filter_kwargs['creation_time__gte'] = last_sync.isoformat()

    tenant_count = Counter()

    for u, obj in bulk_iter(api.cluster, EndUser, 'uid', api._iter_all_users(**filter_kwargs), 'id'):
        i += 1
        if i % 50 == 0:
            print(i)

        obj = sync_single_user_full(api, data=u, obj=obj, batcher=batcher)
        tenant_count[obj.tenant_id] += 1

    batcher.commit()

    if not incremental:
        EndUser.objects.filter(provider=provider, last_synced__lt=start - timedelta(minutes=5), is_active=True).update(is_active=False)
    ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(users_last_sync=now()))

    for tenant in Tenant.objects.filter(provider=api.cluster, pk__in=tenant_count.keys()):
        if tenant.user_count != tenant_count[tenant.pk]:
            partial_update(tenant, {
                'user_count': tenant_count[tenant.pk],
                'last_count_change': now(),
            })


@sync_method
def sync_single_user_full(api: 'PexipAPI', user_id=None, obj=None, data=None, ldapconn=None, batcher=None):

    provider = api.cluster

    if not user_id:
        if not obj and not (data and data.get('id')):
            raise ValueError('No id provided')
        user_id = obj.uid if obj else data.get('id')

    try:
        data = data or api.get_user(user_id)
    except NotFound:
        return

    from provider.models.pexip import PexipEndUser
    end_user = PexipEndUser.objects.filter(cluster=api.cluster, external_id=data['id']).only('organization_unit__id').first()

    cur = {
        'uuid': data.get('uuid', ''),
        'email': _get_email(data.get('primary_email_address'), provider),
        'sync_tag': data.get('sync_tag', ''),
        'avatar_url': data.get('avatar_url', ''),
        'tenant': _get_user_tenant(data, provider),
        'customer': _get_user_customer(data, provider),
        'match': _get_match(data, provider, only_existing=True),
        'first_name': data.get('first_name', ''),
        'last_name': data.get('last_name', ''),
        'display_name': data.get('display_name', ''),
        'description': data.get('description', ''),
        'is_active': True,
        'last_synced': now(),
        'organization_unit': end_user.organization_unit if end_user else None,
    }

    if obj:
        if batcher:
            batcher.partial_update(obj, cur)
        else:
            partial_update(obj, cur)
        created = False
    else:
        obj, created = partial_update_or_create(EndUser, uid=data.get('id'), provider=api.cluster, defaults=cur)

    if created or obj.should_update_ldap:
        u, ldapconn = update_ldap_user(obj, ldapconn=ldapconn)

    return obj


@sync_method
def sync_tenants_from_pexip(api: 'PexipAPI', incremental=False):

    tenants = Customer.objects.filter(lifesize_provider=api.cluster).exclude(pexip_tenant_id='').values_list('pexip_tenant_id', 'title')

    for t in tenants:
        Tenant.objects.get_or_create(tid=t[0], provider=api.cluster, defaults=dict(name=t[1]))

    ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(tenants_last_sync=now()))


@sync_method
def sync_themes_from_pexip(api: 'PexipAPI', incremental=False):

    filter_kwargs = {}
    if incremental:
        last_sync = ProviderSync.objects.filter(provider=api.cluster).values_list('themes_last_sync', flat=True).first()
        if not last_sync:
            last_sync = now() - timedelta(hours=DEFAULT_INCREMENTAL)
        filter_kwargs['last_updated__gt'] = last_sync.isoformat()
        raise ValueError('Themes does not yet support filter on update timestamp')

    start = now()
    valid = set()

    batcher = SyncBatcher(time_update_fields=['last_synced'], defaults={'is_active': True})

    for t in api.get_themes(**filter_kwargs):
        cur, created = batcher.partial_update_or_create(Theme, tid=t['id'], provider=api.cluster, defaults={
            'name': t['name'],
            'uuid': t.get('uuid', ''),
            'last_synced': now(),
            'is_active': True,
        })
        valid.add(cur.pk)

    batcher.commit()

    if not incremental:
        Theme.objects.filter(provider=api.cluster, last_synced__lt=start - timedelta(minutes=5), is_active=True).update(is_active=False)

    ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(themes_last_sync=now()))


@sync_method
def sync_conferences_from_pexip(api: 'PexipAPI', incremental=False):

    i = 0

    start = now()

    batcher = SyncBatcher(time_update_fields=['last_synced'], defaults={'is_active': True})

    filter_kwargs = {}
    if incremental:
        last_sync = ProviderSync.objects.filter(provider=api.cluster).values_list('cospaces_last_sync', flat=True).first()
        if not last_sync:
            last_sync = now() - timedelta(hours=DEFAULT_INCREMENTAL)
        filter_kwargs['creation_time__gte'] = last_sync.isoformat()

    tenant_count = Counter()

    for c, obj in bulk_iter(api.cluster, Conference, 'cid', api._iter_all_cospaces(**filter_kwargs), 'id'):
        i += 1
        if i % 50 == 0:
            print(i)

        obj = sync_single_conference_full(api, c.get('id'), data=c, obj=obj, batcher=batcher)
        tenant_count[obj.tenant_id] += 1

    batcher.commit()

    if not incremental:
        Conference.objects.filter(provider=api.cluster, last_synced__lt=start - timedelta(minutes=5), is_active=True).update(is_active=False)
    ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(cospaces_last_sync=now()))

    valid = set()
    from django.db.models import Count
    for pk, count in CustomerMatch.objects.filter(cluster=api.cluster, conference__is_active=True).annotate(count=Count('conference')).values_list('id', 'count'):
        CustomerMatch.objects.filter(pk=pk).update(room_count=count)
        valid.add(pk)

    for tenant in Tenant.objects.filter(provider=api.cluster, pk__in=tenant_count.keys()):
        if tenant.cospace_count != tenant_count[tenant.pk]:
            partial_update(tenant, {
                'cospace_count': tenant_count[tenant.pk],
                'last_count_change': now(),
            })

    CustomerMatch.objects.filter(cluster=api.cluster).exclude(pk__in=valid).update(room_count=0)
    set_scheduled_meeting_conferences(api)


def set_scheduled_meeting_conferences(api: 'PexipAPI'):

    from meeting.models import Meeting

    scheduled_ids = (
        Meeting.objects.filter(
            provider=api.cluster, ts_stop__gt=now() - timedelta(days=7), existing_ref=False
        )
        .exclude(provider_ref='')
        .annotate(provider_ref2_int=Cast('provider_ref2', output_field=models.IntegerField()))
        .values_list('provider_ref2_int', flat=True)
    )
    Conference.objects.filter(
        is_active=True,
        provider=api.cluster,
        is_scheduled=False,
        cid__in=scheduled_ids,
        sync_tag='sync_tag',
        scheduled_id=None,
    ).update(is_scheduled=True)


@sync_method
def sync_conference_from_alias(api, alias, timeout=3):
    try:
        result, count = api.find_cospaces({'aliases__alias': alias}, timeout=timeout, limit=1)
    except NotFound:
        return
    else:
        if result:
            return sync_single_conference_full(api, data=result[0])


@sync_method
def sync_single_conference_full(api, conference_id=None, obj=None, data=None, batcher=None):

    provider = api.cluster

    if not conference_id:
        if not obj and not (data and data.get('id')):
            raise ValueError('No id provided')
        conference_id = obj.cid if obj else data.get('id')

    try:
        conference = data or api.get_cospace(conference_id)
    except NotFound:
        return

    logger.debug('Start sync for conference_id=%s, name %s', conference_id, conference.get('name', ''))

    space = PexipSpace.objects.filter(cluster=api.cluster, external_id=conference['id']).only('organization_unit__id').first()

    c = conference
    cur = {
        'name': c.get('name', ''),
        'description': c.get('description', ''),
        'allow_guests': c.get('allow_guests', True),
        'guest_pin': c.get('guest_pin', ''),
        'pin': c.get('pin', ''),
        'tag': c.get('tag', ''),
        'sync_tag': c.get('sync_tag', ''),
        'email': _get_email(c.get('primary_owner_email_address', ''), provider),
        'scheduled_id': c.get('scheduled_id'),
        'service_type': c.get('service_type', ''),
        'tenant': _get_conference_tenant(conference, provider),
        'customer': _get_conference_customer(conference, provider),
        'match': _get_match(conference, provider, only_existing=True),
        'theme': _get_theme(c.get('theme'), provider),
        'full_data': json.dumps({k: v for k, v in conference.items() if k not in {'aliases', 'scheduled_conferences'}}),
        'last_synced': now(),
        'is_active': True,
        'call_id': '',  # set below
        'organization_unit': space.organization_unit if space else None,
    }

    cur['web_url'] = api.get_web_url(cospace={**conference, **cur})
    call_id = ''

    local_data = PexipSpace.objects.filter(cluster=api.cluster, external_id=conference_id).first()
    if local_data:
        call_id = local_data.call_id or call_id
        cur['guid'] = local_data.guid
        cur['is_virtual'] = bool(local_data.is_virtual)
    else:
        cur['is_virtual'] = False
        if obj:
            call_id = call_id

    if not call_id or call_id not in [a['alias'] for a in conference['aliases']]:
        try:
            call_id = sorted(
                (a['alias'] for a in conference['aliases'] if a['alias'].isdigit()),
                key=lambda x: len(x),
            )[0]
        except IndexError:
            pass

    cur['call_id'] = call_id

    if obj and batcher:
        batcher.partial_update(obj, cur)
    elif obj:
        partial_update(obj, cur)
    else:
        obj, created = partial_update_or_create(Conference, cid=conference.get('id'), provider=api.cluster, defaults=cur)

    sync_conference_aliases(api, conference.get('id'), obj=obj, data=conference, batcher=batcher)
    sync_conference_auto_participants(api, conference.get('id'), obj=obj, data=conference, batcher=batcher)

    return obj


def _get_auto_participant(api, auto_participant, obj=None, batcher=None):
    p = auto_participant
    data = {
        'alias': p.get('alias'),
        'last_synced': now(),
        'is_active': True,
    }
    if 'remote_display_name' in p:  # full result
        data.update({
            'remote_display_name': p.get('remote_display_name', ''),
            'role': p.get('role', ''),
            "description": p.get('description'),
            "full_data": p,
        })

    if obj:
        if batcher:
            batcher.partial_update(obj, data)
        else:
            partial_update(obj, data)
        created = False
    else:
        obj, created = partial_update_or_create(ConferenceAutoParticipant, provider=api.cluster, pid=p['id'], defaults=data)
    return obj, created


@sync_method
def sync_conference_auto_participants(api, conference_id, obj=None, data=None, batcher=None):

    if not obj:
        obj = _get_conference(conference_id, api.cluster, data)

    if data is not None:
        auto_participants = data.get('automatic_participants') or []
    else:
        auto_participants = api.get_automatic_participants(conference_id)

    local_batcher = batcher or SyncBatcher(time_update_fields=['last_synced'], defaults={'is_active': True})

    valid = set()
    for p in auto_participants:

        cur, created = _get_auto_participant(api, p, batcher=local_batcher)

        if obj:
            obj.automatic_participants.add(cur)

        valid.add(cur.pk)

    if not batcher:
        local_batcher.commit()

    if obj:
        obj.automatic_participants.exclude(pk__in=valid).delete()


@sync_method
def sync_automatic_participants_from_pexip(api: 'PexipAPI', incremental=False):

    filter_kwargs = {}
    if incremental:
        last_sync = ProviderSync.objects.filter(provider=api.cluster).values_list('automatic_participants_last_sync', flat=True).first()
        if not last_sync:
            last_sync = now() - timedelta(hours=DEFAULT_INCREMENTAL)
        filter_kwargs['creation_time__gte'] = last_sync.isoformat()

    start = now()

    batcher = SyncBatcher(time_update_fields=['last_synced'], defaults={'is_active': True})

    valid = set()
    for p, cur in bulk_iter(api.cluster, ConferenceAutoParticipant, 'pid', api.get_automatic_participants(**filter_kwargs), 'id'):

        if not cur:
            cur, created = _get_auto_participant(api, p, obj=cur, batcher=batcher)

        conference_ids = [_extract_id_from_url(c) for c in p.get('conference', [])]
        for conference in Conference.objects.filter(provider=api.cluster, cid__in=conference_ids):
            conference.automatic_participants.add(cur)

        valid.add(cur.pk)

    batcher.commit()

    if not incremental:
        ConferenceAutoParticipant.objects.filter(provider=api.cluster, last_synced__lt=start - timedelta(minutes=5), is_active=True).update(is_active=False)
    ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(automatic_participants_last_sync=now()))


@sync_method
def sync_conference_aliases_from_pexip(api: 'PexipAPI', incremental=False):

    filter_kwargs = {}
    if incremental:
        last_sync = ProviderSync.objects.filter(provider=api.cluster).values_list('aliases_last_sync', flat=True).first()
        if not last_sync:
            last_sync = now() - timedelta(hours=DEFAULT_INCREMENTAL)
        filter_kwargs['creation_time__gte'] = last_sync.isoformat()

    start = now()

    batcher = SyncBatcher()

    for alias, obj in bulk_iter(api.cluster, ConferenceAlias, 'aid', api.get_conference_aliases(**filter_kwargs), 'id'):
        data = {
            'alias': alias.get('alias', '').lower(),
            'description': alias.get('description', ''),
            'conference': _get_conference(alias['conference'], provider=api.cluster),
        }
        if obj:
            batcher.partial_update(obj, data)
        else:
            partial_update_or_create(ConferenceAlias, provider=api.cluster, aid=alias['id'], defaults=data)

    batcher.commit()

    if not incremental:
        ConferenceAutoParticipant.objects.filter(provider=api.cluster, last_synced__lt=start - timedelta(minutes=5), is_active=True).update(is_active=False)
    ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(aliases_last_sync=now()))


@sync_method
def sync_conference_aliases(api, conference_id, obj=None, data=None, batcher=None):

    if conference_id and not obj:
        obj = _get_conference(conference_id, api.cluster, data)
    conference = obj

    if data is not None:
        aliases = data['aliases']
    else:
        aliases = api.get_conference_aliases(conference_id)

    valid = set()
    for alias, cur in bulk_iter(api.cluster, ConferenceAlias, 'aid', aliases, 'id'):
        valid.add(alias['id'])

        data = {
            'alias': alias.get('alias', '').lower(),
            'description': alias.get('description', ''),
            'conference': conference or _get_conference(alias['conference'], provider=api.cluster, data=data),
            'is_active': True,
            'last_synced': now(),
        }
        if cur and batcher:
            batcher.partial_update(cur, data)
        elif cur:
            partial_update(cur, data)
        else:
            partial_update_or_create(ConferenceAlias, provider=api.cluster, aid=alias['id'], defaults=data)

    if conference_id:
        ConferenceAlias.objects.filter(provider=api.cluster, conference=obj).exclude(aid__in=valid).update(is_active=False)

