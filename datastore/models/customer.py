from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now
from jsonfield import JSONField

from provider.models.provider import Provider
from shared.utils import partial_update


def no_empty(tenant_id):
    if not tenant_id:
        raise ValidationError('Tenant ID must not be empty')


class Tenant(models.Model):

    tid = models.CharField(max_length=100, db_index=True, validators=[no_empty])
    name = models.CharField(max_length=100)

    attributes = JSONField(null=True, blank=True, default='{}')

    is_active = models.BooleanField(null=True, default=True)
    last_synced = models.DateTimeField(default=now)

    last_count_change = models.DateTimeField(null=True)
    cospace_count = models.IntegerField(null=True)
    user_count = models.IntegerField(null=True)

    provider = models.ForeignKey(Provider, related_name='datastore_tenants', on_delete=models.CASCADE)

    def to_dict(self):
        return {
            **(self.attributes or {}),
            'id': self.tid,
            'name': self.name,
        }

    def set_updated(self):
        if self.last_count_change and (now() - self.last_count_change) < timedelta(hours=1):
            return

        partial_update(self, {'last_count_change': now()})

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('tid', 'provider')
