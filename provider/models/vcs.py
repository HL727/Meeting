import reversion
from django.db import models
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from customer.models import Customer
from provider.models.provider import Provider, Q


from .provider import Cluster
from ..types import ProviderAPICompatible


class VCSClusterManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(type=Provider.TYPES.vcs_cluster)


class VCSCluster(Cluster):

    objects = VCSClusterManager()

    def save(self, *args, **kwargs):
        self.type = Cluster.TYPES.vcs_cluster
        super().save(*args, **kwargs)


class VCSEProviderManager(models.Manager):

    def filter_for_customer(self, customer):
        return self.filter_for_customers([customer])

    def filter_for_customers(self, customers):
        return self.filter(Q(customer__in=customers) | Q(customer__isnull=True))

    def filter_for_user(self, user):
        if user.is_staff:
            return self.all()

        customers = user.customerpermission_set.all().values_list('customer', flat=True)
        if customers:
            return self.filter(customer__in=customers)
        return self.filter(customer__isnull=True)


@reversion.register
class VCSEProvider(ProviderAPICompatible, models.Model):

    title = models.CharField(_('Beskrivning'), max_length=50)
    hostname = models.CharField(_('DNS-namn'), max_length=100, blank=True)
    ip = models.CharField(_('IP'), max_length=100, blank=True)

    api_host = models.CharField(_('Ev. separat api-ip/host'), max_length=100, blank=True)
    verify_certificate = models.BooleanField(
        _('Verifiera SSL-certifikat'),
        blank=True,
        default=False,
        help_text=_('Använd fullständigt domännamn som matchar serverns certifikat'),
    )

    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL)

    default_domain = models.CharField(_('Standarddomän för videoadresser'), max_length=100, blank=True)

    username = models.CharField(_('Användarnamn'), max_length=50, blank=True)
    password = models.CharField(_('Lösenord'), max_length=50, blank=True)

    cluster = models.ForeignKey(Cluster, blank=True, null=True, on_delete=models.SET_NULL)

    session_id = models.TextField(blank=True, editable=False)
    session_expires = models.DateTimeField(blank=True, null=True, editable=False)

    software_version = models.CharField(max_length=100, editable=False, default='')

    cdr_active = models.BooleanField(default=True, help_text='Maintenance > Logging > Call Data Records = "Service only"')

    objects = VCSEProviderManager()

    is_cluster = False

    def __str__(self):
        return self.title

    @property
    def api(self):
        return self.get_api(None)

    @property
    def has_session(self):
        return self.session_id and self.session_expires > now()

    def get_api(self, customer=None):
        from provider.ext_api.vcse import VCSExpresswayAPI
        return VCSExpresswayAPI(provider=self, customer=customer or self.customer)

    def get_clustered(self, include_self=True, only_call_bridges=True):

        result = {
            self.pk: self,
        }

        if self.cluster_id:
            cluster = self.cluster
            clustered = {p.pk: p for p in VCSEProvider.objects.filter(cluster=self.cluster_id)}
            for c in clustered.values():
                c.cluster = cluster
            result.update(clustered)

        if not include_self:
            result.pop(self.pk, None)

        return list(result.values())

    def save(self, *args, **kwargs):

        if not self.cluster_id:
            self.cluster = self.create_cluster()

        super().save(*args, **kwargs)

    def create_cluster(self):
        return VCSCluster.objects.create(title='VCS Cluster')

    class Meta:
        verbose_name = 'VCS'
        verbose_name_plural = 'VCSer'
