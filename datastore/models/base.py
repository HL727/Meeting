from datetime import timedelta

from cacheout import fifo_memoize
from django.db import models
from django.utils.timezone import now

from provider.models.provider import Provider


class ProviderSync(models.Model):

    provider = models.OneToOneField(Provider, on_delete=models.CASCADE)

    last_full_sync = models.DateTimeField(null=True)
    last_incremental_sync = models.DateTimeField(null=True)

    users_last_sync = models.DateTimeField(null=True)
    cospaces_last_sync = models.DateTimeField(null=True)
    tenants_last_sync = models.DateTimeField(null=True)
    themes_last_sync = models.DateTimeField(null=True)
    automatic_participants_last_sync = models.DateTimeField(null=True)
    aliases_last_sync = models.DateTimeField(null=True)

    @staticmethod
    @fifo_memoize(ttl=10)
    def check_has_cached_values(cluster_id):
        last_sync = ProviderSync.objects.filter(provider=cluster_id).values_list('cospaces_last_sync', flat=True).first()
        if last_sync and last_sync > now() - timedelta(hours=3):
            return True
        return False

    def save(self, *args, **kwargs):
        ProviderSync.check_has_cached_values.cache.clear()
        super().save(*args, **kwargs)
