from django.conf import settings
from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils.timezone import now


class LicenseManager(models.Manager['License']):
    def get_active(self, lock=False):

        if lock:
            manager = License.objects.select_for_update(of=('self',))
        else:
            manager = License.objects

        try:
            license, _created = manager.get_or_create(active=True)
        except Exception:
            license = manager.filter(active=True)[0]
            manager.filter(active=True).exclude(pk=license.pk).update(active=False)

        return license

    @transaction.atomic
    def sync_active(self, value: str):
        license = self.get_active(lock=True)
        if license.value != value:
            license.active = False
            license.save()
            license, created = License.objects.get_or_create(active=True, value=value)

        return license

    def sync_from_settings(self):
        if settings.LICENSE.value:
            return self.sync_active(settings.LICENSE.value)
        return self.get_active()


class License(models.Model):

    active = models.BooleanField(default=False)
    ts_created = models.DateTimeField(default=now)
    value = models.TextField()

    objects = LicenseManager()

    @cached_property
    def validator(self):
        from license.validator import LicenseValidator

        return LicenseValidator(self.value)
