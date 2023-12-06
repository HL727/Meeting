from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
from customer.models import Customer
from statistics.parser.utils import clean_target
from django.utils.translation import gettext_lazy as _


class CustomerPermission(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, help_text=_('Fungerar bara för kunder med tenant'), on_delete=models.CASCADE)


class DialoutHistoryManager(models.Manager):

    def add(self, user, uri, name=None):

        uri = clean_target(uri)

        existing = DialoutHistory.objects.filter(uri=uri, user=user)
        if name:
            changed = existing.update(ts_used=now(), name=name)
        else:
            changed = existing.update(ts_used=now())

        if not changed:
            DialoutHistory.objects.create(user=user, uri=uri, name=name or '')

        return True

class DialoutHistory(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    uri = models.CharField(max_length=100)
    ts_used = models.DateTimeField(auto_now=True)

    objects = DialoutHistoryManager()

    class Meta:
        ordering = ('-ts_used',)

