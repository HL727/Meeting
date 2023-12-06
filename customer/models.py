import re
import uuid
from collections import defaultdict
from random import choice
from time import time
from typing import Union
from urllib.parse import parse_qsl
import typing
from cacheout import fifo_memoize
from django.core.cache import cache
from django.db import models, transaction
from django.db.models.aggregates import Count
from django.http import HttpRequest
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
import reversion
from sentry_sdk import capture_exception

from provider.exceptions import InvalidKey, NotFound
from django.conf import settings
import logging

from provider.models.consts import MCU_CLUSTER_TYPES, CLEARSEA_CLUSTER_TYPES

if typing.TYPE_CHECKING:
    from provider.models.provider import Cluster  # noqa

logger = logging.getLogger(__name__)

ENABLE_CLEARSEA = settings.DEBUG
ENABLE_VIDEOCENTER = settings.DEBUG
ENABLE_CORE = settings.ENABLE_CORE
ENABLE_EPM = settings.ENABLE_EPM

EDITION_CHOICE = bool(ENABLE_CORE and ENABLE_EPM)

SHARED_KEY_LENGTH = 40

Q = models.Q


def new_key(length=10):

    letters = '1234567890qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM'
    return ''.join(choice(letters) for i in list(range(length)))


class CustomerManager(models.Manager):

    def get_active(self, type):
        return self.get_or_create(title='Kund')[0]

    def validate_api_key(self, extended_key: str, ou_key: str) -> 'Customer':
        extended_key = self.check_extended_key(extended_key)
        customer = self.get_by_key(ou_key)

        limit_customer_ids = set(extended_key.limit_customers.values_list('id', flat=True))
        if not limit_customer_ids or customer.pk in limit_customer_ids:
            return customer

        raise InvalidKey()

    def get_by_key(self, key_string: str) -> 'Customer':
        """
        Try all keys one by one, try to use joined key first and later one by one.
        Eg. "key1,key2,key3" checks first all three, than "key1,key2", "key2,key3"
        """

        for key in self.iter_all_keys(key_string):
            try:
                return CustomerKey.objects.filter(active=True, shared_key__iexact=key[:SHARED_KEY_LENGTH]).first().customer
            except AttributeError:
                pass
        raise InvalidKey()

    def filter_by_keys(self, keys: typing.List[str]) -> typing.List['Customer']:
        result = []
        for key in keys:
            try:
                customer = self.get_by_key(key)
                result.append(customer)
            except InvalidKey:
                pass

        return result

    @staticmethod
    def iter_all_keys(key_string: str) -> typing.Iterator[str]:
        keys = key_string.split(',')[-3:]

        for i in range(len(keys) - 1):  # combination
            for j in range(len(keys) - 1, i, -1):
                key = ','.join(keys[i:j + 1])
                yield key

        for key in keys:  # single
            yield key

    def check_extended_key(self, key: str):
        from api_key.models import BookingAPIKey
        try:
            result = BookingAPIKey.objects.filter(key=key, enabled=True)[0]
            result.ts_last_used = now()
            result.save(update_fields=['ts_last_used'])
            return result
        except IndexError:
            if key in settings.EXTENDED_API_KEYS:  # tests
                BookingAPIKey.objects.populate_system_keys()
                return self.check_extended_key(key)
            raise InvalidKey('Extended key not valid')

    def get_extended_key_from_request(self, request: HttpRequest):
        return (
            request.META.get('HTTP_X_MIVIDAS_TOKEN')
            or request.GET.get('extended_key')
            or request.POST.get('extended_key')
            or ''
        )

    def from_request(self, request: HttpRequest, require_extended_key=None) -> 'Customer':
        key = (
            request.META.get('HTTP_X_MIVIDAS_OU')
            or request.GET.get('key')
            or request.POST.get('key')
            or ''
        )
        if require_extended_key or (require_extended_key is None and settings.REQUIRE_EXTENDED_KEY):
            from audit.models import AuditLog

            extended_key = self.get_extended_key_from_request(request)

            try:
                result = self.validate_api_key(extended_key, key)
                AuditLog.objects.store_request(
                    request, 'API key validated for customer {}'.format(result.pk)
                )
                return result
            except InvalidKey:
                AuditLog.objects.store_request(request, 'API key verification failed')
                raise
        return self.get_by_key(key)

    def get_for_user(self, user) -> models.QuerySet:
        if not user.is_authenticated:
            return Customer.objects.none()

        permission_customers = user.customerpermission_set.all().values_list('customer', flat=True)

        if not permission_customers:
            queryset = self.get_queryset().all()
        else:
            queryset = Customer.objects.filter(pk__in=permission_customers)

        return queryset.prefetch_related('lifesize_provider', 'lifesize_provider__cluster', 'lifesize_provider__clustered')

    def has_all_customers(self, user):
        from supporthelpers.models import CustomerPermission
        if CustomerPermission.objects.filter(user=user).exists():
            return False
        return True

    def get_for_request(self, request):
        from .utils import get_customers_from_request
        return get_customers_from_request(request)

    def find_customer(self, acano_tenant_id=None, pexip_tenant_id=None, domain=None, cluster=None):

        assert acano_tenant_id is None or pexip_tenant_id is None

        result = None

        if acano_tenant_id is not None:
            if cluster:
                result = MatchCache.match_cluster_tenant(cluster, acano_tenant_id)
            return result or Customer.objects.filter(acano_tenant_id=acano_tenant_id).first()
        if pexip_tenant_id is not None:
            if cluster:
                result = MatchCache.match_cluster_tenant(cluster, pexip_tenant_id)
            if pexip_tenant_id and not result:
                return Customer.objects.filter(pexip_tenant_id=pexip_tenant_id).first()
            return result or Customer.objects.filter(pexip_default__isnull=False, pexip_tenant_id=pexip_tenant_id).first()

        if '.' in (domain or ''):
            try:
                return self.get_by_key(domain)
            except InvalidKey:
                pass

    def get_usage_counts_cached(self):
        cache_key = 'customer.all_usage'
        cached = cache.get(cache_key)
        if cached:
            return cached
        result = self.get_usage_counts()
        cache.set(cache_key, result, 90)
        return result

    def get_usage_counts(self, customers=None):
        from endpoint.models import Endpoint
        from endpointproxy.models import EndpointProxy
        from meeting.models import Meeting
        from address.models import AddressBook
        from supporthelpers.models import CustomerPermission

        if customers:
            filter_kwarg = {'customer__in': customers}
        else:
            filter_kwarg = {}

        def _filter(model, extra_filter=None):
            qs = model.objects.filter(**filter_kwarg, **(extra_filter or {})).order_by()
            return dict(qs.values_list('customer').annotate(Count('customer')))

        return {
            'endpoints': _filter(Endpoint),
            'endpoint_proxies': _filter(EndpointProxy),
            'meetings': _filter(Meeting, {'is_superseded': False}),
            'address_books': _filter(AddressBook),
            'admin_users': _filter(CustomerPermission),
            'matches': _filter(CustomerMatch),
            **self.get_datastore_usage_counts(customers),
        }

    def get_datastore_usage_counts(self, customers=None):

        from datastore.models.acano import CoSpace
        from datastore.models.pexip import Conference
        from datastore.models.acano import User
        from datastore.models.pexip import EndUser

        all_customers = customers or Customer.objects.all()
        customer_map = {c.pk: c.acano_tenant_id for c in all_customers if c.acano_tenant_id}
        customer_map.update({c.pk: c.pexip_tenant_id for c in all_customers if c.pexip_tenant_id})

        tenant_args = Q()

        if customers:
            # TODO filter provider for default customer (tenant__isnull=True) support
            if customer_map:
                tenant_args &= Q(tenant__tid__in=customer_map)
            else:
                tenant_args &= Q(tenant__isnull=True)

        cospaces = [
            (x[0], x[1], x[2])
            for x in CoSpace.objects.filter(tenant_args, is_active=True)
            .values_list('provider', 'tenant__tid')
            .annotate(count=Count('*'))
        ]
        cospaces2 = [
            (x[0], x[1], x[2])
            for x in Conference.objects.filter(tenant_args, is_active=True)
            .values_list('provider', 'tenant__tid')
            .annotate(count=Count('*'))
        ]

        users = [
            (x[0], x[1], x[2])
            for x in User.objects.filter(tenant_args, is_active=True)
            .values_list('provider', 'tenant__tid')
            .annotate(count=Count('*'))
        ]
        users2 = [
            (x[0], x[1], x[2])
            for x in EndUser.objects.filter(tenant_args, is_active=True)
            .values_list('provider', 'tenant__tid')
            .annotate(count=Count('*'))
        ]

        def separate_by_tenant(*args):
            result = defaultdict(lambda: 0)
            for counts in args:
                for cluster_id, tenant_id, count in counts:
                    customer = MatchCache.match_cluster_tenant(cluster_id, tenant_id or '')
                    if not customer:
                        continue

                    result[customer.pk] += count
            return dict(result)

        return {
            'cospaces': separate_by_tenant(cospaces, cospaces2),
            'users': separate_by_tenant(users, users2),
        }


@reversion.register
class Customer(models.Model):

    title = models.CharField(max_length=255)
    shared_key = models.CharField(max_length=40, default='', blank=True, editable=False)

    lifesize_provider = models.ForeignKey('provider.Cluster', null=True, blank=True,
                                          limit_choices_to={'type__in': MCU_CLUSTER_TYPES},
                                          verbose_name=_('Video-provider'),
                                          on_delete=models.SET_NULL, related_name='customers')
    clearsea_provider = models.ForeignKey('provider.Provider', null=True, blank=True,
                                          on_delete=models.SET_NULL, related_name='+',
                                          limit_choices_to={'type__in': CLEARSEA_CLUSTER_TYPES},
                                          editable=ENABLE_CLEARSEA)

    videocenter_provider = models.ForeignKey('provider.VideoCenterProvider', null=True, blank=True,
                                             verbose_name=_('Inspelning/streaming-provider'),
                                             on_delete=models.SET_NULL, related_name='+')

    streaming_provider = models.ForeignKey('provider.VideoCenterProvider', null=True, blank=True, verbose_name=_('Separat provider enbart för streaming'),
                                          on_delete=models.SET_NULL, related_name='+')

    meeting_add_seconds_before = models.IntegerField(_('Lägg till x sekunder före ett möte'), default=0)
    meeting_add_seconds_after = models.IntegerField(_('Lägg till x sekunder efter ett möte'), default=0)

    always_enable_external = models.BooleanField(_('Registrera alltid clearsea'), default=False, editable=ENABLE_CLEARSEA)

    username_prefix = models.CharField(_('Prefix för användarnamn'), help_text=_('Användarnamnet kommer bli detta, ett understreck, och löpnummer'),
        max_length=100, default='user', editable=ENABLE_CLEARSEA)

    clearsea_group_name = models.CharField(_('Clearsea gruppnamn'), max_length=100, blank=True, help_text=_('Måste finnas i clearsea redan'), editable=ENABLE_CLEARSEA)
    acano_tenant_id = models.CharField(_('Acano tenant-id'), max_length=65, help_text=_('Måste finnas i acano'), blank=True)
    pexip_tenant_id = models.CharField(_('Pexip tenant-id'), max_length=65, blank=True, help_text=_('Genereras automatiskt'))

    recording_user = models.CharField(_('Ev. ägare (user) för inspelningar'), help_text=_('Måste finnas'), max_length=100, blank=True, editable=ENABLE_VIDEOCENTER)
    recording_channel = models.CharField(_('Ev. kanalnamn för inspelning'), help_text=_('Måste finnas'), max_length=100, blank=True, editable=ENABLE_VIDEOCENTER)

    seevia_key = models.CharField(_('Ev. API-nyckel för seevia'), max_length=100, blank=True)

    enable_core = models.BooleanField(
        _('Aktivera åtkomst till Core'),
        default=ENABLE_CORE,
        editable=ENABLE_CORE and EDITION_CHOICE,
    )
    enable_epm = models.BooleanField(
        _('Aktivera åtkomst till Rooms'), default=ENABLE_EPM, editable=ENABLE_EPM and EDITION_CHOICE
    )

    enable_streaming = models.BooleanField(_('Aktivera streaming'), default=True)
    enable_recording = models.BooleanField(_('Aktivera inspelning'), default=True)

    logo_url = models.URLField(null=True, blank=True, help_text=_('För inbjudningsmeddelanden'))

    cospace_prefix = models.CharField(
        _('Förifylld prefix för nya mötesrum'), max_length=50, blank=True, editable=False
    )

    verify_certificate = False

    has_custom_messages = models.BooleanField(default=False, editable=False)

    objects = CustomerManager()

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        shared_key = self.shared_key
        self.shared_key = ''
        super().save(*args, **kwargs)
        if shared_key:
            CustomerKey.objects.get_or_create(shared_key=shared_key, customer=self)

    @property
    def tenant_id(self):
        if self.acano_tenant_id and self.pexip_tenant_id:
            provider = self.get_provider()
            if provider and provider.is_pexip and self.pexip_tenant_id:
                return self.pexip_tenant_id
        return self.acano_tenant_id or self.pexip_tenant_id or ''

    @staticmethod
    @fifo_memoize(100, 10)
    def get_cluster_default_customer(provider_id):
        if not provider_id:
            return None

        from provider.models.pexip import PexipCluster
        cluster = PexipCluster.objects.filter(Q(pk=provider_id) | Q(children=provider_id)).first()
        if cluster and cluster.default_customer_id:
            return cluster.default_customer_id

        return None

    def get_pexip_tenant_id(self):
        if self.pexip_tenant_id:
            return self.pexip_tenant_id

        if settings.ENABLE_DEMO and not self.get_api().provider.is_pexip:
            try:
                raise ValueError('Pexip tenant id requested for non-pexip customer')
            except Exception:
                capture_exception()

        if self.get_cluster_default_customer(self.lifesize_provider_id) == self.pk:
            return ''

        with transaction.atomic():
            refreshed = Customer.objects.select_for_update(of=('self',)).get(pk=self.pk)
            if refreshed.pexip_tenant_id:
                self.pexip_tenant_id = refreshed.pexip_tenant_id
            else:
                refreshed.pexip_tenant_id = str(uuid.uuid4())
                refreshed.save(update_fields=['pexip_tenant_id'])
                self.pexip_tenant_id = refreshed.pexip_tenant_id
        return self.pexip_tenant_id

    def get_api(self, allow_cached_values=False):
        return self.get_mcu_api(allow_cached_values=allow_cached_values)

    def get_mcu_api(self, allow_cached_values=False):
        ":rtype: provider.ext_api.acano.AcanoAPI | provider.ext_api.pexip.PexipAPI"

        provider = self.get_provider()
        if not provider:
            raise NotFound('Customer has no MCU')  # TODO other exceptions for special handling?

        api = provider.get_api(self)
        if allow_cached_values:
            api.allow_cached_values = allow_cached_values

        return api

    def get_recording_api(self):
        return self.get_videocenter_provider().get_api(self)

    def get_streaming_api(self):
        if self.streaming_provider_id:
            return self.streaming_provider.get_api(self)
        return self.get_videocenter_provider().get_api(self)

    def get_vcs_api(self):
        from provider.models.vcs import VCSEProvider
        try:
            return VCSEProvider.objects.filter(customer=self).first().get_api(self)
        except AttributeError:
            try:
                return VCSEProvider.objects.filter(customer__isnull=True).first().get_api(self)
            except AttributeError:
                return None

    def get_provider(self):
        ":rtype: Cluster | None"
        from provider.models.provider import Provider

        if self.lifesize_provider_id:
            return self.lifesize_provider

        return Provider.objects.get_active('mcu')

    def get_videocenter_provider(self):
        from recording.models import VideoCenterProvider

        if self.videocenter_provider_id:
            return self.videocenter_provider
        elif self.streaming_provider_id:
            return self.streaming_provider

        return VideoCenterProvider.objects.get_active()

    class Meta:
        ordering = ('title',)
        verbose_name = _('kund')
        verbose_name_plural = _('kunder')
        app_label = 'provider'  # dont change. will break foreign keys
        db_table = 'customer_customer'

    def get_domain_keys(self):

        keys = list(self.keys.values_list('shared_key', flat=True))
        return [k for k in keys if '.' in keys]

    def get_non_domain_keys(self):

        keys = list(self.keys.values_list('shared_key', flat=True))
        return [k for k in keys if '.' not in keys]


class CustomerKey(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='keys')
    shared_key = models.CharField(max_length=SHARED_KEY_LENGTH)  # TODO increase? right now its capped in key check
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.shared_key

    class Meta:
        app_label = 'provider'  # dont change. will break foreign keys
        db_table = 'customer_customerkey'


def validate_regexp(s):
    from django.core.exceptions import ValidationError
    import re

    if not s:
        return

    try:
        re.compile(s)
    except (re.error, ValueError) as e:
        raise ValidationError(_('Regexp error: {}').format(e))


class CustomerMatchManager(models.Manager):

    def get_pexip_tenant_id(self, obj, cluster, default=''):
        match = self.get_match(obj, cluster=cluster)
        if not match:
            return None
        return match.get_pexip_tenant_id(cluster=cluster, default=default)

    def match(self, obj, cluster):
        result = self.get_match(obj, cluster=cluster)
        return result.customer if result else None

    def get_match(self, obj, cluster) -> Union['CustomerMatch', None]:
        'get match from alias/uri, owner or tag'
        if not obj:
            return None

        from statistics.parser.utils import clean_target

        logger.debug('Start new match for object with type %s', type(obj))

        if isinstance(obj, str):
            return self.get_match_from_text(obj, cluster=cluster)

        if not isinstance(obj, dict):
            raise ValueError('Value must be dict or str')

        for key in ('tag', 'service_tag'):
            if obj.get(key):
                result = self.get_match_from_tag(obj[key], cluster=cluster)
                if result:
                    return result

        match_strs = []
        for alias in sorted(obj.get('aliases') or (), key=lambda x: len(x['alias']), reverse=True):
            match_strs.append(alias['alias'])

        for key in ('local_alias', 'remote_alias', 'destination_alias', 'source_alias'):
            if key in obj:
                match_strs.append(clean_target(obj.get(key)))

        if obj.get('ivr_theme'):
            match_strs.append(obj['ivr_theme']['uuid'])  # TODO make sure cluster is set?

        for key in ('primary_email_address', 'primary_owner_email_address', 'service_tag'):
            match_strs.append(obj.get(key))

        for m in match_strs:
            if not m:
                continue

            result = self.get_match_from_text(m, cluster=cluster)
            if result:
                return result

    def match_text(self, obj, cluster):
        match = self.get_match_from_text(obj, cluster=cluster)
        if match and match.customer_id:
            return match.customer

    def get_match_from_text(self, obj, cluster: Union['Cluster', int]):
        if obj and 't=' in str(obj):
            result = self.get_match_from_tag(obj, cluster=cluster)
            if result:
                return result

        cluster_id = getattr(cluster, 'pk', cluster)
        return CustomerMatchManager._real_match_from_text(str(obj or '').lower(), cluster_id)

    @staticmethod
    @fifo_memoize(128, 10)
    def _real_match_from_text(text, cluster_id):
        for matcher in MatchCache.get().matchers:
            if cluster_id and cluster_id != matcher.cluster_id:
                continue
            if matcher.match(text):
                logger.debug('Matched text %s to match %s', text, matcher.pk)
                return matcher

    def match_customer_from_tag(self, tag, cluster):
        result = self.get_match_from_tag(tag, cluster=cluster)
        if result:
            return result.customer

    def get_match_from_tag(self, tag, cluster):
        if not isinstance(tag, str) or 't=' not in tag:
            return None
        try:
            tenant = dict(parse_qsl(tag)).get('t')
        except ValueError:
            return None

        if not tenant:
            return None

        logger.debug('Matched tag %s to %s', tag, tenant)
        customer = MatchCache.match_cluster_tenant(cluster, tenant)
        return CustomerMatch(cluster=cluster, prefix_match=tenant, customer=customer, tenant_id=tenant)

    def get_customer_for_pexip(self, conference_name=None, obj=None, cluster=None):
        assert cluster
        match = self.get_match_for_pexip(conference_name=conference_name, obj=obj, cluster=cluster)
        if match and match.customer_id:
            return match.customer

    def get_match_for_pexip(self, conference_name=None, obj=None, cluster=None, use_cache=True):
        "match against cached or locally overridden pexip data"
        from statistics.parser.utils import clean_target

        assert cluster

        cur_id = None
        if obj:
            try:
                cur_id = ['{}={}'.format(k, obj[k]) for k in {'id', 'call_uuid', 'conversation_id'} if obj.get(k)][0]
            except IndexError:
                cur_id = None

        logger.debug('Begin pexip match for id %s, conference %s, obj typ %s, cluster %s', cur_id, conference_name, type(obj), cluster)

        if obj and (obj.get('tag') or obj.get('service_tag')):  # TODO keep here?
            match = self.get_match_from_tag(obj.get('tag') or obj.get('service_tag'), cluster=cluster)
            if match:
                return match

        if not conference_name and obj:
            for k in ('conference_name', 'conference'):
                if obj.get(k) and isinstance(obj[k], str) and not obj[k].startswith('/admin/v1/configuration/'):
                    conference_name = obj[k]
                    logger.debug('Update conference name to %s from key %s', conference_name, k)
                    break

        local_alias = None
        if obj and obj.get('local_alias'):
            local_alias = clean_target(obj['local_alias'])

        cluster_id = getattr(cluster, 'pk', cluster) if cluster else None

        result = None
        if conference_name:
            result = self._pexip_get_conference(conference_name, cluster_id)

        if local_alias and not result:
            result = self._pexip_get_local_alias(conference_name, cluster_id)

        return result

    @staticmethod
    @fifo_memoize(maxsize=200, ttl=10)
    def _pexip_get_conference(conference_name, cluster_id):
        "cached getter for normalized parameters."
        # TODO: problem in real life with lru cache and rule changes due to multi process?

        from datastore.models.pexip import Conference

        conference = Conference.objects.match(conference_name, cluster=cluster_id)
        if not conference:
            return

        match = CustomerMatchManager._verify_customer_tenant(conference, cluster_id)
        if match:
            logger.debug('Matched name %s to match %s', conference_name, match.pk)
            return match

    @staticmethod
    @fifo_memoize(maxsize=200, ttl=10)
    def _pexip_get_local_alias(local_alias, cluster_id):
        "cached getter for normalized parameters."
        # TODO: problem in real life with lru cache and rule changes due to multi process?

        from datastore.models.pexip import Conference
        conference = Conference.objects.match({'local_alias': local_alias}, cluster=cluster_id)
        if not conference:
            return

        match = CustomerMatchManager._verify_customer_tenant(conference, cluster_id)
        if match:
            logger.debug('Matched local alias %s to match %s', local_alias, match.pk)
            return match

    @staticmethod
    def _verify_customer_tenant(conference, cluster_id):
        from provider.models.provider import Cluster

        if not conference or not (conference.tenant_id or conference.match_id):
            return None

        if not conference.tenant_id and conference.match_id:
            return conference.match

        tenant_customer = MatchCache.match_cluster_tenant(cluster_id, conference.tenant.tid)
        if conference.match_id and (not tenant_customer or conference.match.customer_id == tenant_customer.pk):
            return conference.match
        return CustomerMatch(cluster=Cluster(pk=cluster_id) if cluster_id else None,
                             customer=tenant_customer,
                             prefix_match=conference.tenant.tid,
                             tenant_id=conference.tenant.tid,
                             )


class MatchCache:
    _cache = None

    def __init__(self, tenant_map, tenant_cluster_map, matchers, expire=None):
        self.tenant_map = tenant_map
        self.tenant_cluster_map = tenant_cluster_map
        self.matchers = matchers
        self.expire = expire or time() + 10

    @classmethod
    def get(cls):
        if not cls._cache or cls._cache.expire < time():
            return cls.update()
        return cls._cache

    @classmethod
    def match_cluster_tenant(cls, cluster, tenant_id):
        if hasattr(cluster, 'cluster_id'):
            cluster_id = cluster.cluster_id or cluster.pk
        else:
            cluster_id = cluster
        cur = (cluster_id, tenant_id)
        return cls.get().tenant_cluster_map.get(cur)

    @classmethod
    def match_tenant(cls, tenant):
        return cls.get().tenant_map.get(tenant)

    @classmethod
    def update(cls):
        customers = {c.pk: c for c in Customer.objects.all()}

        from provider.models.provider import Provider, Cluster
        providers = {provider.pk: provider for provider in Provider.objects.all()}

        tenant_map = {c.pexip_tenant_id: c for c in customers.values() if c.pexip_tenant_id}
        tenant_map.update({c.acano_tenant_id: c for c in customers.values() if c.acano_tenant_id})

        tenant_cluster_map = {}

        for customer in customers.values():
            if customer.lifesize_provider_id not in providers:
                continue

            provider = providers[customer.lifesize_provider_id]

            cluster = Cluster.get_provider_cluster(
                provider.cluster if provider.cluster else provider
            )

            if provider.is_pexip:
                if not customer.pexip_tenant_id and cluster.pexip.default_customer != customer:
                    continue  # Ignore empty tenant id until it is generated
                cur = (cluster.pk, customer.pexip_tenant_id)
            elif provider.is_acano:
                cur = (cluster.pk, customer.acano_tenant_id)
            else:
                continue
            tenant_cluster_map[cur] = customer

        matchers = list(CustomerMatch.objects.order_by('priority', 'id'))

        for m in matchers:
            m.customer = customers.get(m.customer_id)

        cls._cache = MatchCache(tenant_map, tenant_cluster_map, matchers)
        return cls._cache


@reversion.register
class CustomerMatch(models.Model):

    def __init__(self, *args, **kwargs):
        self.tenant_id = kwargs.pop('tenant_id', None)
        super().__init__(*args, **kwargs)

    EITHER = 1

    MODES = (
        (0, _('Både prefix och suffix matchar')),
        (EITHER, _('Antingen prefix eller suffix matchar')),
        (2, _('Använd regexp-fältet')),
    )

    cluster = models.ForeignKey('provider.Cluster', on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    prefix_match = models.CharField(_('SIP-URI/alias börjar med'), max_length=100, blank=True)
    suffix_match = models.CharField(_('SIP-URI/alias slutar med'), max_length=100, blank=True, help_text=_('Adressen innehåller oftast domän (beroende på uppringningssätt)'))
    match_mode = models.SmallIntegerField(_('Typ av matchning'), choices=MODES, default=0, help_text=_('Läge för prefix/suffix-match. Regexp väljs automatiskt'))
    regexp_match = models.CharField(_('Regexp'), max_length=250, blank=True, validators=[validate_regexp],
                                    help_text=_('Används istället för prefix/suffix. Matchar från start (implicit ^)'))

    room_count = models.IntegerField(null=True, editable=False, help_text=_('Antalet cachade rum som matchar'))

    require_authorization = models.BooleanField(_('Kräv extern autentisering före deltagare släpps in'), default=False, help_text=_('Kräver att policy-server och regler för kluster är aktiverade'))

    priority = models.SmallIntegerField(default=10)

    tenant_id = None  # fallback if customer is removed

    objects = CustomerMatchManager()

    def __str__(self):
        return '{} - {} {}'.format(self.customer if self.customer_id else 'None', self.prefix_match or '', self.suffix_match or '')

    def match(self, needle):

        if self.regexp_match:
            if re.match(self.regexp_match, needle, re.IGNORECASE):
                return True
            return False

        matches = []
        if self.prefix_match:
            cur = needle.lower().startswith(self.prefix_match.lower())
            matches.append(cur)

        if self.suffix_match:
            cur = needle.lower().endswith(self.suffix_match.lower())
            matches.append(cur)

        if self.match_mode == self.EITHER and any(matches):
            return True

        return all(matches) if matches else False

    def save(self, *args, **kwargs):
        if self.regexp_match:
            self.match_mode = 3
        elif self.match_mode == 3:
            self.match_mode = 0

        self.prefix_match = (self.prefix_match or '').lower()
        self.suffix_match = (self.suffix_match or '').lower()

        if self.customer_id and self.cluster_id and self.cluster.is_pexip:
            self.customer.get_pexip_tenant_id()

        super().save(*args, **kwargs)

    def get_pexip_tenant_id(self, cluster=None, default=None):
        if self.customer_id:
            return self.customer.get_pexip_tenant_id()
        if self.tenant_id is not None:
            return self.tenant_id
        return default

    class Meta:
        verbose_name = _('nummermatchningsregel')
        verbose_name_plural = _('nummermatchningsregler')


def clear_cache(sender, **kwargs):

    MatchCache._cache = None
    CustomerMatchManager._pexip_get_conference.cache.clear()
    CustomerMatchManager._pexip_get_local_alias.cache.clear()
    CustomerMatchManager._real_match_from_text.cache.clear()


models.signals.post_save.connect(clear_cache, sender=Customer)
models.signals.post_save.connect(clear_cache, sender=CustomerMatch)
models.signals.post_delete.connect(clear_cache, sender=CustomerMatch)

