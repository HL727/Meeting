from django.db import models

# Create your models here.
from django.utils.text import slugify
from django.utils.timezone import localtime

from customer.models import Customer
from endpoint.models import Endpoint
from endpoint_data.models import EndpointDataContent


class EndpointBackup(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    endpoint = models.ForeignKey(Endpoint, on_delete=models.SET_NULL, null=True)
    endpoint_name = models.CharField(max_length=200)

    slug = models.SlugField()

    ts_created = models.DateTimeField(auto_now_add=True)
    ts_completed = models.DateTimeField(null=True)

    hash = models.CharField(max_length=128)

    error = models.TextField()
    file = models.FileField(upload_to='backup')

    configuration = models.ForeignKey(EndpointDataContent, null=True, blank=True, db_constraint=False, on_delete=models.SET_NULL, editable=False, related_name='+')
    status = models.ForeignKey(EndpointDataContent, null=True, blank=True, db_constraint=False, on_delete=models.SET_NULL, editable=False, related_name='+')
    macros = models.ForeignKey(EndpointDataContent, null=True, blank=True, db_constraint=False, on_delete=models.SET_NULL, editable=False, related_name='+')
    panels = models.ForeignKey(EndpointDataContent, null=True, blank=True, db_constraint=False, on_delete=models.SET_NULL, editable=False, related_name='+')

    def set_data(self, key, content):
        if key not in (v[1] for v in EndpointDataContent.TYPES):
            raise ValueError('Key {} not valid for content'.format(key))

        if content in (None, b'', ''):
            setattr(self, key, None)
            return

        content_type_value = {v: k for k, v in EndpointDataContent.TYPES}[key]

        setattr(self, key, EndpointDataContent.objects.store(content, content_type=content_type_value, endpoint=self.endpoint,
                                                             _log_type='endpoint_{}'.format(key)))

    def save(self, *args, **kwargs):
        if not self.endpoint_name:
            self.endpoint_name = str(self.endpoint)
        self.slug = '{}-{}'.format(slugify(self.endpoint_name)[:40], str(localtime()).split('.')[0])
        return super().save(*args, **kwargs)

    def restore(self):
        return self.endpoint.get_api().restore_backup(self)

    class Meta:
        ordering = ('-ts_created',)
