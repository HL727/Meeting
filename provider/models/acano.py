from django.db import models
from django.urls import reverse
from django.utils.timezone import now

from customer.models import Customer
from .utils import new_secret_key
from .provider import Cluster, Provider
from django.utils.translation import ugettext_lazy as _


class AcanoClusterManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(type=Provider.TYPES.acano_cluster)


class AcanoCluster(Cluster):

    clear_chat_interval = models.SmallIntegerField(
        _('Töm chatt x minuter efter samtalsslut'),
        null=True,
        blank=True,
        help_text=_('Gäller endast CMS innan v3.0'),
    )
    set_call_id_as_uri = models.BooleanField(
        _('Sätt Call ID som uri eller secondary_uri'),
        default=False,
        help_text=_(
            'Uppdatera rum så att de alltid går att ringa via SIP via rumsnummer även om användare skapat dem manuellt'
        ),
    )

    def save(self, *args, **kwargs):
        self.type = Cluster.TYPES.acano_cluster
        super().save(*args, **kwargs)


class CoSpace(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    secret_key = models.CharField(default=new_secret_key, max_length=48, editable=False)

    title = models.CharField(max_length=100)
    uri = models.CharField(max_length=100)
    call_id = models.CharField(_('Call ID'), max_length=50, blank=True)
    secret = models.CharField(_('Secret'), max_length=50, blank=True, editable=False)
    creator = models.CharField(max_length=80)
    group = models.CharField(max_length=100, blank=True)
    force_encryption = models.BooleanField(default=False)
    disable_chat = models.BooleanField(default=False)

    owner_email = models.EmailField(blank=True, editable=False, default='')

    call_leg_profile = models.CharField(max_length=100, blank=True)
    call_profile = models.CharField(max_length=100, blank=True)

    provider_ref = models.CharField(max_length=128, blank=True)
    moderator_password = models.CharField(_('Lösenord'), max_length=50, blank=True)
    lobby = models.BooleanField(default=False)
    activation_ref = models.CharField(max_length=128, blank=True)
    moderator_ref = models.CharField(max_length=128, blank=True)

    ts_auto_remove = models.DateTimeField(_('Radera efter tidpunkt'), blank=True, null=True)

    @property
    def id_key(self):
        return '%s-%s' % (self.pk, self.secret_key)

    def get_api_url(self):
        return reverse('api_cospace', args=[self.id_key])

    @property
    def join_url(self):

        api = self.customer.get_api()
        return api.get_web_url(self.call_id, secret=self.secret)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.schedule_remove()

    def schedule_remove(self):
        from provider import tasks

        if not self.ts_auto_remove:
            return
        tasks.remove_schedule_cospace.apply_async(
            [self.pk, self.ts_auto_remove.isoformat()], eta=self.ts_auto_remove
        )


class CoSpaceAccessMethod(models.Model):

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    cospace_id = models.CharField(max_length=64)

    provider_ref = models.CharField('call id', max_length=64)
    provider_ref2 = models.CharField('accessmethod id', max_length=64)

    system_id = models.CharField(max_length=100, null=True)

    ts_created = models.DateTimeField(default=now, editable=False)
    is_virtual = models.BooleanField(default=False, blank=True)

    provider_secret = models.CharField(max_length=64, blank=True)
    password = models.CharField(max_length=64, blank=True)

    class Meta:
        unique_together = ('provider', 'cospace_id', 'system_id')
