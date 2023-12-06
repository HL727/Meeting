from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import localtime, now
from datetime import timedelta
from meeting.models import Meeting
from provider.models.provider import TandbergProvider, SeeviaProvider, LdapProvider
from customer.models import Customer
import json
from .sync import SeeviaSyncer, LdapSyncer
import logging

logger = logging.getLogger(__name__)


class SeeviaSyncManager(models.Manager):

    def sync(self, customer):

        result = []
        for s in SeeviaSync.objects.filter(customer=customer):
            SeeviaSyncState.objects.get_or_create(seevia=s)
            with transaction.atomic():
                cur = SeeviaSyncState.objects.select_for_update().get(seevia=s).sync()
                result.append(cur)

        return result


class SeeviaSync(models.Model):

    provider = models.ForeignKey(SeeviaProvider, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    base_dir = models.CharField(_('Mapp-ID'), max_length=64, blank=True)
    sync_meetings = models.BooleanField(_('Synka kommande möten'), default=True)
    sync_users = models.BooleanField(_('Synka användare'), default=False,
                                     help_text=_('Fungerar bara för kunder med egen tenant'))
    sync_minutes = models.IntegerField(_('Synka möten som startar inom x min'), default=60)

    objects = SeeviaSyncManager()

    def __str__(self):
        services = []
        if self.sync_users:
            services.append(str(_('användare')))
        if self.sync_meetings:
            services.append(str(_('kommande möten')))

        return '{} ({})'.format(self.provider, ' + '.join(services))


class SeeviaSyncState(models.Model):

    seevia = models.ForeignKey(SeeviaSync, on_delete=models.CASCADE)
    data_json = models.TextField()
    ts_synced = models.DateTimeField(auto_now=True)

    @property
    def data(self):
        return json.loads(self.data_json or '[]')

    @data.setter
    def data(self, data):
        self.data_json = json.dumps(data)

    def get_valid_meetings(self):

        start = now() + timedelta(minutes=self.seevia.sync_minutes)

        upcoming = Meeting.objects.filter(customer=self.seevia.customer, backend_active=True, ts_start__lt=start, ts_stop__gt=now()).order_by('ts_start')

        result = []

        for u in upcoming:
            if (u.ts_stop - u.ts_start).days >= 1:
                continue
            username = u.creator.split('@', 1)[0]

            cur = {
                'name': '{} - {} av {}'.format(str(localtime(u.ts_start).time())[:5], str(localtime(u.ts_stop).time())[:5], username),
                'uri': u.sip_uri,
                'time': str(u.ts_start.time()),
                'id': None,
            }

            result.append(cur)

        return result

    def get_valid_users(self):

        api = self.seevia.customer.get_api()
        users = api._iter_all_users(tenant_id=self.seevia.customer.acano_tenant_id)

        result = []

        for u in users:
            data = api.get_user(u.get('id'))

            cur = {
                'name': data.get('name'),
                'uri': data.get('jid'),
                'id': None
            }
            result.append(cur)

        return result

    def get_valid(self):

        result = []
        if self.seevia.sync_meetings:
            result.extend(self.get_valid_meetings())

        if self.seevia.sync_users:
            result.extend(self.get_valid_users())

        return result

    def sync(self):

        syncer = SeeviaSyncer(self.get_valid(), self.data, {
            'base_dir': self.seevia.base_dir,
            'api': self.seevia.provider.get_api(self.seevia.customer),
            })

        self.data = syncer.sync()
        self.save()

        return self.data


class LdapSyncManager(models.Manager):

    def sync(self, customer):

        result = []
        for l in LdapSync.objects.filter(customer=customer):
            LdapSyncState.objects.get_or_create(ldap=l)
            with transaction.atomic():
                cur = LdapSyncState.objects.select_for_update().get(ldap=l).sync()
                result.append(cur)

        return result


class LdapSync(models.Model):

    provider = models.ForeignKey(LdapProvider, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, blank=True, null=True, on_delete=models.CASCADE)

    base_dn = models.CharField(_('Synka till OU'), max_length=300, blank=True)
    obj_class = models.CharField(_('Class för objekt'), default='InetPerson', max_length=300, blank=True)

    sync_cospaces = models.BooleanField(_('Lägg upp objekt för cospaces'), default=False)
    sync_address_book = models.BooleanField(_('Synka adressbok'), default=False)
    sync_tms = models.ForeignKey(TandbergProvider, blank=True, null=True, on_delete=models.CASCADE)

    objects = LdapSyncManager()

    def __str__(self):
        return str(self.customer)

    def get_api(self):
        return self.provider.get_api(self.customer)


class LdapSyncState(models.Model):

    ldap = models.ForeignKey(LdapSync, on_delete=models.CASCADE)
    data_json = models.TextField()

    ts_synced = models.DateTimeField(auto_now=True)

    @property
    def data(self):
        return json.loads(self.data_json or '[]')

    @data.setter
    def data(self, data):
        self.data_json = json.dumps(data)

    def get_valid(self):

        result = []

        if self.ldap.sync_cospaces:
            tenant = self.ldap.customer.acano_tenant_id
            domain = self.ldap.customer.get_provider().hostname

            from datastore.models import acano as ds

            cospaces = ds.CoSpace.objects.filter(provider=self.ldap.customer.get_provider(), is_active=True, is_auto=False)
            if tenant:
                cospaces = cospaces.filter(tenant__tid=tenant)
            else:
                cospaces = cospaces.filter(tenant__isnull=True)

            for cospace in cospaces.select_related('tenant'):
                if cospace.tenant.tid != tenant:
                    continue
                if cospace.is_auto:
                    continue

                cur = {
                    'name': cospace.name,
                    'uri': '{}@{}'.format(cospace.uri, domain),
                    'id': None,
                }
                result.append(cur)

        if self.ldap.sync_address_book:
            from address.models import Group
            for g in Group.objects.filter(parent__isnull=True, customer=self.ldap.customer):
                for item in g.iter_items():
                    cur = {
                        'name': item.title,
                        'uri': item.sip or item.h323 or item.h323_e164,
                        'id': None,
                    }
                    result.append(cur)

        if self.ldap.sync_tms:
            rooms = self.ldap.sync_tms.get_api().get_phonebooks()
            for cospace in rooms:
                cur = {
                    'name': cospace['name'],
                    'uri': cospace['dialstring'],
                    'id': None,
                }
                result.append(cur)

        return result

    def get_syncer(self):

        syncer = LdapSyncer(self.get_valid(), self.data, {
            'ou': self.ldap.base_dn,
            'class': self.ldap.obj_class,
            'api': self.ldap.provider.get_api(self.ldap.customer),
            'default_domain': self.ldap.customer.get_provider().hostname,

        })
        return syncer

    def sync(self):

        syncer = self.get_syncer()

        logger.info('Start LDAP sync')
        self.data = syncer.sync()
        self.save()
        logger.info('Finished LDAP sync')

        return self.data


