import hashlib
import re
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.utils.encoding import force_bytes
from django.utils.timezone import now

from compressed_store.models import CompressedStoreManager, CompressStoreModel
from endpoint.models import Endpoint


class EndpointDataContentManager(CompressedStoreManager):

    def _get_create_kwargs(self, content, **kwargs):

        return {
            'hash': EndpointDataContent.get_hash(content),
            **kwargs,
        }


class EndpointDataFileBase(CompressStoreModel):

    log_type = 'endpoint_data'
    log_basename = 'endpoint_data'
    log_disable_archive = True

    @staticmethod
    def get_hash(content):
        return hashlib.md5(force_bytes(content)).hexdigest()

    def get_log_type(self):
        return 'endpoint_{}'.format(str(self.get_content_type_display()).lower())

    TYPES = (
        (0, 'configuration'),
        (1, 'status'),
        (2, 'command'),
        (3, 'valuespace'),

        (10, 'macros'),
        (11, 'panels'),
    )
    TYPES_MAP = {v: k for k, v in TYPES}

    content_type = models.SmallIntegerField(choices=TYPES)
    hash = models.CharField(max_length=64)

    # Don't reset endpoint_id on delete to allow for timescaledb-compression:
    endpoint = models.ForeignKey(
        Endpoint, on_delete=models.DO_NOTHING, null=True, db_constraint=False
    )

    objects = EndpointDataContentManager()

    class Meta:
        abstract = True

    @property
    def ts_update(self):
        return self.ts_created


class EndpointDataContent(EndpointDataFileBase):
    """Single state file content for latest version and manual backups"""



class EndpointDataFileManager(EndpointDataContentManager):

    def _get_create_kwargs(self, content, **kwargs):

        return {
            'hash': EndpointDataContent.get_hash(content),
            'hash_cleaned': EndpointDataContent.get_hash(EndpointDataFile.remove_changing_data(content)),
            **kwargs,
        }


class EndpointDataFile(EndpointDataFileBase):
    """Archive for previous endpoint file content"""

    parent = models.ForeignKey('self', null=True, on_delete=models.SET_NULL, db_constraint=False, db_index=False)
    hash_cleaned = models.CharField(max_length=64)

    ts_last_used = models.DateTimeField(null=True)
    reuse_count = models.IntegerField(null=True, default=None)

    objects = EndpointDataFileManager()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @staticmethod
    def remove_changing_data(content):
        "remove ever changing timestamps"
        bytes = force_bytes(content)
        bytes = re.sub(rb'>20[234]\d-\d\d-\d\d[ T][\d:\.+]+Z?<', b'>[date]<', bytes)
        bytes = re.sub(rb'<Uptime>\d+</Uptime>', b'<Uptime>0</Uptime>', bytes)
        bytes = re.sub(rb'<TestRunning>(True|False)</Uptime>', b'<TestRunning></TestRunning>', bytes)
        return bytes

    @staticmethod
    def get_cleaned_hash(content):
        return EndpointDataFile.get_hash(EndpointDataFile.remove_changing_data(content))

    @property
    def ts_update(self):
        return self.ts_last_used or self.ts_created

    class Meta:
        indexes = [
            models.Index(name='endpoint_datafile_last_used', fields=['ts_last_used'], condition=Q(ts_last_used__isnull=False)),
        ]


class EndpointCurrentStateManager(models.Manager):

    def store(self, endpoint, status=None, configuration=None, valuespace=None, command=None):
        state = EndpointCurrentState.objects.get_or_create(endpoint=endpoint)[0]

        if status is not None:
            state.set_data('status', status)
        if configuration is not None:
            state.set_data('configuration', configuration)
        if command is not None:
            state.set_data('command', command)
        if valuespace is not None:
            state.set_data('valuespace', valuespace)

        return state


class EndpointCurrentState(models.Model):
    """Latest endpoint file content"""
    endpoint = models.OneToOneField(Endpoint, on_delete=models.CASCADE, related_name='files')
    status = models.ForeignKey(
        'EndpointDataContent',
        null=True,
        db_index=False,
        db_constraint=False,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    configuration = models.ForeignKey(
        'EndpointDataContent',
        null=True,
        db_index=False,
        db_constraint=False,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    command = models.ForeignKey(
        'EndpointDataContent',
        null=True,
        db_index=False,
        db_constraint=False,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    valuespace = models.ForeignKey(
        'EndpointDataContent',
        null=True,
        db_index=False,
        db_constraint=False,
        on_delete=models.SET_NULL,
        related_name='+',
    )

    objects = EndpointCurrentStateManager()

    class Meta:
        db_table = 'endpoint_data_endpointcurrentstate_new'

    @transaction.atomic
    def set_data(self, key, content):

        def _get():
            try:
                return getattr(self, key)
            except EndpointDataContent.DoesNotExist:
                return None

        obj = _get()

        if not obj:
            EndpointCurrentState.objects.select_for_update(of=('self',)).get(pk=self.pk)
            obj = _get()

        if obj is None or obj.pk is None:  # removed + using timescale
            obj = EndpointDataContent.objects.store(content=content, content_type=EndpointDataContent.TYPES_MAP[key],
                                                         endpoint=self.endpoint)
        else:
            obj.content = content
            obj.ts_created = now()
            obj.save(update_fields=['content_compressed', 'ts_created'])

        setattr(self, key, obj)
        self.save(update_fields=[key])

        self.store_history(key, content)
        return obj

    def store_history(self, key, content):
        """Store a new copy if file is not already stored within the last day"""

        cleaned_hash = EndpointDataFile.get_cleaned_hash(content)

        try:
            existing = EndpointDataFile.objects.filter(
                endpoint=self.endpoint_id,
                content_type=EndpointDataFile.TYPES_MAP[key],
                ts_created__gt=now() - timedelta(days=1),
                hash_cleaned=cleaned_hash,
            ).order_by('-ts_created')[0]
        except IndexError:
            existing = None
        else:
            existing.ts_last_used = now()
            try:
                existing.save(update_fields=['ts_last_used'])
            except Exception:  # Ignore errors on updte, e.g. timescale compression read only-mode
                if settings.DEBUG or settings.TEST_MODE:
                    raise

        if existing:
            return

        parent = (
            EndpointDataFile.objects.filter(
                endpoint=self.endpoint_id,
                content_type=EndpointDataFile.TYPES_MAP[key],
                ts_created__gt=now() - timedelta(days=1),
            )
            .order_by('-ts_created')
            .first()
        )

        return EndpointDataFile.objects.store(
            content=content,
            content_type=EndpointDataFile.TYPES_MAP[key],
            parent=parent,
            endpoint=self.endpoint,
        )


class EndpointCurrentStateOld(models.Model):
    """Deprecated. Old version with data files stored in same table as archive."""
    # TODO Remove after 2022-01-01

    endpoint = models.OneToOneField(Endpoint, on_delete=models.CASCADE, related_name='+')
    status = models.ForeignKey('EndpointDataFile', null=True, db_constraint=False, on_delete=models.SET_NULL, related_name='+')
    configuration = models.ForeignKey('EndpointDataFile', null=True, db_constraint=False, on_delete=models.SET_NULL, related_name='+')
    command = models.ForeignKey('EndpointDataFile', null=True, db_constraint=False, on_delete=models.SET_NULL, related_name='+')
    valuespace = models.ForeignKey('EndpointDataFile', null=True, db_constraint=False, on_delete=models.SET_NULL, related_name='+')

    objects = EndpointCurrentStateManager()

    class Meta:
        db_table = 'endpoint_data_endpointcurrentstate'
