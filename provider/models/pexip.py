import uuid
from datetime import timedelta

from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField
from mptt.fields import TreeForeignKey

from .provider import Cluster, Provider, ClusterManager


class PexipClusterManager(ClusterManager):

    def get_queryset(self):
        return super(ClusterManager, self).get_queryset().filter(type=Provider.TYPES.pexip_cluster)


class PexipCluster(Cluster):

    default_customer = models.ForeignKey('provider.Customer', null=True, blank=True,
                                         on_delete=models.SET_NULL,
                                         related_name='pexip_default')

    system_objects_data = JSONField(editable=False)

    def should_refresh_system_objects(self):

        if not self.system_objects_data:
            return True

        ts = self.system_objects_data.get('ts')
        if not ts:
            return True

        if ts > (now() - timedelta(seconds=30)).isoformat():
            return False

        return True

    def update_system_objects(self, data):
        self.system_objects_data = {
            **self.system_objects_data,
            **data,
            'ts': now().isoformat(),
        }

        from policy_rule.models import PolicyRule
        for location in (data.get('system_location') or []):  # update cached location names for faster lookup
            PolicyRule.objects.filter(cluster=self.cluster,
                                      match_source_location=location['id']
                                      ).update(match_source_location_name=location['name'])

        self.save(update_fields=['system_objects_data'])

    def save(self, *args, **kwargs):
        self.type = Cluster.TYPES.pexip_cluster
        super().save(*args, **kwargs)

    objects = PexipClusterManager()


class PexipSpace(models.Model):
    "Store overrides/everything not synced from server"

    cluster = models.ForeignKey(Provider, on_delete=models.CASCADE)
    external_id = models.IntegerField(null=True)
    name = models.CharField(max_length=250)
    call_id = models.IntegerField(null=True)
    guid = models.UUIDField(default=uuid.uuid4)
    is_virtual = models.BooleanField(null=True, default=False, editable=False)
    customer = models.ForeignKey('provider.Customer', null=True, blank=True, on_delete=models.SET_NULL)

    organization_unit = TreeForeignKey('organization.OrganizationUnit', null=True, blank=True, on_delete=models.SET_NULL)

    ts_auto_remove = models.DateTimeField(_('Radera efter tidpunkt'), blank=True, null=True)

    class Meta:
        unique_together = ('cluster', 'external_id')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.schedule_remove()

    def schedule_remove(self):
        if not self.ts_auto_remove:
            return

        from provider import tasks

        tasks.remove_schedule_pexip_cospace.apply_async(
            [self.pk, self.ts_auto_remove.isoformat()], eta=self.ts_auto_remove
        )


class PexipEndUser(models.Model):
    "Store overrides/everything not synced from server"

    cluster = models.ForeignKey(Provider, on_delete=models.CASCADE)
    external_id = models.IntegerField()
    guid = models.UUIDField(default=uuid.uuid4)
    customer = models.ForeignKey('provider.Customer', null=True, blank=True, on_delete=models.SET_NULL)

    organization_unit = TreeForeignKey('organization.OrganizationUnit', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ('cluster', 'external_id')


def clear_cache(sender=None, **kwargs):
    from customer.models import Customer
    Customer.get_cluster_default_customer.cache.clear()


models.signals.post_save.connect(clear_cache, sender=PexipCluster)
