from django.db import models
from django.db.models import Q, QuerySet
from django.db.models.functions import Lower
from mptt.models import TreeForeignKey
from django.utils.timezone import now

from datastore.models.customer import Tenant
from datastore.models.ldap import LdapOU
from provider.exceptions import NotFound
from provider.models.provider import Provider
from datetime import timedelta


class UserManager(models.Manager):

    def get_user(self, api, uid, force_sync=False):
        from datastore.utils.acano import sync_acano_user

        try:
            user = self.get_queryset().get(uid=uid, provider=api.provider)
            if user.should_update_data or force_sync:
                return sync_acano_user(api, uid, update_ldap=True)
            return user
        except User.DoesNotExist:
            try:
                return sync_acano_user(api, uid, update_ldap=True)
            except NotFound:
                raise User.DoesNotExist()

    def search_active(
        self, provider: Provider, q=None, tenant: str = None, org_unit=None, **kwargs
    ) -> 'QuerySet[User]':
        cond = Q(**kwargs)

        if isinstance(q, dict):  # TODO filter valid filter keys
            q_str = q.pop('q', None)
            cond &= Q(**q)
        else:
            q_str = q

        if q_str:
            for f in ('name', 'username', 'email', 'ldap_username'):
                cond |= Q(**{f + '__istartswith': q_str})
            cond |= Q(name__icontains=' ' + q_str.strip())

        result = self.filter(provider=provider, is_active=True).filter(cond)

        if org_unit:
            from organization.models import OrganizationUnit

            result = result.filter(OrganizationUnit.objects.get_filter(org_unit))

        if tenant == '':
            result = result.filter(tenant__isnull=True)
        elif tenant is not None:
            result = result.filter(tenant__tid=tenant)

        return result.select_related('tenant').order_by(Lower('username'))


class User(models.Model):

    uid = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=200)
    username = models.CharField(max_length=200, db_index=True)
    email = models.CharField(max_length=200, db_index=True)
    cdr_tag = models.CharField(max_length=500)

    provider = models.ForeignKey(Provider, related_name='datastore_users', db_index=False, on_delete=models.CASCADE)

    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True)
    customer = models.ForeignKey('provider.Customer', on_delete=models.SET_NULL, null=True, db_index=False,
                                 editable=False, related_name='ds_users')

    ldap_username = models.CharField(max_length=100)
    ldap_ou = TreeForeignKey(LdapOU, related_name='users', null=True, blank=True, on_delete=models.CASCADE)

    organization_unit = models.ForeignKey('organization.OrganizationUnit', null=True, db_index=False, on_delete=models.SET_NULL)

    ts_created = models.DateTimeField(auto_now_add=True)
    last_synced = models.DateTimeField(auto_now_add=True)
    last_synced_data = models.DateTimeField(null=True)
    last_synced_ldap = models.DateTimeField(null=True)
    last_synced_cospaces = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)

    ts_instruction_email_sent = models.DateTimeField(null=True)

    objects = UserManager()

    def __str__(self):
        return self.name

    @property
    def should_update_data(self):
        if not self.last_synced_data:
            return True
        return self.last_synced_data < now() - timedelta(hours=6)

    @property
    def should_update_ldap(self):
        if not self.last_synced_ldap:
            return True
        return self.last_synced_ldap < now() - timedelta(hours=12)

    def to_dict(self):

        return {
            'id': self.uid,
            'name': self.name,
            'jid': self.username,
            'email': self.email,
            'tenant': self.tenant.tid if self.tenant_id else '',
            'ldap_username': self.ldap_username,
            'organization_unit': self.organization_unit_id,
        }

    class Meta:
        unique_together = ('uid', 'provider')
        indexes = [
            models.Index(name='ds_acano_user_is_active', fields=('provider', 'last_synced'),
                         condition=models.Q(is_active=True)),
            models.Index(name='ds_acano_user_data', fields=('provider', 'last_synced_data'),
                         condition=models.Q(is_active=True)),
            models.Index(name='ds_acano_user_org_unit', fields=('organization_unit',),
                         condition=models.Q(organization_unit__isnull=False, is_active=True)),
            models.Index(name='ds_acano_user_customer', fields=('customer',),
                         condition=models.Q(customer__isnull=False)),
        ]


class CoSpaceManager(models.Manager):

    def get_by_call_id(self, cluster, call_id, only_active=False):
        result = CoSpace.objects.distinct().filter(provider=cluster).filter(Q(call_id=call_id) | Q(access_methods__call_id=call_id))
        if only_active:
            return result.filter(is_active=True)
        return result.first()

    def get_by_uri(self, cluster, uri, only_active=False):
        result = CoSpace.objects.distinct().filter(provider=cluster).filter(Q(uri=uri) | Q(access_methods__uri=uri))
        if only_active:
            return result.filter(is_active=True)
        return result.first()

    def search_active(
        self, provider: Provider, q=None, tenant: str = None, org_unit=None, **kwargs
    ) -> 'QuerySet[CoSpace]':
        cond = Q(**kwargs)

        if isinstance(q, dict):  # TODO filter valid filter keys
            q_str = q.pop('q', None)
            cond &= Q(**q)
        else:
            q_str = q

        if q_str:
            for f in ('name', 'call_id', 'uri'):
                cond |= Q(**{f + '__istartswith': q_str})
            cond |= Q(name__icontains=' ' + q_str.strip())
            cond |= Q(
                Q(access_methods__call_id__startswith=q_str.lower())
                | Q(access_methods__uri__startswith=q_str.lower()),
            )

        result = CoSpace.objects.distinct().filter(provider=provider, is_active=True).filter(cond)

        if org_unit:
            from organization.models import OrganizationUnit

            result = result.filter(OrganizationUnit.objects.get_filter(org_unit))

        if tenant == '':
            result = result.filter(tenant__isnull=True)
        elif tenant is not None:
            result = result.filter(tenant__tid=tenant)

        return result.select_related('tenant', 'owner').order_by(Lower('name'))


class CoSpace(models.Model):

    cid = models.CharField(max_length=100, db_index=True)
    uri = models.CharField(max_length=100)
    secondary_uri = models.CharField(max_length=100)
    name = models.CharField(max_length=200)

    is_scheduled = models.BooleanField(null=True)

    passcode = models.CharField(max_length=200)

    provider = models.ForeignKey(Provider, related_name='datastore_cospaces', db_index=False, on_delete=models.CASCADE)
    cdr_tag = models.CharField(max_length=500)

    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owner_cospaces')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True)
    customer = models.ForeignKey('provider.Customer', on_delete=models.SET_NULL, null=True, db_index=False, editable=False, related_name='ds_cospaces')
    is_auto = models.BooleanField(default=False)

    call_id = models.CharField(max_length=50, db_index=True)
    secret = models.CharField(max_length=50, db_index=True)
    stream_url = models.CharField(max_length=200, db_index=True)

    organization_unit = models.ForeignKey('organization.OrganizationUnit', null=True, db_index=False, on_delete=models.SET_NULL)

    num_access_methods = models.IntegerField(null=True)

    ts_created = models.DateTimeField(auto_now_add=True)

    last_synced = models.DateTimeField(auto_now_add=True)
    last_synced_data = models.DateTimeField(null=True)
    last_synced_members = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)

    users = models.ManyToManyField(User, through='CoSpaceMember', related_name='cospaces')

    objects = CoSpaceManager()

    def __str__(self):
        return self.name

    @property
    def should_update_data(self):

        if not self.last_synced_data:
            return True
        return self.last_synced_data < now() - timedelta(hours=1)

    @property
    def should_update_members(self):
        if not self.last_synced_members:
            return True
        return self.last_synced_members < now() - timedelta(days=1)

    def to_dict(self):

        return {
            'tenant': self.tenant.tid if self.tenant_id else '',
            'call_id': self.call_id,
            'uri': self.uri,
            'auto_generated': self.is_auto,
            'owner_id': self.owner.uid if self.owner_id else '',
            'owner_jid': self.owner.username if self.owner_id else '',
            'name': self.name,
            'id': self.cid,
            'secret': self.secret,
            'stream_url': self.stream_url,
            'organization_unit': self.organization_unit_id,
            'passcode': self.passcode,
            'num_access_methods': self.num_access_methods,
        }

    def to_acano_dict(self):
        return {
            'tenant': self.tenant.tid if self.tenant_id else '',
            'callId': self.call_id,
            'call_id': self.call_id,
            'uri': self.uri,
            'autoGenerated': self.is_auto,
            'ownerJid': self.owner.username if self.owner_id else None,
            'ownerId': self.owner.uid if self.owner_id else None,
            'name': self.name,
            'id': self.cid,
            'secret': self.secret,
            'streamUrl': self.stream_url,
            'passcode': self.passcode,
            'numAccessMethods': self.num_access_methods,
        }

    class Meta:
        unique_together = ('cid', 'provider')
        indexes = [
            models.Index(name='ds_acano_cospace_active', fields=('provider', 'last_synced'),
                         condition=models.Q(is_active=True)),
            models.Index(name='ds_acano_cospace_data', fields=('provider', 'last_synced_data'),
                         condition=models.Q(is_active=True)),
            models.Index(name='ds_acano_cospace_org_unit', fields=('organization_unit',),
                         condition=models.Q(organization_unit__isnull=False, is_active=True)),
            models.Index(name='ds_acano_cospace_customer', fields=('customer',),
                         condition=models.Q(customer__isnull=False)),
        ]


class CoSpaceAccessMethod(models.Model):

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='+')
    aid = models.CharField(max_length=100)
    name = models.CharField(max_length=255, blank=True, null=True)
    cospace = models.ForeignKey(CoSpace, on_delete=models.CASCADE, related_name='access_methods')
    uri = models.CharField(max_length=100)
    call_id = models.CharField(max_length=100)
    passcode = models.CharField(max_length=100)
    scope = models.CharField(max_length=100, blank=True, null=True)
    secret = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ('aid', 'provider')


class CoSpaceMember(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    cospace = models.ForeignKey(CoSpace, on_delete=models.CASCADE, related_name='+')

    ts_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'cospace')

    def __str__(self):
        return self.user.name
