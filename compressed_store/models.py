import json
import os
import zlib

from django.conf import settings
from django.core.serializers import json as json_s
from django.db import models, connections
from django.utils.encoding import force_bytes, force_text
from django.utils.timezone import localtime


class CompressedContentMixin:

    @classmethod
    def _compress(cls, content, content_type=None, extra=False):
        if not content:
            return b''
        dict_id = b'0'

        content = force_bytes(content, encoding='utf-8')
        compressed = zlib.compress(content)

        if len(compressed) > len(content) - max(len(content) * .10, 50):
            compressed = content
            dict_id = b'1'

        return dict_id + compressed

    @classmethod
    def _decompress(cls, content, content_type=None, extra=False):
        if not content:
            return b''
        dict_id = bytes(content[:1]) if content else b''
        if dict_id == b'1':  # uncompressed
            return bytes(content[1:])

        return bytes(zlib.decompress(content[1:]))

    @staticmethod
    def _get_compress_obj(content_type=None, extra=False):
        return zlib.compressobj()

    @staticmethod
    def _get_decompress_obj(content_type=None, extra=False):
        return zlib.decompressobj()


class FastCountQuerySet(models.QuerySet):
    """Use inexact row counts for large tables"""

    def count(self):

        if 'postgres' not in settings.DATABASES['default']['ENGINE']:
            return super().count()

        if self._result_cache is not None:
            return len(self._result_cache)

        query = self.query
        if not (query.group_by or query.where or query.distinct):
            cursor = connections[self.db].cursor()
            cursor.execute('SELECT reltuples FROM pg_class WHERE relname = %s', [self.query.model._meta.db_table])
            n = int(cursor.fetchone()[0])
            if n >= 5000:
                return n  # exact count for small tables
            else:
                return self.query.get_count(using=self.db)
        else:
            return self.query.get_count(using=self.db)


class FastCountManager(models.Manager):

    def get_queryset(self):
        return FastCountQuerySet(model=self.model, using=self.db, hints=self._hints)


class CompressedStoreManager(FastCountManager, CompressedContentMixin, models.Manager):

    def _get_create_kwargs(self, content, **kwargs):
        return kwargs

    def _split_extra(self, **data):

        extra = {}
        for extra_field in set(data.keys()) - {f.name for f in self.model._meta.get_fields()}:
            extra[extra_field] = data.pop(extra_field)

        return data, extra

    def store(self, content, ts_created=None, _log_type=None, **kwargs):

        data, extra = self._split_extra(
            ts_created=ts_created or localtime(),
            **self._get_create_kwargs(content, **kwargs))

        obj = self.model(**data)
        obj.content = content  # enable self.get_log_type() with access to content
        obj.extra = extra
        obj.save(force_insert=True)
        return obj

    def _get_archive_qs(self, ts_start=None, ts_stop=None, qs=None):
        if (ts_start, ts_stop, qs) == (None, None, None):
            raise ValueError('Filter is required')

        if qs:
            return qs

        ts_stop = min(ts_stop, localtime())

        qs = self.filter(ts_created__lte=ts_stop)
        if ts_start:
            qs = qs.filter(ts_created__gte=ts_start)

        return qs

    def archive(self, ts_stop, output_dir=None, ts_start=None, clean=False):

        last = None
        fd = None

        objects = self._get_archive_qs(ts_start=ts_start, ts_stop=ts_stop)

        model = self.model
        basename = model.log_basename

        if model.log_disable_archive:
            raise ValueError('Archive is disabled for {}!'.format(model.__class__.__name__))

        if not output_dir:
            output_dir = settings.LOG_DIR

        if not os.path.exists(output_dir):
            os.mkdir(output_dir)

        serializer = json_s.DjangoJSONEncoder()

        def _get_fd(cur_date):
            from .utils import get_compressed_fd
            nonlocal fd
            _close_fd()
            return get_compressed_fd(basename, cur_date, output_dir=output_dir)

        def _close_fd():
            if not fd:
                return
            compress_obj.flush()
            fd.close()

        compress_obj = self._get_compress_obj()

        for obj in objects.order_by('ts_created').iterator():
            date = obj.ts_created.date()
            if date != last:
                fd = _get_fd(date)
                last = date

            fd.write(serializer.encode({
                    **(obj.extra or {}),
                    'ts': obj.ts_created.isoformat(),
                    'content': obj.content.decode('utf-8'),
                }).encode('utf-8')
             )

        _close_fd()

        if clean:
            self.clean(qs=objects)

    def clean(self, ts_start=None, ts_stop=None, qs=None):

        objects = self._get_archive_qs(ts_start=ts_start, ts_stop=ts_stop, qs=qs)
        return objects.delete()

    def search(self, find_str, ts_start=None, ts_stop=None):

        if not find_str:
            return []

        qs = self.all()

        if ts_start:
            qs = qs.filter(ts_created__gte=ts_start)
        if ts_stop:
            qs = qs.filter(ts_created__lte=ts_stop)

        result = []

        find_bytes = force_bytes(find_str)

        for log in qs:
            if find_bytes in log.content:
                result.append(log)
        return result


class CompressStoreModel(CompressedContentMixin, models.Model):

    log_type = 'generic'
    log_basename = 'generic'
    log_disable_archive = False

    def get_log_type(self):
        "support for in place updates of object content. must be passed as _log_type=<type> to store()"
        return self.log_type

    _content = None
    _content_json = None
    _extra = None

    ts_created = models.DateTimeField(default=localtime, db_index=True)
    content_compressed = models.BinaryField()
    extra_compressed = models.BinaryField(null=True)

    objects: models.Manager = CompressedStoreManager()

    def as_dict(self):
        return {
            **(self.extra or {}),
            'ts_created': self.ts_created,
            'content': self.content,
        }

    @staticmethod
    def clean_content(content):
        return force_bytes(content)

    @property
    def content(self):
        if not self._content and self.content_compressed:
            self._content = self._decompress(self.content_compressed, content_type=self.get_log_type())
        return self._content

    @content.setter
    def content(self, value):
        self.content_compressed = self._compress(self.clean_content(value), content_type=self.get_log_type())
        self._content = None

    @property
    def content_text(self):
        if self.content is None:
            return None
        return force_text(self.content)

    @property
    def content_json(self):
        if not self._content_json and self.content:
            self._content_json = json.loads(self.content_text)
        return self._content_json

    @property
    def extra(self):
        if not self._extra and self.extra_compressed:
            self._extra = json.loads(force_text(self._decompress(self.extra_compressed,
                                                      content_type=self.get_log_type(), extra=True)))
        return self._extra

    @extra.setter
    def extra(self, value):
        serializer = json_s.DjangoJSONEncoder()

        self.extra_compressed = self._compress(force_bytes(serializer.encode(value)),
                                               content_type=self.get_log_type(), extra=True)
        self._extra = None

    class Meta:
        abstract = True
