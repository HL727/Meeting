import logging
from collections import Counter
from datetime import timedelta
from time import sleep
from typing import Iterator, Any, Tuple, Union, Sequence, Optional
from urllib.parse import parse_qs

from cacheout import fifo_memoize
from django.conf import settings
from django.db.models import Q, F
from django.utils.timezone import now

from customer.models import Customer
from datastore.models.acano import User, CoSpace, CoSpaceAccessMethod, CoSpaceMember
from provider.ext_api.acano import AcanoAPI, AcanoDistributedRunner, AcanoDistributedGet
from . import bulk_iter, sync_method
from ..models.base import ProviderSync
from shared.utils import partial_update_or_create, partial_update, SyncBatcher
from ..models.customer import Tenant
from .ldap import update_ldap_user
from provider.exceptions import MultipleResponseError, NotFound, ResponseError, ResponseConnectionError

logger = logging.getLogger(__name__)

ENABLE_CREATOR_SYNC = False


@fifo_memoize(500, 10)
def _get_tenant(id: str, provider_id: int):

    if not id:
        return None

    try:
        return Tenant.objects.get(tid=id, provider=provider_id)
    except Tenant.DoesNotExist:
        return None


@fifo_memoize(500, 10)
def _get_customer(tenant_id: str, provider_id: int) -> Optional[Customer]:

    try:
        return Customer.objects \
            .filter(lifesize_provider=provider_id, acano_tenant_id=tenant_id or '').order_by('id')[0]
    except IndexError:
        return None


def _get_user(id_or_jid, api):

    if not id_or_jid:
        return None
    try:
        if '@' in id_or_jid:
            return User.objects.filter(username=id_or_jid, provider=api.cluster).order_by('-last_synced')[0]
        return User.objects.filter(uid=id_or_jid, provider=api.cluster).order_by('-last_synced')[0]
    except IndexError:
        try:
            if '@' in id_or_jid:
                data = api.find_user(id_or_jid)
            else:
                data = None
            return sync_acano_user(api, id_or_jid, data=data)
        except ResponseError:
            pass


def sync_all_acano(provider, customer=None, incremental=False):
    return list(sync_all_acano_iter(provider, customer=customer, incremental=incremental))


def sync_all_acano_iter(provider, customer=None, incremental=False) -> Iterator[Tuple[str, Any]]:

    if not provider.is_acano:
        return

    if not customer:
        customer = Customer.objects.all()[0]

    api = provider.get_api(customer)
    api.is_syncing = True

    cluster = api.cluster

    partial_update_or_create(ProviderSync, provider=cluster, defaults={
        ('last_incremental_sync' if incremental else 'last_full_sync'): now(),
    })

    all_start = now()

    def _log_and_run(step, fn):
        start = now()
        result = fn(api)
        logger.info('Full sync of {} for cluster %s in %s secs'.format(step), cluster, (now() - start).total_seconds())
        return step, result

    if not incremental:
        yield _log_and_run('tenants', sync_tenants_from_acano)
        # activate and remove from sync_tenants if other info than id/name is used regularly:
        # yield _log_and_run('tenants_extended', sync_tenants_from_acano_extended)
        yield _log_and_run('users', sync_users_from_acano_active_tenants)
        yield _log_and_run('cospaces', sync_cospaces_from_acano_active_tenants)
        ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(cospaces_last_sync=now()))

        yield _log_and_run('users_full', sync_users_extended_from_acano_active_tenants)
        ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(users_last_sync=now()))

        yield _log_and_run('cospaces_full', sync_cospaces_extended_from_acano_active_tenants)
        yield _log_and_run('users_ldap', sync_users_ldap_from_acano)
    else:
        yield _log_and_run('tenant_counts', sync_tenants_count_from_acano_incremental)
        yield _log_and_run('users_incremental', sync_users_from_acano_active_tenants)
        yield _log_and_run('cospaces_incremental', sync_cospaces_from_acano_active_tenants)

        yield _log_and_run('users_incremental', sync_users_extended_from_acano_incremental)
        yield _log_and_run('cospaces_incremental', sync_cospaces_extended_from_acano_incremental)

    api.is_syncing = False

    if incremental:
        logger.info('Incremental sync of cluster %s in %s secs', cluster,
                    (now() - all_start).total_seconds())
    else:
        logger.info('Full sync of cluster %s in %s secs', cluster,
                    (now() - all_start).total_seconds())


def get_active_tenants(api: AcanoAPI) -> Sequence[Union[None, Tenant]]:
    """
    Get all tenants with newly changed data. Service providers often have old tenants which a lot
    of users/rooms which takes a lot of time to sync, unnecessarily.

    CMS lacks the support to only filter on the default tenant id. So if it is changed, all
    data must be iterated
    """
    tenants = Tenant.objects.filter(provider=api.cluster, is_active=True)
    if tenants.count() > 2:
        result = list(tenants.filter(last_count_change__gt=now() - timedelta(days=30)))
        if all(r.tid for r in result):  # Check if only non-default tenant is updated
            logger.info('Only syncing %s recently changed tenants', len(result))
            return result
    return [None]


@sync_method
def sync_users_from_acano_active_tenants(api: AcanoAPI):
    for tenant in get_active_tenants(api):
        logger.info('Syncing user list for tenant %s in cluster %s',
                    tenant.tid if tenant else 'default', api.cluster.pk)
        sync_users_from_acano(api, tenant=tenant)


@sync_method
def sync_users_from_acano(api: AcanoAPI, tenant: Tenant = None):

    i = 0

    tenant_query = '?tenantFilter={}'.format(tenant.tid) if tenant else ''

    batcher = SyncBatcher(time_update_fields=['last_synced'], defaults={'is_active': True})

    tenant_count = Counter()

    start = now()
    for u, obj in bulk_iter(api.cluster, User, 'uid', api.iter_nodes_list('users' + tenant_query), 'id'):
        i += 1
        if i % 50 == 0:
            print(i)

        sync_single_user_list(api, u, obj, batcher)
        tenant_count[u.get('tenant') or ''] += 1

    batcher.commit()

    if tenant_count.get('', 0) > 0:  # default tenant
        default_tenant = Tenant.objects.get_or_create(provider=api.cluster, tid='')[0]
        if default_tenant.user_count != tenant_count['']:
            partial_update(default_tenant, {'user_count': tenant_count[''], 'last_count_change': now()})

    tenant_kwargs = {'tenant': tenant} if tenant else {}

    User.objects.filter(provider=api.cluster, last_synced__lt=start - timedelta(hours=2),
                        is_active=True, **tenant_kwargs).update(is_active=False)

    if not tenant:
        ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(users_last_sync=now()))


def sync_single_user_list(
    api: AcanoAPI, data: dict, obj: User = None, batcher: SyncBatcher = None
) -> User:

    cur = {
        'username': data.get('userJid', ''),
        'tenant': _get_tenant(data.get('tenant'), api.cluster.pk),
        'customer': _get_customer(data.get('tenant'), api.cluster.pk),
        'is_active': True,
        'last_synced': now(),
    }

    if obj:
        if batcher:
            batcher.partial_update(obj, cur)
        else:
            partial_update(obj, cur)
    else:
        obj, created = partial_update_or_create(
            User, uid=data.get('id'), provider=api.cluster, defaults=cur
        )

        if created and cur['tenant']:
            cur['tenant'].set_updated()

    return obj


@sync_method
def sync_users_extended_from_acano_incremental(api: AcanoAPI, start=None):
    return sync_users_extended_from_acano_active_tenants(api, start=start, only_new=True)


@sync_method
def sync_users_extended_from_acano_active_tenants(api: AcanoAPI, start=None, only_new=False):
    for tenant in get_active_tenants(api):
        logger.info('Syncing extended user info for tenant %s in cluster %s',
                    tenant.tid if tenant else 'default', api.cluster.pk)
        sync_users_extended_from_acano(api, start=start, only_new=only_new, tenant=tenant)


@sync_method
def sync_users_extended_from_acano(api: AcanoAPI, start=None, only_new=False, tenant: Tenant = None):

    errors = 0
    start = start or now() - timedelta(minutes=60)

    last_synced_cond = Q(last_synced_data__isnull=True)
    if not only_new:
        last_synced_cond |= Q(last_synced_data__lt=start)

    tenant_kwargs = {'tenant': tenant} if tenant else {}

    users = User.objects.filter(provider=api.cluster, is_active=True, **tenant_kwargs)\
                        .filter(last_synced_cond) \
                        .order_by(F('last_synced_data').asc(nulls_last=False))

    batcher = SyncBatcher(time_update_fields=['last_synced', 'last_synced_data', 'last_synced_cospaces'],
                          defaults={'is_active': True})

    def _sync_user(api, obj):
        nonlocal errors

        try:
            if obj.should_update_data:
                return sync_acano_user(api, obj.uid, obj=obj, sync_cospaces=True, batcher=batcher)
        except ResponseConnectionError:
            errors += 1
            if errors > 5:
                raise
            if not settings.TEST_MODE:
                sleep(.1)
        except NotFound:
            pass

    for _result in AcanoDistributedRunner(api, _sync_user, users):
        pass

    batcher.commit()


@sync_method
def sync_users_ldap_from_acano(api: AcanoAPI, start=None):

    start = start or now() - timedelta(minutes=60)

    users = User.objects.filter(provider=api.cluster, is_active=True)\
                        .filter(Q(last_synced_ldap__isnull=True) | Q(last_synced_ldap__lt=start)) \
                        .order_by(F('last_synced_ldap').asc(nulls_last=False))

    ldapconn = None

    for obj in users:
        if obj.should_update_ldap:
            u, ldapconn = update_ldap_user(obj, ldapconn=ldapconn)


@sync_method
def sync_acano_user(api, uid, obj=None, data=None, update_ldap=False, sync_cospaces=None, batcher=None) -> User:

    user = data or api.get_user(uid)

    tenant = _get_tenant(user.get('tenant'), api.cluster.pk)
    customer = _get_customer(user.get('tenant'), api.cluster.pk)

    from organization.models import UserUnitRelation
    organization_unit_rel = UserUnitRelation.objects.filter(user_jid=user['jid']).only('unit__id').first()

    result = {
        'username': user['jid'],
        'tenant': tenant,
        'customer': customer,
        'name': user['name'],
        'email': user['email'],
        'cdr_tag': user.get('cdr_tag') or '',
        'is_active': True,
        'last_synced': now(),
        'last_synced_data': now(),
        'organization_unit': organization_unit_rel.unit if organization_unit_rel else None,
    }
    for keep_old_value in ('name', 'email'):
        if not result.get(keep_old_value):
            result.pop(keep_old_value)

    created = False
    if obj and batcher:
        batcher.partial_update(obj, result)
    elif obj:
        partial_update(obj, result)
    else:
        obj, created = partial_update_or_create(User, uid=user['id'], provider=api.cluster, defaults=result)
        if created and tenant:
            tenant.set_updated()

    if sync_cospaces or (sync_cospaces is None and created):
        try:
            sync_user_cospaces(api, user['id'], obj=obj, batcher=batcher)
            result['last_synced_cospaces'] = now()
        except Exception:
            pass

    if update_ldap:
        update_ldap_user(obj)

    return obj


@sync_method
def sync_user_cospaces(api, user_id, obj=None, data=None, batcher=None):

    if not obj:
        obj, created = User.objects.get_or_create(uid=user_id, provider=api.cluster)
    else:
        pass

    existing = set(CoSpaceMember.objects
                   .filter(cospace__provider=api.cluster, user=obj)
                   .values_list('cospace__cid', flat=True))

    if data is None:
        data = api.get_user_cospaces(user_id)

    valid = set()

    for cospace in data:

        valid.add(cospace['id'])

        if cospace['id'] in existing:
            continue

        cospace = CoSpace.objects.filter(provider=api.cluster, cid=cospace['id']).first()
        if cospace:  # TODO sync now?
            CoSpaceMember.objects.get_or_create(cospace=cospace, user=obj)

    if not batcher:  # Make sure to update timestamp in upper function
        batcher.partial_update(obj, {'last_synced_cospaces': now()})

    if existing - valid:
        CoSpaceMember.objects.filter(user=obj).exclude(cospace__cid__in=valid).delete()


@sync_method
def sync_tenants_from_acano(api: AcanoAPI, force_full_sync=False):

    start = now()

    any_created = False

    for t, obj in bulk_iter(api.cluster, Tenant, 'tid', api.iter_nodes_list('tenants')):
        data = {
            'name': t['name'] or '',
            'last_synced': now(),
        }
        if obj:
            partial_update(obj, data)
        else:
            obj, created = Tenant.objects.update_or_create(tid=t['id'], provider=api.cluster, defaults=data)
            if created:
                partial_update(
                    obj, {'last_count_change': now() - timedelta(days=25)}
                )  # force resync for new tenants
                any_created = True

    default_tenant, default_created = Tenant.objects.update_or_create(
        provider=api.cluster,
        tid='',
        defaults={
            'last_synced': now(),
        },
    )
    if default_created:
        partial_update(default_tenant, {'last_count_change': now() - timedelta(days=25)})

    ProviderSync.objects.update_or_create(provider=api.cluster, defaults=dict(tenants_last_sync=now()))
    removed = Tenant.objects.filter(provider=api.cluster, last_synced__lt=start).update(is_active=False)

    sync_tenants_count_from_acano(api)

    if any_created or removed or force_full_sync:
        sync_tenants_from_acano_extended(api)


@sync_method
def sync_tenants_count_from_acano(api: AcanoAPI, only_active=False):

    tenants = Tenant.objects.filter(provider=api.cluster, is_active=True)
    if only_active:
        tenants = tenants.filter(
            Q(last_count_change__isnull=True) | Q(last_count_change__gt=now() - timedelta(days=30))
        )

    def _update_count(api, tenant):
        if not tenant.tid:
            return

        cospace_count = api.find_cospaces('', tenant=tenant.tid, limit=1)[1]
        user_count = api.find_users('', tenant=tenant.tid, limit=1)[1]

        if tenant.cospace_count != cospace_count or tenant.user_count != user_count:
            tenant_had_values = tenant.cospace_count or tenant.user_count
            partial_update(tenant, {
                'cospace_count': cospace_count,
                'user_count': user_count,
                **({'last_count_change': now()} if tenant_had_values else {}),
            })

    for _result in AcanoDistributedRunner(api, _update_count, tenants):
        pass


@sync_method
def sync_tenants_count_from_acano_incremental(api: AcanoAPI):
    return sync_tenants_count_from_acano(api, only_active=True)


@sync_method
def sync_tenants_from_acano_extended(api: AcanoAPI, tenants_data=None):

    if tenants_data is None:
        pks = Tenant.objects.filter(provider=api.cluster, is_active=True).values_list('tid', flat=True)
        urls = ['tenants/{}'.format(tid) for tid in pks]

        tenants_data = AcanoDistributedGet(api, urls).iter_dicts(convert_case=True, convert_bool=True)

    for attributes, obj in bulk_iter(api.cluster, Tenant, 'tid', tenants_data):

        attributes.pop('id', None)
        name = attributes.pop('name', None) or ''

        if obj:
            partial_update(obj, {'name': name, 'attributes': attributes})


@sync_method
def sync_cospaces_from_acano_active_tenants(api: AcanoAPI):
    for tenant in get_active_tenants(api):
        logger.info('Syncing cospace list for tenant %s in cluster %s',
                    tenant.tid if tenant else 'default', api.cluster.pk)
        sync_cospaces_from_acano(api, tenant=tenant)


@sync_method
def sync_cospaces_from_acano(api: AcanoAPI, tenant: Tenant = None):

    i = 0

    start = now()
    batcher = SyncBatcher(time_update_fields=['last_synced'], defaults={'is_active': True})

    tenant_query = '?tenantFilter={}'.format(tenant.tid) if tenant else ''
    tenant_count = Counter()

    for c, obj in bulk_iter(
        api.cluster, CoSpace, 'cid', api.iter_nodes_list('coSpaces' + tenant_query)
    ):
        i += 1
        if i % 50 == 0:
            print(i)

        sync_single_cospace_list(api, c, obj, batcher)
        tenant_count[c.get('tenant') or ''] += 1

    batcher.commit()

    if tenant_count.get('', 0) > 0:  # default tenant
        default_tenant = Tenant.objects.get_or_create(provider=api.cluster, tid='')[0]
        if default_tenant.cospace_count != tenant_count['']:
            partial_update(
                default_tenant, {'cospace_count': tenant_count[''], 'last_count_change': now()}
            )

    tenant_kwargs = {'tenant': tenant} if tenant else {}

    CoSpace.objects.filter(
        provider=api.cluster,
        last_synced__lt=start - timedelta(hours=2),
        is_active=True,
        **tenant_kwargs
    ).update(is_active=False)

    if not tenant:
        ProviderSync.objects.update_or_create(
            provider=api.cluster, defaults=dict(cospaces_last_sync=now())
        )


def sync_single_cospace_list(
    api: AcanoAPI,
    data: dict,
    obj: CoSpace = None,
    batcher: SyncBatcher = None,
) -> CoSpace:
    'list call: name, tenant, uri, callId'
    tenant = _get_tenant(data.get('tenant', ''), api.cluster.pk)
    customer = _get_customer(data.get('tenant', ''), api.cluster.pk)

    cur = {
        'uri': data.get('uri', ''),
        'secondary_uri': data.get('secondaryUri', ''),
        'name': data.get('name') or '',
        'call_id': data.get('callId', ''),
        'is_auto': data.get('autoGenerated', '') == 'true',
        'is_active': True,
        'last_synced': now(),
        'tenant': tenant,
        'customer': customer,
    }

    if obj:
        if obj.num_access_methods and not (cur['uri'] or cur['secondary_uri'] or cur['call_id']):
            for k in ('uri', 'secondary_uri', 'call_id', 'secret'):
                cur.pop(k, None)  # use info from access method instead during extended sync

        if batcher:
            batcher.partial_update(obj, cur)
        else:
            partial_update(obj, cur)
    else:
        obj, created = partial_update_or_create(
            CoSpace, cid=data.get('id'), provider=api.cluster, defaults=cur
        )

        if created and tenant:
            tenant.set_updated()

    return obj


@sync_method
def sync_cospaces_extended_from_acano_incremental(api: AcanoAPI, start=None):
    return sync_cospaces_extended_from_acano_active_tenants(api, start=start, only_new=True)


@sync_method
def sync_cospaces_extended_from_acano_active_tenants(api: AcanoAPI, start=None, only_new=False):
    for tenant in get_active_tenants(api):
        logger.info(
            'Syncing extended cospace info for tenant %s in cluster %s',
            tenant.tid if tenant else 'default',
            api.cluster.pk,
        )
        return sync_cospaces_extended_from_acano(api, start=start, only_new=only_new, tenant=tenant)


def set_scheduled_meeting_cospaces(api: AcanoAPI):

    from meeting.models import Meeting

    scheduled_ids = (
        Meeting.objects.filter(
            provider=api.cluster, ts_stop__gt=now() - timedelta(days=7), existing_ref=False
        )
        .exclude(provider_ref='')
        .values_list('provider_ref2', flat=True)
    )
    CoSpace.objects.filter(
        is_active=True,
        cluster=api.cluster,
        is_scheduled=False,
        cid__in=scheduled_ids,
        sync_tag='',
        scheduled_id=None,
    ).update(is_scheduled=True)


@sync_method
def sync_cospaces_extended_from_acano(api: AcanoAPI, start=None, only_new=False, tenant: Tenant = None):

    errors = 0
    start = start or now() - timedelta(minutes=60)

    last_synced_cond = Q(last_synced_data__isnull=True)
    if not only_new:
        last_synced_cond |= Q(last_synced_data__lt=start)

    tenant_kwargs = {'tenant': tenant} if tenant else {}

    cospaces = CoSpace.objects.filter(provider=api.cluster, is_active=True) \
                              .filter(last_synced_cond, **tenant_kwargs) \
                              .order_by(F('last_synced_data').asc(nulls_last=False))

    batcher = SyncBatcher(time_update_fields=['last_synced', 'last_synced_data'], defaults={'is_active': True})

    def _sync_cospace(api, obj):
        nonlocal errors

        try:
            if obj.should_update_data:
                return sync_single_cospace_full(api,
                                                obj.cid,
                                                obj=obj,
                                                update_members=obj.last_synced_data is None,
                                                batcher=batcher)
        except ResponseConnectionError:
            errors += 1
            if errors > 5:
                raise
            if not settings.TEST_MODE:
                sleep(.1)
        except NotFound:
            pass

    for _result in AcanoDistributedRunner(api, _sync_cospace, cospaces):
        pass

    batcher.commit()


@sync_method
def sync_single_cospace_full(api, cospace_id, data=None, obj=None, update_members=True, batcher=None):

    provider = api.cluster

    try:
        cospace = data or api.get_cospace(cospace_id)
    except NotFound:
        return

    owner = _get_user(cospace.get('ownerId'), api)
    creator = None

    if cospace.get('cdrTag') and ENABLE_CREATOR_SYNC:
        creator = parse_qs(cospace.get('cdrTag')).get('creator')
        if creator:
            creator = _get_user(creator[0], api)

    from organization.models import CoSpaceUnitRelation
    organization_unit_rel = CoSpaceUnitRelation.objects.filter(provider_ref=cospace_id).only('unit__id').first()

    cur = {
        'uri': cospace.get('uri') or '',  # may be overridden by sync_cospace_access_methods if empty
        'secondary_uri': cospace.get('secondaryUri') or '',
        'name': cospace.get('name') or '',
        'call_id': cospace.get('callId') or '',
        'is_auto': cospace.get('autoGenerated', '') == 'true',
        'passcode': cospace.get('passcode') or '',
        'secret': cospace.get('secret') or '',
        'stream_url': cospace.get('stream_url') or '',
        'cdr_tag': cospace.get('cdrTag') or '',
        'num_access_methods': int(cospace.get('numAccessMethods') or 0),
        'owner': owner,
        'creator': creator or owner,
        'tenant': _get_tenant(cospace.get('tenant'), api.cluster.pk),
        'customer': _get_customer(cospace.get('tenant'), api.cluster.pk),
        'last_synced': now(),
        'last_synced_data': now(),
        'organization_unit': organization_unit_rel.unit if organization_unit_rel else None,
    }

    force_rewrite_dial_info = False
    if cospace.get('numAccessMethods', '') and not (cur['uri'] or cur['secondary_uri'] or cur['call_id']):
        force_rewrite_dial_info = True
        for k in ('uri', 'secondary_uri', 'call_id', 'secret'):
            cur.pop(k, None)  # use info from access method later instead

    had_access_methods = obj and obj.num_access_methods

    if obj:
        if batcher:
            batcher.partial_update(obj, cur)
        else:
            partial_update(obj, cur)
    else:
        obj, created = partial_update_or_create(CoSpace, cid=cospace_id, provider=api.cluster, defaults=cur)
        if created and cur['tenant']:
            cur['tenant'].set_updated()

    if cospace.get('numAccessMethods', ''):
        sync_cospace_access_methods(api, cospace_id, obj=obj, force_rewrite_dial_info=force_rewrite_dial_info)
    elif had_access_methods:
        CoSpaceAccessMethod.objects.filter(provider=provider, cospace=obj).delete()

    if update_members and obj.should_update_members:
        sync_cospace_members(api, cospace_id, obj=obj)

    return obj


@sync_method
def sync_cospace_members(api, cospace_id, obj=None, data=None):

    if not obj:
        obj, created = CoSpace.objects.get_or_create(cid=cospace_id, provider=api.cluster)
    else:
        pass

    existing = set(CoSpaceMember.objects
                   .filter(cospace__provider=api.cluster, cospace=obj)
                   .values_list('user__username', flat=True))

    members = set()

    if data is None:
        data = api.get_members(cospace_id, include_permissions=False)

    for member in data:

        if member['user_jid'] in existing:
            members.add(member['user_jid'])
            continue

        cur = _get_user(member['user_jid'], api)
        if not cur:
            continue  # TODO update

        CoSpaceMember.objects.get_or_create(cospace=obj, user=cur)
        members.add(member['user_jid'])

    obj.last_synced_members = now()
    obj.save()

    if existing - members:
        CoSpaceMember.objects.filter(cospace=obj).exclude(user__username__in=members).delete()


@sync_method
def sync_cospace_access_methods(
    api,
    cospace_id: str,
    obj: CoSpace = None,
    force_rewrite_dial_info=False,
) -> Sequence[CoSpaceAccessMethod]:

    if not obj:
        obj, created = CoSpace.objects.get_or_create(cid=cospace_id, provider=api.cluster)

    existing_map = {ca.aid: ca for ca in CoSpaceAccessMethod.objects.filter(provider=api.cluster, cospace=obj)}
    result = []

    valid = set()
    for method in api.get_cospace_accessmethods(cospace_id, include_data=True):

        existing = existing_map.get(method['id'])
        valid.add(method['id'])

        data = {
            'uri': method.get('uri') or '',
            'name': method.get('name') or '',
            'call_id': method.get('callId') or '',
            'passcode': method.get('passcode') or '',
            'cospace': obj,
            'scope': method.get('scope'),
            'secret': method.get('secret'),
        }
        if existing:
            partial_update(existing, data)
        else:
            existing, _created = partial_update_or_create(CoSpaceAccessMethod, provider=api.cluster, aid=method['id'], defaults=data)

        result.append(existing)

    if set(existing_map) - valid:
        CoSpaceAccessMethod.objects.filter(provider=api.cluster, cospace=obj).exclude(aid__in=valid).delete()

    # synergy sometimes (always?) creates access method for dial info only. rewrite cospace with that
    if (force_rewrite_dial_info or not (obj.uri or obj.secondary_uri or obj.call_id)) and result:
        method_with_most_values = sorted(
            result,
            key=lambda am: sum(1 for val in (am.scope == 'public', am.uri, am.call_id) if val),
        )[-1]
        partial_update(
            obj,
            {
                'uri': method_with_most_values.uri,
                'call_id': method_with_most_values.call_id,
                'passcode': method_with_most_values.passcode,
            },
        )

    return result


def update_extra_cospace_uris(provider):

    result = {}

    api = provider.get_api(Customer.objects.first())
    errors = []

    for cospace in CoSpace.objects.filter(provider=provider, is_active=True).filter(Q(uri='') | Q(secondary_uri='')):
        update = {}
        if not cospace.uri:
            update['uri'] = cospace.call_id
            cospace.uri = cospace.call_id
        elif not cospace.secondary_uri and cospace.uri != cospace.call_id:
            update['secondaryUri'] = cospace.call_id
            cospace.secondary_uri = cospace.call_id

        try:
            api.update_cospace(cospace.cid, update)
            cospace.save()
        except NotFound:
            cospace.is_active = False
            cospace.save()
        except ResponseError as e:
            errors.append((cospace.id, e))
        result[cospace.call_id] = ([update.get('uri', cospace.uri), update.get('secondary_uri', cospace.secondary_uri)])

    if errors:
        raise MultipleResponseError(errors)
    return result
