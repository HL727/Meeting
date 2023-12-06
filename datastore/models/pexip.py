import json
import uuid

from django.db import models
from django.db.models import Q, QuerySet
from django.db.models.functions import Lower
from django.utils.timezone import now
from jsonfield import JSONField

from datastore.models.customer import Tenant
from provider.models.provider import Provider


class Email(models.Model):
    provider = models.ForeignKey(Provider, related_name='datastore_pexip_emails', on_delete=models.CASCADE)
    email = models.CharField(max_length=100, db_index=True)


class Theme(models.Model):

    provider = models.ForeignKey(Provider, related_name='datastore_pexip_themes', on_delete=models.CASCADE)
    tid = models.IntegerField(null=True)
    name = models.CharField(max_length=100)
    uuid = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(default=now, editable=False)

    class Meta:
        unique_together = ('provider', 'tid')


class ConferenceManager(models.Manager):

    def match(self, obj_or_name, cluster=None, only_active=True):
        if not obj_or_name:
            return None

        if isinstance(obj_or_name, str):
            obj = {'conference': obj_or_name}
            name = obj_or_name
        else:
            obj = obj_or_name
            name = obj.get('conference') or obj.get('conference_name') or obj.get('name')

        conferences = self.select_related('tenant', 'match').order_by('-last_synced')
        if only_active:
            conferences = conferences.filter(is_active=True)

        if cluster:
            conferences = conferences.filter(provider=cluster)

        if name:
            conference = conferences.filter(name=name).first()
            if conference:
                return conference

        local_alias = obj.get('local_alias')
        if local_alias:
            from statistics.parser.utils import clean_target
            conference = conferences.filter(aliases__alias=str(clean_target(local_alias)).lower(), aliases__is_active=True).first()
            if conference:
                return conference

        return None

    def match_by_alias(self, alias, cluster=None, only_active=True):

        return self.match({'local_alias': alias}, cluster=cluster, only_active=only_active)

    def get_active(self, provider, external_id=None, name=None):
        if not (external_id or name):
            raise ValueError('ID or name must be provided')

        result = self.filter(provider=provider, is_active=True).order_by('-last_synced')
        if external_id:
            result = result.filter(cid=external_id)
        if name:
            result = result.filter(name=name)

        return result.get()

    def search_active(
        self, provider: Provider, q=None, tenant: str = None, org_unit=None, **kwargs
    ) -> 'QuerySet[Conference]':
        cond = Q()

        if isinstance(q, dict):  # TODO filter valid filter keys
            q_str = q.pop('q', None)
            if q.get('primary_owner_email_address'):
                q['email__email'] = q.pop('primary_owner_email_address')
            cond &= Q(**q)
        else:
            q_str = q

        if q_str:
            text_cond = Q()
            for f in ('name', 'description'):
                text_cond |= Q(**{f + '__istartswith': q_str})
            text_cond |= Q(name__icontains=' ' + q_str.strip())
            text_cond |= Q(
                **{'aliases__alias__startswith': q_str.lower(), 'aliases__is_active': True}
            )
            cond &= text_cond

        if 'type' in kwargs:
            if kwargs['type'] == 'cospace':
                kwargs['service_type'] = 'conference'
            elif kwargs['type'] == 'webinar':
                kwargs['service_type'] = 'lecture'
            kwargs.pop('type')

        cond &= Q(**kwargs)

        result = self.distinct().filter(provider=provider, is_active=True).filter(cond)

        if org_unit:
            from organization.models import OrganizationUnit

            result = result.filter(OrganizationUnit.objects.get_filter(org_unit))

        if tenant == '':
            result = result.filter(tenant__isnull=True)
        elif tenant is not None:
            result = result.filter(tenant__tid=tenant)

        return result.select_related('tenant', 'email').order_by(Lower('name'))


class Conference(models.Model):

    provider = models.ForeignKey(Provider, related_name='datastore_pexip_conferences', db_index=False, on_delete=models.CASCADE)

    cid = models.IntegerField(null=True)

    guid = models.UUIDField(default=uuid.uuid4, null=True, editable=False, blank=True)
    is_virtual = models.BooleanField(null=True, blank=True, editable=False)

    name = models.CharField(max_length=250, null=True)
    description = models.CharField(max_length=250)

    allow_guests = models.BooleanField(default=True)
    guest_pin = models.CharField(max_length=200)
    pin = models.CharField(max_length=200)

    tag = models.CharField(max_length=500, editable=False)
    sync_tag = models.CharField(max_length=500, editable=False)
    email = models.ForeignKey(Email, on_delete=models.SET_NULL, null=True)

    is_scheduled = models.BooleanField(null=True)

    scheduled_id = models.IntegerField(null=True)
    service_type = models.CharField(max_length=100)

    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True)
    match = models.ForeignKey('customer.CustomerMatch', on_delete=models.SET_NULL, null=True, db_index=False,
                              editable=False)
    customer = models.ForeignKey('provider.Customer', on_delete=models.SET_NULL, null=True, db_index=False,
                                 editable=False, related_name='ds_conferences')

    theme = models.ForeignKey(Theme, on_delete=models.SET_NULL, null=True)
    organization_unit = models.ForeignKey('organization.OrganizationUnit', null=True, db_index=False, on_delete=models.SET_NULL)

    # cached/computed
    call_id = models.CharField(max_length=200, blank=True, null=True, editable=False)  # TODO IntegerField?
    web_url = models.CharField(max_length=200, blank=True, editable=False)

    ts_created = models.DateTimeField(auto_now_add=True, editable=False)

    last_synced = models.DateTimeField(default=now, editable=False)
    last_synced_data = models.DateTimeField(null=True, editable=False)
    last_synced_members = models.DateTimeField(null=True, editable=False)

    automatic_participants = models.ManyToManyField('ConferenceAutoParticipant')

    is_active = models.BooleanField(default=True, editable=False)

    full_data = models.TextField(blank=True, editable=False)  # for external policy response

    objects = ConferenceManager()

    @property
    def primary_owner_email_address(self):
        return self.email.email if self.email_id else None

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = None
        self.call_id = self.call_id or None
        super().save(*args, **kwargs)

    def get_customer(self):
        from customer.models import MatchCache
        if not self.tenant_id and not self.match_id:
            return None

        if self.tenant_id:
            customer = MatchCache.match_cluster_tenant(self.provider_id, self.tenant.tid)
            if customer:
                return customer
        return self.match.customer if self.match_id else None

    @property
    def resource_uri(self):
        return '/api/admin/configuration/v1/conference/{}/'.format(self.cid)

    def to_dict(self):

        resource_uri = self.resource_uri

        aliases = [a.to_dict() for a in self.aliases.filter(is_active=True)]
        number_aliases = [a for a in aliases if a['alias'].split('@')[0].isdigit()]

        result = {f.name: getattr(self, f.name) for f in self._meta.get_fields() if not f.is_relation and f.editable}
        result.update((k, v) for k, v in json.loads(self.full_data or '{}').items())
        result['primary_owner_email_address'] = self.email.email if self.email_id else ''
        result['id'] = result.pop('cid')
        result['aliases'] = aliases
        result['call_id'] = self.call_id or ([a['alias'] for a in number_aliases] or [None])[0]
        result['full_uri'] = ([a['alias'] for a in aliases if '@' in a['alias']] or [''])[0]
        result['uri'] = ([a['alias'] for a in aliases if '@' not in a['alias']] or [''])[0]
        result['web_url'] = self.web_url

        result['tenant'] = self.tenant.tid if self.tenant_id else ''
        result['resource_uri'] = resource_uri
        result['organization_unit'] = self.organization_unit_id

        return result

    def to_dict_compact(self):
        return {
            'id': self.cid,
            'name': self.name,
            'call_id': self.call_id,
            'web_url': self.web_url,
            'tenant': self.tenant.tid if self.tenant_id else '',
        }

    def get_members(self):
        result = []

        users = EndUser.objects.filter(provider=self.provider, email__conference=self)
        if self.tenant_id is None:
            users = users.filter(tenant__isnull=True)
        else:
            users = users.filter(tenant=self.tenant_id)

        for user in users:

            cur = user.to_dict_compact()
            cur.update({
                'user_id': cur['id'],
                'auto_generated': False,
                'permissions': [],
            })
            result.append(cur)

        return result

    class Meta:
        unique_together = (('cid', 'provider'), ('guid', 'provider'))
        indexes = [
            models.Index(fields=('name', 'provider')),
            models.Index(name='ds_pexip_conferenance_active', fields=('provider', 'last_synced'), condition=models.Q(is_active=True)),
            models.Index(name='ds_pexip_conferenance_org', fields=('organization_unit',), condition=models.Q(organization_unit__isnull=False, is_active=True)),
            models.Index(name='ds_pexip_conferenance_cust', fields=('customer',), condition=models.Q(customer__isnull=False)),
            models.Index(name='ds_pexip_conferenance_match', fields=('match',), condition=models.Q(match__isnull=False)),
        ]


class EndUserManager(models.Manager):

    def get_active(self, provider, external_id=None, name=None):
        if not (external_id or name):
            raise ValueError('ID or name must be provided')

        result = self.filter(provider=provider, is_active=True).order_by('-last_synced')
        if external_id:
            result = result.filter(uid=external_id)
        if name:
            result = result.filter(name=name)

        return result.get()

    def search_active(
        self, provider: Provider, q=None, tenant: str = None, org_unit=None, **kwargs
    ) -> 'QuerySet[EndUser]':
        cond = Q(**kwargs)

        if isinstance(q, dict):  # TODO filter valid filter keys
            q_str = q.pop('q', None)
            if q.get('primary_email_address'):
                q['email__email'] = q.pop('primary_email_address')
            cond &= Q(**q)
        else:
            q_str = q

        if q_str:
            for f in ('first_name', 'last_name', 'display_name', 'description', 'email__email'):
                cond |= Q(**{f + '__istartswith': q_str})
            cond |= Q(display_name__icontains=' ' + q_str.strip())

        result = self.filter(provider=provider, is_active=True).filter(cond)

        if org_unit:
            from organization.models import OrganizationUnit

            result = result.filter(OrganizationUnit.objects.get_filter(org_unit))

        if tenant == '':
            result = result.filter(tenant__isnull=True)
        elif tenant is not None:
            result = result.filter(tenant__tid=tenant)

        return result.select_related('tenant', 'email').order_by(Lower('display_name'))


class EndUser(models.Model):

    provider = models.ForeignKey(Provider, related_name='datastore_pexip_end_users', db_index=False, on_delete=models.CASCADE)

    uid = models.IntegerField(null=True)
    email = models.ForeignKey(Email, null=True, on_delete=models.SET_NULL)
    uuid = models.CharField(max_length=100, editable=False)
    sync_tag = models.CharField(max_length=100, editable=False)

    avatar_url = models.CharField(max_length=200)

    first_name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)

    description = models.CharField(max_length=200)

    match = models.ForeignKey('customer.CustomerMatch', on_delete=models.SET_NULL, null=True, db_index=False,
                              editable=False)
    customer = models.ForeignKey('provider.Customer', on_delete=models.SET_NULL, null=True, db_index=False,
                                 editable=False, related_name='ds_endusers')
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True)

    organization_unit = models.ForeignKey('organization.OrganizationUnit', null=True, db_index=False, on_delete=models.SET_NULL)

    is_active = models.BooleanField(default=True, editable=False)

    ts_created = models.DateTimeField(auto_now_add=True, editable=False)
    last_synced = models.DateTimeField(default=now, editable=False)

    objects = EndUserManager()

    @property
    def primary_email_address(self):
        return self.email.email if self.email_id else None

    @property
    def name(self):
        if self.display_name:
            return self.display_name
        return '{} {}'.format(self.first_name, self.last_name).strip() or self.primary_email_address or ''

    class Meta:
        unique_together = ('provider', 'uid')
        indexes = [
            models.Index(name='ds_pexip_enduser_active', fields=('provider', 'last_synced'), condition=models.Q(is_active=True)),
            models.Index(name='ds_pexip_enduser_org', fields=('organization_unit',), condition=models.Q(organization_unit__isnull=False, is_active=True)),
            models.Index(name='ds_pexip_enduser_customer', fields=('customer',), condition=models.Q(customer__isnull=False)),
            models.Index(name='ds_pexip_enduser_match', fields=('match',), condition=models.Q(match__isnull=False)),
        ]

    @property
    def should_update_ldap(self):
        return False  # TODO

    def to_dict(self):
        return {
            'id': self.uid,
            'email': self.primary_email_address,
            'primary_email_address': self.primary_email_address,
            'uuid': self.uuid,
            'sync_tag': self.sync_tag,
            'avatar_url': self.avatar_url,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'display_name': self.display_name,
            'name': self.display_name,
            'description': self.description,
            'tenant': self.tenant.tid if self.tenant_id else '',
            'organization_unit': self.organization_unit_id,
        }

    def to_dict_compact(self):
        result = {
            'name': self.name,
            'email': self.primary_email_address,
            'primary_email_address': self.primary_email_address,
            'id': self.uid,
            'tenant': self.tenant.tid if self.tenant_id else '',
        }
        return result


class ConferenceAlias(models.Model):

    provider = models.ForeignKey(Provider, related_name='datastore_pexip_conference_aliases', db_index=False, on_delete=models.CASCADE)
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='aliases')

    aid = models.IntegerField(null=True)

    guid = models.UUIDField(default=uuid.uuid4, null=True, editable=False, blank=True)
    is_virtual = models.BooleanField(null=True, blank=True, editable=False)

    alias = models.CharField(max_length=200, db_index=True)
    description = models.CharField(max_length=250, blank=True)

    is_active = models.BooleanField(default=True, editable=False)
    last_synced = models.DateTimeField(default=now, editable=False)

    class Meta:
        unique_together = (('aid', 'provider'), ('guid', 'provider'))
        indexes = [
            models.Index(name='ds_pexip_alias_active', fields=('provider', 'last_synced'), condition=models.Q(is_active=True)),
        ]

    def save(self, *args, **kwargs):
        self.alias = self.alias.lower()
        return super().save(*args, **kwargs)

    def to_dict(self):
        return {
            'alias': self.alias,
            'id': self.aid,
            'description': self.description,
        }


class ConferenceAutoParticipant(models.Model):

    provider = models.ForeignKey(Provider, related_name='datastore_pexip_auto_participants', db_index=False, on_delete=models.CASCADE)

    pid = models.IntegerField(null=True)

    guid = models.UUIDField(default=uuid.uuid4, null=True, editable=False, blank=True)
    is_virtual = models.BooleanField(null=True, blank=True, editable=False)

    alias = models.CharField(max_length=255, db_index=True)
    role = models.CharField(max_length=255)
    remote_display_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)

    full_data = JSONField()  # for external policy response

    is_active = models.BooleanField(default=True, editable=False)
    last_synced = models.DateTimeField(default=now, editable=False)

    class Meta:
        unique_together = (('pid', 'provider'), ('guid', 'provider'))


def clear_cache(sender, **kwargs):

    from customer.models import CustomerMatchManager
    CustomerMatchManager._pexip_get_conference.cache.clear()
    CustomerMatchManager._pexip_get_local_alias.cache.clear()
    CustomerMatchManager._real_match_from_text.cache.clear()


models.signals.post_save.connect(clear_cache, sender=Conference)
models.signals.post_save.connect(clear_cache, sender=ConferenceAlias)
models.signals.post_delete.connect(clear_cache, sender=Conference)
models.signals.post_delete.connect(clear_cache, sender=ConferenceAlias)
