import re
from datetime import timedelta
from typing import Dict, Set, DefaultDict

from cachetools.func import ttl_cache
from django.db import models

# Create your models here.
from django.utils.encoding import force_bytes
from django.utils.timezone import now

from compressed_store.models import CompressStoreModel, CompressedStoreManager


class ActiveTraceLogManager(models.Manager['ActiveTraceLog']):
    @ttl_cache(ttl=10)
    def get_active(self) -> Dict[str, Set[int]]:
        result = DefaultDict[str, Set[int]](set)

        for active in ActiveTraceLog.objects.filter(ts_start__lte=now(), ts_stop__gte=now()):
            for k in ('cluster', 'provider', 'customer', 'endpoint'):
                if getattr(active, k):
                    result[k].add(getattr(active, k).pk)

            if active.everything:
                result['everything'].add(active.customer_id or 0)

        return dict(result)


def default_stop_time():
    return now() + timedelta(seconds=600)


class ActiveTraceLog(models.Model):

    cluster = models.ForeignKey(
        'provider.Cluster',
        db_index=False,
        db_constraint=False,
        blank=True,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )
    provider = models.ForeignKey(
        'provider.Provider',
        db_index=False,
        db_constraint=False,
        blank=True,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )
    customer = models.ForeignKey(
        'provider.Customer',
        db_index=False,
        db_constraint=False,
        blank=True,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )
    endpoint = models.ForeignKey(
        'endpoint.Endpoint',
        db_index=False,
        db_constraint=False,
        blank=True,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )
    user = models.CharField(max_length=250, blank=True, editable=False)

    everything = models.BooleanField(default=False, blank=True)

    ts_start = models.DateTimeField(default=now)
    ts_stop = models.DateTimeField(null=True, default=default_stop_time)
    ts_created = models.DateTimeField(default=now, editable=False)

    objects = ActiveTraceLogManager()

    def save(self, *args, **kwargs):
        if not self.ts_stop:
            self.ts_stop = self.ts_start + timedelta(seconds=600)
        super().save(*args, **kwargs)

    def __str__(self):
        return ', '.join('{}={}'.format(k, v) for k, v in self.get_active().items())

    @property
    def is_active(self) -> bool:
        return self.ts_start <= now() and self.ts_stop and self.ts_stop >= now()

    def get_active(self):
        result = {}
        for k in ('cluster', 'provider', 'customer', 'endpoint'):
            if getattr(self, k):
                result[k] = getattr(self, k)
        if self.everything:
            result['everything'] = True
        return result


class TraceLogManager(CompressedStoreManager['TraceLog']):
    def store(self, content, *args, **kwargs):
        if kwargs.get('url_base'):
            kwargs['url_base'] = str(kwargs['url_base'])[:250]

        content = self.redact(content)

        return super().store(content, *args, **kwargs)

    def redact(self, content):
        result = re.sub(
            rb'<([A-z]*Pass(word|phrase))>\s*[^<]+</\1>',
            rb'<\1>******</\1>',
            force_bytes(content),
        )

        result = re.sub(
            rb'"([A-z]*Pass(word|phrase))":\s*"[^"]+"',
            rb'"\1": "******"',
            result,
        )

        return result


class TraceLog(CompressStoreModel):

    log_type = 'trace_log'
    log_basename = 'trace_log'

    cluster = models.ForeignKey(
        'provider.Cluster',
        db_index=False,
        db_constraint=False,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )
    provider = models.ForeignKey(
        'provider.Provider',
        db_index=False,
        db_constraint=False,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )
    customer = models.ForeignKey(
        'provider.Customer',
        db_index=False,
        db_constraint=False,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )
    endpoint = models.ForeignKey(
        'endpoint.Endpoint',
        db_index=False,
        db_constraint=False,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )
    endpoint_task = models.ForeignKey(
        'endpoint_provision.EndpointTask',
        db_index=False,
        db_constraint=False,
        null=True,
        related_name='+',
        on_delete=models.DO_NOTHING,
    )

    method = models.CharField(max_length=250)
    url_base = models.CharField(max_length=250)

    objects = TraceLogManager()
