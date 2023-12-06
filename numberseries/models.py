from random import randint

from django.db import models, transaction

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _

import re


def get_next(last_number=None, prefix=None, suffix=None, default=None):

    content = last_number or ''

    if not last_number:
        if not default:
            default = '%04d' % 1

        content = '{}{}{}'.format(
            prefix, default, suffix)

        return content

    if prefix and content.startswith(prefix):
        content = content[len(prefix):]
    if suffix and content.endswith(suffix):
        content = content[:-len(suffix)]

    if not re.search(r'[0-9]', content):
        content = '0{}'.format(content)

    parts = content.split('-')

    found = False

    next_number = parts

    i = len(parts)
    for part in reversed(parts[:]):
        i -= 1
        if not part:
            continue

        m = re.findall(r'(\d+)', part)

        if not m:
            continue

        for number in reversed(m):
            if number == '9' * len(number):
                parts[i] = ('0' * len(number))[:len(number) - 1] + '1'
            else:
                increased = '%0{}d'.format(len(number)) % (int(number) + 1)

                found = True
                break

        if found:
            index = part.rindex(number)
            increased_part = part[:index] + \
                             increased + part[index + len(increased):]

            parts[i] = increased_part
            break
    else:
        raise ValueError('Couldnt get new number after %s' % content)

    return '{}{}{}'.format(
        prefix, '-'.join(next_number), suffix)


class NumberSeriesManager(models.Manager):

    def get_for(self, name, content_object=None):
        if content_object:
            return NumberSeries.objects.get_or_create(name=name, content_type=ContentType.objects.get_for_model(content_object),
                                              object_id=content_object.pk)[0]
        return NumberSeries.objects.get_or_create(name=name, object_id__isnull=True)[0]

    def get_next(self, name, content_object=None, prefix=None, suffix=None, default=''):
        series = self.get_for(name, content_object)

        return series.get_next(prefix=prefix, suffix=suffix, default=default)

    def use_next(self, name, content_object=None, prefix=None, suffix=None, default=''):
        series = self.get_for(name, content_object)

        return series.use_next(prefix=prefix, suffix=suffix, default=default)


class NumberSeries(models.Model):
    name = models.SlugField(_(u'Namn'))

    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    objects = NumberSeriesManager()

    class Meta:
        unique_together = ('name', 'content_type', 'object_id')

    def get_prefix(self, prefix=None, suffix=None, lock=False) -> 'NumberSeriesPrefix':

        if lock:
            with transaction.atomic():
                return NumberSeriesPrefix.objects.select_for_update().get_or_create(series=self, prefix=prefix or '',
                                                                                    suffix=suffix or '')[0]
        else:
            return NumberSeriesPrefix.objects.get_or_create(series=self, prefix=prefix or '',
                                                                                suffix=suffix or '')[0]

    def get_next(self, prefix=None, suffix=None, default=None):

        prefix = self.get_prefix(prefix=prefix, suffix=suffix)
        return prefix.get_next(default=default)

    def use_next(self, prefix=None, suffix=None, default=None):

        prefix = self.get_prefix(prefix=prefix, suffix=suffix)
        return prefix.use_next(default=default)


class NumberSeriesPrefix(models.Model):
    series = models.ForeignKey(NumberSeries, related_name='prefix', on_delete=models.CASCADE)

    prefix = models.CharField(max_length=10, db_index=True)
    suffix = models.CharField(max_length=10, db_index=True)

    last_number = models.CharField(max_length=64)

    class Meta:
        unique_together = ('series', 'prefix', 'suffix')

    def get_next(self, default=None):
        return get_next(self.last_number, self.prefix, self.suffix, default=default)

    @transaction.atomic()
    def use_next(self, default=None):

        latest = NumberSeriesPrefix.objects.select_for_update(of=('self',)).get(pk=self.pk)
        self.last_number = latest.last_number
        self.last_number = self.get_next(default=default)
        self.save()

        return self.last_number


class NumberRange(models.Model):

    title = models.CharField(max_length=100)
    start = models.PositiveIntegerField(default=100000000)
    stop = models.PositiveIntegerField(default=999999999)

    next_number = models.PositiveIntegerField(null=True, blank=True)

    is_dummy = False

    @transaction.atomic
    def use(self):
        locked = NumberRange.objects.select_for_update(of=('self',)).get(pk=self.pk)
        result = locked.next_number or self.start
        self.next_number = result + 1
        self.save()
        return result

    def random(self):
        return randint(self.start, self.stop)

    def __str__(self):
        return self.title


class NumberRangeDummy:

    cluster = None
    start = 10000000
    stop = 99999999
    next_number = start

    def __init__(self, next_number=None):
        self.next_number = next_number

    is_dummy = True

    def use(self):
        # TODO exception?
        if self.next_number:
            result = self.next_number
            self.next_number += 1
        else:
            result = self.__class__.next_number
            self.__class__.next_number += 1
        return result

    def random(self):
        return randint(self.start, self.stop)

    def save(self, *args, **kwargs):
        raise ValueError('Temporary range, no number range available')
