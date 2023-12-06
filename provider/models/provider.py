import json
from datetime import timedelta
from urllib.parse import urlparse

import reversion
import typing

from cacheout import fifo_memoize
from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from descriptive_choices import DescriptiveChoices
from numberseries.models import NumberRangeDummy
from .customer import Customer
from ..types import ProviderAPICompatible

Q = models.Q
TASK_DELAY = 5  # seconds before set time that tasks should be scheduled for dialout


ENABLE_CLEARSEA = settings.DEBUG


class ProviderManager(models.Manager):

    def get_active(self, type):
        def _get(type_id, **kwargs) -> typing.Union[Provider, None]:
            return self.filter(type=type_id, is_standard=True, **kwargs).first()

        if type in ('acano',):
            return _get(0, subtype=1)
        elif type in ('pexip',):
            return _get(0, subtype=2)
        elif type in ('lifesize', 0):
            return _get(0)
        elif type in ('clearsea', 1):
            return _get(1)
        elif type in ('internal', 2):
            return _get(2)
        elif type in ('external',):
            return Provider.objects.get_or_create(type=3, defaults=dict(ip='127.0.0.1', hostname='external'))[0]
        elif type in ('offline',):
            return Provider.objects.get_or_create(type=7, defaults=dict(ip='127.0.0.1', hostname='offline'))[0]

        # mcu, default:
        return _get(0, subtype=1) or _get(0, subtype=2) or _get(0)


@reversion.register
class Provider(ProviderAPICompatible, models.Model):

    TYPES = DescriptiveChoices([
        (0, 'lifesize', _('MCU')),
        (1, 'clearsea', _('ClearSea')),
        (2, 'internal', _('Internal')),
        (3, 'external', _('Externa bokningar')),
        (7, 'offline', _('Offline-möte')),

        (4, 'acano_cluster', _('CMS Cluster')),
        (5, 'vcs_cluster', _('VCS Cluster')),
        (6, 'pexip_cluster', _('Pexip Cluster')),
    ])

    CLUSTERED_TYPES = (TYPES.acano_cluster, TYPES.vcs_cluster, TYPES.pexip_cluster)
    MCU_TYPES = (TYPES.acano_cluster, TYPES.pexip_cluster)
    CALL_CONTROL_TYPES = (TYPES.vcs_cluster,)

    SUBTYPES = DescriptiveChoices([
        (1, 'acano', _('CMS Call bridge')),
        (4, 'acano_node', _('CMS Service node')),

        (2, 'pexip', _('Pexip Management node')),
        #(3, 'pexip_node', 'Pexip Node'),
        *([(0, 'lifesize', 'LifeSize')] if ENABLE_CLEARSEA else ()),
    ])

    VIRTUAL_TYPES = (
        TYPES.internal,
        TYPES.external,
        TYPES.offline,
    )

    enabled = models.BooleanField(_('Aktiverad'), null=True, default=True, blank=True)
    is_online = models.BooleanField(_('Är online'), null=True, default=True, editable=False, blank=True)

    title = models.CharField(_('Beskrivning'), max_length=50)
    ip = models.GenericIPAddressField(_('IP-nummer'), blank=True, null=True)
    api_host = models.CharField(_('Ev. separat ip/host för API-anrop'), max_length=100, blank=True, help_text=_('Ex. 192.168.1.1:444'))

    verify_certificate = models.BooleanField(
        _('Verifiera SSL-certifikat'),
        blank=True,
        default=False,
        help_text=_('Använd fullständigt domännamn som matchar serverns certifikat'),
    )

    username = models.CharField(_('Användarnamn'), max_length=50, blank=True)
    password = models.CharField(_('Lösenord'), max_length=50, blank=True)

    hostname = models.CharField(_('DNS-namn'), max_length=100, blank=True)

    web_host = models.CharField(_('Hostname för WebRTC/Web access'), max_length=100, blank=True)

    is_standard = models.BooleanField(_('Är fallback'), help_text=_('Används som standard för kunder som inte har en specifik provider angedd'),
                                      default=False, editable=False)

    phone_ivr = models.CharField(_('Telefonnummer för uppringning'), max_length=25, blank=True)

    type = models.IntegerField(choices=TYPES, default=0)
    subtype = models.IntegerField(choices=SUBTYPES, null=True, blank=True)

    internal_domains = models.TextField(_('Kopplade domäner'), blank=True, help_text=_('Kommaseparerade'))

    cluster = models.ForeignKey('Cluster', blank=True, null=True, limit_choices_to={
        'type__in': CLUSTERED_TYPES,
    }, on_delete=models.SET_NULL, related_name='children')

    clustered = models.ManyToManyField('self', blank=True, editable=False)

    max_load = models.PositiveIntegerField(_('Max load'), null=True, blank=True, help_text='125 000 för X2, 250 000 för X3')

    groupname = models.CharField(_('Gruppnamn'), help_text=_('Används för clearsea'), max_length=50,
                                 blank=True, editable=ENABLE_CLEARSEA)

    session_id = models.TextField(blank=True, editable=False)
    session_expires = models.DateTimeField(blank=True, null=True, editable=False)

    software_version = models.CharField(max_length=100, editable=False, default='')

    options = models.TextField(blank=True, editable=False)

    auto_update_statistics = models.BooleanField(_('Uppdatera statistik automatiskt'), null=True, default=True, help_text=_('Gäller VCS och Pexip'), blank=True)

    use_local_database = models.BooleanField(_('Använd lokal databas för sökningar'), null=True, default=True, blank=True,
                                             help_text=_(
                                                 'Använd lokal databas om möjligt för att bläddra bland bl.a. mötesrum och användare '
                                                 'för bättre prestanda och minskade API-anrop. Synkronisering sker löpande men om många '
                                                 'ändringar sker direkt i bryggan kan det bli fördröjning innan de visas. '
                                                 'Bör alltid användas i Pexip multitenant-miljöer'
                                             ))
    use_local_call_state = models.BooleanField(_('Använd CDR/Eventsink-data för aktiva samtal'), null=True, default=True, blank=True,
                                             help_text=_(
                                                 'Använd lokal samtalsdata för att visa aktiva samtal för bättre prestanda. '
                                                 'Kräver att CDR/Eventsink är kopplad mot Core. '
                                                 'Bör alltid användas i Pexip multitenant-miljöer'
                                             ))


    objects: ProviderManager['Provider'] = ProviderManager()

    def __str__(self):
        return self.title

    @property
    def api(self):
        return self.get_api(None)

    def get_api(self, customer: Customer, allow_cached_values=False):

        from ..ext_api.base import ProviderAPI
        def _allow_cached(api) -> ProviderAPI:
            if api:
                api.allow_cached_values = allow_cached_values
            return api

        if self.is_acano:
            from provider.ext_api.acano import AcanoAPI
            return _allow_cached(AcanoAPI(provider=self, customer=customer))
        if self.is_pexip:
            from provider.ext_api.pexip import PexipAPI
            return _allow_cached(PexipAPI(provider=self, customer=customer))
        elif self.is_lifesize:
            from provider.ext_api.lifesize import LifeSizeAPI
            return _allow_cached(LifeSizeAPI(provider=self, customer=customer))
        elif self.is_clearsea:
            from provider.ext_api.clearsea import ClearSeaAPI
            return _allow_cached(ClearSeaAPI(provider=self, customer=customer))
        elif self.is_internal:
            from provider.ext_api.base import InternalAPI
            return _allow_cached(InternalAPI(provider=self, customer=customer))
        elif self.is_external or self.is_offline:
            from provider.ext_api.base import ExternalNoOpAPI
            return _allow_cached(ExternalNoOpAPI(provider=self, customer=customer))
        elif self.is_vcs:
            from provider.ext_api.vcse import VCSExpresswayAPI
            return _allow_cached(VCSExpresswayAPI(provider=self, customer=customer))

    @property
    def has_session(self):
        return self.session_id and self.session_expires > now()

    def save(self, *args, **kwargs):

        if not self.hostname:
            self.hostname = self.ip or ''

        if self.is_cluster:
            self.cluster = None
        elif not self.cluster_id:
            if self.pk:
                try:
                    self.cluster = self.clustered.all().filter(cluster__isnull=False).first().cluster
                except AttributeError:
                    pass
            if not self.cluster_id:
                self.cluster = self.create_cluster()
                if self.pk:
                    self.clustered.all().update(cluster=self.cluster)

        super().save(*args, **kwargs)

    def create_cluster(self):
        if self.is_pexip:
            from .pexip import PexipCluster
            cluster = PexipCluster.objects.create(title='Pexip Cluster')
        elif self.is_acano:
            from .acano import AcanoCluster
            cluster = AcanoCluster.objects.create(title='CMS Cluster')
        else:
            return

        ClusterSettings.objects.create(
                cluster=cluster,
                main_domain=self.internal_domain,
                web_domain=self.web_host,
                phone_ivr=self.phone_ivr,
            )

        cluster.get_statistics_server()
        return cluster

    @property
    def is_cluster(self):
        return self.type in self.CLUSTERED_TYPES

    @property
    def supports_dialout(self):
        return self.is_acano or self.is_pexip

    @property
    def is_acano(self):
        if self.type == self.TYPES.acano_cluster:
            return True
        return self.type == self.TYPES.lifesize and self.subtype in {self.SUBTYPES.acano, self.SUBTYPES.acano_node}

    @property
    def is_service_node(self):
        return self.is_acano and self.subtype == self.SUBTYPES.acano_node

    @property
    def is_pexip(self):
        if self.type == self.TYPES.pexip_cluster:
            return True

        return self.type == self.TYPES.lifesize and self.subtype in (self.SUBTYPES.pexip,)

    @property
    def is_lifesize(self):
        return self.type == self.TYPES.lifesize and (self.subtype == 0 or self.subtype is None)

    @property
    def is_clearsea(self):
        return self.type == self.TYPES.clearsea

    @property
    def is_internal(self):
        return self.type == self.TYPES.internal

    @property
    def is_external(self):
        return self.type == self.TYPES.external

    @property
    def is_offline(self):
        return self.type == self.TYPES.offline

    @property
    def is_vcs(self):
        return self.type == Provider.TYPES.vcs_cluster

    @property
    def internal_domain(self):
        if self.internal_domains:
            return self.internal_domains.split(',')[0]

        # backwards compatibility for providers before cluster existed
        if self.is_cluster and not self.hostname:
            provider: Provider = Provider.objects.filter(cluster=self).exclude(internal_domains='', hostname='').first()
            if provider:
                return provider.internal_domain
        return self.hostname

    @cached_property
    def internal_callbridge_ips(self):
        return [str(p.ip) for p in self.get_clustered() if p.ip]

    def get_options(self):

        with transaction.atomic():
            p = Provider.objects.select_for_update(of=('self',)).only('options').get(pk=self.pk)
            self.options = p.options

        return {} if not self.options else json.loads(self.options or '{}')

    def get_option(self, key):
        return self.get_options().get(key)

    _all_clustered_cache = None

    def get_all_clustered(self):

        if self._all_clustered_cache:
            return self._all_clustered_cache.copy()

        cluster = self if self.is_cluster else self.cluster
        if cluster and cluster._all_clustered_cache:
            return cluster._all_clustered_cache.copy()

        result = {
            self.pk: self
        }

        if self.is_cluster:
            result.pop(self.pk, None)

        qs = self.clustered.filter(enabled=True)
        if self.is_cluster:
            qs = qs.union(Provider.objects.filter(cluster=self, enabled=True))
        if self.cluster_id:
            qs = qs.union(Provider.objects.filter(cluster=self.cluster, enabled=True))

        for provider in qs:
            if provider.is_cluster or provider.pk in result:
                continue
            if cluster and provider.cluster_id == cluster.pk:
                provider.cluster = cluster
            result[provider.pk] = provider

        self._all_clustered_cache = result
        if cluster:
            cluster._all_clustered_cache = result
        return result.copy()

    def get_clustered(self, include_self=True, only_call_bridges=True):

        result = self.get_all_clustered()

        if not include_self or self.is_cluster:
            result.pop(self.pk, None)

        if not result and self.is_vcs:
            from provider.models.vcs import VCSEProvider
            return VCSEProvider.objects.filter(cluster=self)

        if only_call_bridges:
            return [p for p in result.values() if not p.is_service_node]

        return list(result.values())

    def is_clustered(self):

        return bool(self.get_clustered(include_self=False))

    @transaction.atomic
    def set_option(self, key, value, commit=True):

        options = self.get_options()
        if value is None:
            options.pop(key, None)
        options[key] = value

        self.options = json.dumps(options)

        if commit:
            Provider.objects.filter(pk=self.pk).update(options=self.options)

    def get_cluster_settings(self, customer=None):
        cluster = self.cluster if self.cluster_id else self
        if not cluster.is_cluster:
            return ClusterSettings.objects.get_default_for_cluster(cluster)
        result = ClusterSettings.objects.filter(cluster=cluster, customer=customer).first()
        if result:
            return result

        return ClusterSettings.objects.get_default_for_cluster(cluster)

    class Meta:
        permissions = (
            ("api_client", _("Can use API-client")),
        )
        verbose_name = _('mötesplattform')
        verbose_name_plural = _('mötesplattformar')


class ClusterManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(type__in=Provider.CLUSTERED_TYPES)


class Cluster(Provider):

    class Meta:
        proxy = True

    objects: ClusterManager['Cluster'] = ClusterManager()

    @cached_property
    def has_cdr_events(self):
        from statistics.models import Call
        cache_key = 'cluster.has_cdr_events.{}'.format(self.pk)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        has_calls = Call.objects.filter(server__cluster=self,
                                        ts_start__gt=now() - timedelta(hours=4),
                                        ts_stop__isnull=True).exists()

        if not settings.TEST_MODE:
            timeout_mins = 60 if has_calls else 5
            cache.set(cache_key, has_calls, timeout_mins * 60)

        return has_calls

    @staticmethod
    def get_provider_cluster(obj):
        if obj.is_pexip:
            from provider.models.pexip import PexipCluster
            try:
                return obj.pexipcluster
            except Exception:
                new_obj, created = PexipCluster.objects.get_or_create(
                    pk=obj.id, defaults=dict(type=Provider.TYPES.pexip_cluster)
                )
                if created:
                    obj.save()  # keep values
                    new_obj.refresh_from_db()
                return new_obj

        elif obj.is_acano:
            try:
                return obj.acanocluster
            except Exception:
                from provider.models.acano import AcanoCluster

                new_obj, created = AcanoCluster.objects.get_or_create(
                    pk=obj.id, defaults=dict(type=Provider.TYPES.acano_cluster)
                )
                if created:
                    obj.save()  # keep values
                new_obj.refresh_from_db()
                return new_obj

        elif obj.is_vcs:
            if obj.is_cluster:
                return obj
            return obj.cluster

    @cached_property
    def pexip(self):
        from provider.models.pexip import PexipCluster

        if isinstance(self, PexipCluster):
            return self
        return Cluster.get_provider_cluster(self)

    @cached_property
    def acano(self):
        from provider.models.acano import AcanoCluster

        if isinstance(self, AcanoCluster):
            return self
        return Cluster.get_provider_cluster(self)

    def get_statistics_server(self):
        from statistics.models import Server

        if self.is_pexip:
            server_type = Server.PEXIP
        elif self.is_vcs:
            server_type = Server.VCS
        elif self.is_acano:
            server_type = Server.ACANO
        else:
            server_type = Server.ACANO

        server = Server.objects.filter(cluster=self).first()
        if server:
            return server
        return Server.objects.get_or_create(cluster=self, defaults={'type': server_type, 'name': str(self)})[0]


class ClusterSettingsManager(models.Manager):

    def get_default_for_cluster(self, cluster):
        cluster = cluster.cluster if cluster.cluster_id else cluster

        if not cluster.is_cluster:
            return ClusterSettings(id='temp', cluster=cluster, main_domain=cluster.internal_domain)

        return self.get_or_create(cluster=cluster, customer=None, defaults={
            'main_domain': cluster.internal_domain,
        })[0]

    def get_for_cluster(self, cluster, customer: typing.Union[Customer, int, None] = None):
        if customer and not isinstance(customer, int):
            customer_id = customer.pk
        else:
            customer_id = customer or None
        return self._get_settings(cluster.pk, customer_id)

    @staticmethod
    @fifo_memoize(100, ttl=10)
    def _get_settings(cluster_id: int, customer_id: int):

        if customer_id:
            customer_cond = Q(customer=customer_id) | Q(customer__isnull=True)
        else:
            customer_cond = Q(customer__isnull=True)

        cluster_settings = {s.customer_id: s
                            for s in ClusterSettings.objects.filter(customer_cond, cluster=cluster_id)
                            }

        if customer_id:
            result = cluster_settings.get(customer_id) or cluster_settings.get(None)
        else:
            result = cluster_settings.get(None)

        return result or ClusterSettings.objects.get_default_for_cluster(Cluster.objects.filter(pk=cluster_id).first())


class ClusterSettings(models.Model):

    PROVISION_CHOICES = DescriptiveChoices(
        [
            (0, 'eager', _('Direkt vid bokning')),
            (10, 'schedule', _('Schemalagt')),
            (15, 'pexip_schedule', _('Pexip schemaläggning')),
            (20, 'virtual', _('Policy/virtuellt')),
        ]
    )

    PEXIP_PROVISION_CHOICES = [
        (id, title)
        for id, key, title in PROVISION_CHOICES.items
        if key in ('eager',)  # 'schedule', 'pexip_schedule', 'virtual')
    ]
    OTHER_PROVISION_CHOICES = [
        (id, title)
        for id, key, title in PROVISION_CHOICES.items
        if key in ('eager',)  # 'schedule')
    ]

    cluster: Cluster = models.ForeignKey('provider.Cluster', on_delete=models.CASCADE)
    customer = models.ForeignKey('provider.Customer', on_delete=models.CASCADE, null=True)

    main_domain = models.CharField(_('Standard SIP-domän'), max_length=100, blank=True)

    dial_out_location = models.CharField(
        _('Dial out-location för nya deltagare'), blank=True, null=True, max_length=200
    )
    theme_profile = models.CharField(
        _('Tema-inställning'),
        help_text=_('Resource-uri för pexip, ex. /admin/api/configuration/v1/ivr_theme/1234/'),
        blank=True,
        null=True,
        max_length=200,
    )

    web_domain = models.CharField(
        _('Ev. separat domän WebRTC/Web access'), max_length=100, blank=True
    )
    phone_ivr = models.CharField(_('Telefonnummer för uppringning'), max_length=25, blank=True)
    additional_domains = models.TextField(_('Alternativa SIP-domäner'), blank=True, help_text=_('Tillåt användning av ytterligare domäner för ex. mötesrum. Komma-separerad'))

    scheduled_room_number_range = models.ForeignKey('numberseries.NumberRange', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    static_room_number_range = models.ForeignKey('numberseries.NumberRange', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    meeting_provision_mode = models.IntegerField(
        _('Provisionera möten'), choices=PROVISION_CHOICES, null=True, editable=False
    )
    provision_meeting_rooms_before = models.IntegerField(
        _('Provisionera mötesrum x min före bokat möte'),
        null=True,
        editable=False,
        blank=True,
        help_text=_('För schemalagd provisionering'),
    )

    remove_expired_meeting_rooms = models.IntegerField(_('Radera mötesrum x min efter bokat möte'),
                                                         default=settings.MEETING_EXPIRE_ROOM * 60)

    objects: ClusterSettingsManager['ClusterSettings'] = ClusterSettingsManager()

    class Meta:
        unique_together = ('cluster', 'customer')

    @property
    def is_dummy(self):
        return self.id == 'temp'

    def get_scheduled_room_number_range(self):
        if self.is_dummy:
            return NumberRangeDummy()

        if self.scheduled_room_number_range_id:
            return self.scheduled_room_number_range

        if self.customer_id:
            return self.fallback_settings.get_scheduled_room_number_range()

        from numberseries.models import NumberRange
        with transaction.atomic():
            existing = ClusterSettings.objects.select_for_update(of=('self',)).get(pk=self.pk)
            if existing.scheduled_room_number_range:
                self.scheduled_room_number_range = existing.scheduled_room_number_range
                return existing.scheduled_room_number_range
            self.scheduled_room_number_range = NumberRange.objects.create(title='Default scheduled number range for cluster {}'.format(self.cluster))
            self.save(update_fields=['scheduled_room_number_range'])
        return self.scheduled_room_number_range

    def get_static_room_number_range(self):
        if self.is_dummy:
            return NumberRangeDummy()

        if self.static_room_number_range_id:
            return self.static_room_number_range

        if self.customer_id:
            return self.fallback_settings.get_static_room_number_range()

        from numberseries.models import NumberRange
        with transaction.atomic():
            existing = ClusterSettings.objects.select_for_update(of=('self',)).get(pk=self.pk)
            if existing.static_room_number_range:
                self.static_room_number_range = existing.static_room_number_range
                return existing.static_room_number_range
            self.static_room_number_range = NumberRange.objects.create(title='Default static number range for cluster {}'.format(self.cluster))
            self.save(update_fields=['static_room_number_range'])
        return self.static_room_number_range

    def get_main_domain(self):
        if self.main_domain:
            return self.main_domain

        if self.customer_id:
            return self.fallback_settings.get_main_domain()

        return self.cluster.internal_domain

    def get_additional_domains(self):
        domains = (self.additional_domains or '').strip()
        if domains:
            return [d.strip() for d in domains.split(',') if '.' in d]
        return []

    def get_web_domain(self):
        if self.web_domain:
            return self.web_domain

        if self.customer_id:
            return self.fallback_settings.get_web_domain() or self.cluster.web_host or self.get_main_domain()

        return self.cluster.web_host

    def get_dial_out_location(self):
        if self.dial_out_location:
            return self.dial_out_location

        if self.customer_id:
            return self.fallback_settings.get_dial_out_location()

        return ''

    def get_theme_profile(self):
        if self.theme_profile:
            return self.theme_profile

        if self.customer_id:
            return self.fallback_settings.get_theme_profile()

        return ''

    def get_phone_ivr(self):
        if self.phone_ivr:
            return self.phone_ivr

        if self.customer_id:
            return self.fallback_settings.get_phone_ivr()

        return self.cluster.phone_ivr

    @cached_property
    def fallback_settings(self):
        if not self.customer_id:
            return None

        return ClusterSettings.objects.get_default_for_cluster(self.cluster)


class VideoCenterProviderManager(models.Manager):

    def get_active(self):
        return VideoCenterProvider.objects.filter(is_standard=True).first()


class VideoCenterProvider(ProviderAPICompatible, models.Model):

    MIVIDAS_STREAMING = 40
    TYPES = (
        (0, _('Videocenter')),
        (10, _('Rec.VC')),
        (15, _('RTMP Streaming')),
        (20, _('Quickchannel')),
        (30, _('CMS native recording')),
        (MIVIDAS_STREAMING, _('Mividas streaming')),
    )

    type = models.IntegerField(choices=TYPES, default=0)
    customer = models.ForeignKey(Customer, verbose_name=_('Kund'), null=True, blank=True, on_delete=models.CASCADE)
    is_standard = models.BooleanField(_('Är fallback'), help_text=_('Används som standard för kunder som inte har en specifik provider angedd'), blank=True, default=False)

    title = models.CharField(_('Beskrivning'), max_length=50)
    ip = models.GenericIPAddressField(_('IP-nummer'), blank=True, null=True)
    hostname = models.CharField(_('DNS-namn'), max_length=100, blank=True)

    api_host = models.CharField(_('Ev. separat api-ip/host'), max_length=100, blank=True)
    web_host = models.CharField(_('Ev. separat hostname för webbaccess'), max_length=100, blank=True)

    username = models.CharField(_('Användarnamn'), max_length=50, blank=True)
    password = models.CharField(_('Lösenord'), max_length=50, blank=True)
    channel = models.CharField(_('Channel'), max_length=50, blank=True)
    recording_key = models.CharField(_('Recording-key'), max_length=200, blank=True)

    session_id = models.CharField(max_length=200, blank=True, editable=False)
    session_expires = models.DateTimeField(blank=True, null=True, editable=False)

    cluster = None

    objects = VideoCenterProviderManager()

    @property
    def is_cluster(self):
        return False

    def get_clustered(self, include_self=True, only_call_bridges=True):
        return [self] if include_self else []

    @property
    def is_videocenter(self):
        return self.type == 0

    @property
    def is_recvc(self):
        return self.type == 10

    @property
    def is_quickchannel(self):
        return self.type == 20

    @property
    def is_acano_native(self):
        return self.type == 30

    @property
    def is_rtmp(self):
        return self.type == 15

    @property
    def is_mividas_stream(self):
        return self.type == 40

    @property
    def has_session(self):
        return self.session_id and self.session_expires >= now()

    @property
    def display_web_host(self):
        if self.web_host:
            return self.web_host
        return self.hostname

    def get_api(self, customer):
        if self.is_recvc:
            from recording.ext_api.recvc import RecVcAPI
            return RecVcAPI(self, customer=customer)
        if self.is_quickchannel:
            from recording.ext_api.quickchannel import QuickChannelAPI
            return QuickChannelAPI(self, customer=customer)
        if self.is_acano_native:
            from recording.ext_api.acano_recording import AcanoRecordingAPI
            return AcanoRecordingAPI(self, customer=customer)
        if self.is_rtmp:
            from recording.ext_api.acanortmp import RTMPStreamAPI
            return RTMPStreamAPI(self, customer=customer)
        if self.is_mividas_stream:
            from recording.ext_api.mividas_stream import MividasStreamAPI
            return MividasStreamAPI(self, customer=customer)

        from recording.ext_api.videocenter import VideoCenterAPI
        return VideoCenterAPI(self, customer=customer)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):

        if self.is_recvc:
            try:
                self.channel = self.get_api(Customer.objects.all()[0]).get_recorders()[0]['recorder_id']
            except Exception:
                pass
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'recording/streaming'
        verbose_name_plural = 'recording/streaming'


class TandbergProvider(models.Model):

    hostname = models.CharField(_('DNS-namn'), max_length=100, blank=True)

    verify_certificate = models.BooleanField(
        _('Verifiera SSL-certifikat'),
        blank=True,
        default=False,
        help_text=_('Använd fullständigt domännamn som matchar serverns certifikat'),
    )

    phonebook_url = models.CharField(
        _('URL till telefonbok'),
        max_length=200,
        blank=True,
        default='/tms/public/external/phonebook/phonebookservice.asmx?op=%s',
    )
    mac_address = models.CharField(_('MAC-adress för verifiering'), max_length=100, blank=True)
    default_domain = models.CharField(_('Standarddomän för URIs utan'), max_length=100, blank=True)

    def save(self, *args, **kwargs):
        if not self.hostname and '://' in self.phonebook_url:
            self.hostname = urlparse(self.phonebook_url).hostname

        super().save(*args, **kwargs)

    def get_api(self):
        from provider.ext_api.tandberg import TandbergAPI

        return TandbergAPI(
            self.mac_address,
            self.hostname,
            default_domain=self.default_domain,
            phonebook_url=self.phonebook_url,
            verify_certificate=self.verify_certificate,
        )

    def __str__(self):
        return self.hostname

    class Meta:
        verbose_name = 'Cisco/Tandberg TMS'
        verbose_name_plural = 'Cisco/Tandberg TMS'


class SeeviaProvider(ProviderAPICompatible, models.Model):

    title = models.CharField(_('Beskrivning'), max_length=50)

    is_test = models.BooleanField(_('Använd testserver'), blank=True, default=False, editable=False)

    username = models.CharField(_('Användarnamn'), max_length=64, blank=True)
    password = models.CharField(_('Lösenord'), max_length=64, blank=True)

    session_id = ''
    session_expires = None

    def get_api(self, customer):
        from provider.ext_api.seevia import SeeviaAPI
        return SeeviaAPI(provider=self, customer=customer)

    @property
    def hostname(self):
        if self.is_test:
            return 'backend-staging.seevia.me'
        return 'www.seevia.me'

    @property
    def api_host(self):
        return self.hostname

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('seevia-konto')
        verbose_name_plural = _('seevia-konton')


class LdapProvider(models.Model):

    title = models.CharField(_('Beskrivning'), max_length=50)

    ip = models.GenericIPAddressField(_('IP-nummer'), blank=True, null=True)
    hostname = models.CharField(_('DNS-namn'), max_length=100, blank=True)
    base_dn = models.CharField(_('Base DN'), max_length=300, blank=True)

    username = models.CharField(_('Användarnamn'), max_length=50, blank=True)
    password = models.CharField(_('Lösenord'), max_length=50, blank=True)

    def get_api(self, customer=None):
        from provider.ext_api.ldapconn import LDAPConnection

        return LDAPConnection(self.ip, self.base_dn, self.username, self.password)

    @property
    def api_host(self):
        return self.hostname

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _('LDAP-server')
        verbose_name_plural = _('LDAP-servrar')


def clear_cache(sender=None, **kwargs):
    ClusterSettingsManager._get_settings.cache.clear()


models.signals.post_save.connect(clear_cache, sender=ClusterSettings)
models.signals.post_delete.connect(clear_cache, sender=ClusterSettings)
