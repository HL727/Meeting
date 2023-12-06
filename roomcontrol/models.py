import hashlib
import os
import re

import xml.etree.ElementTree as ET
import zipfile
from collections import OrderedDict

from defusedxml.cElementTree import fromstring as saft_xml_fromstring

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.encoding import force_text
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from compressed_store.models import CompressStoreModel, CompressedStoreManager
from customer.models import Customer
from roomcontrol.export import generate_roomcontrol_manifest, generate_roomcontrol_zip, get_export_url


class RoomControlFileManager(models.Manager):
    def create(self, *args, **kwargs):
        return super().create(*args, **kwargs)

    def validate_size(self, size, filename=None):
        if size > 2 * 1024 * 1024:
            raise ValidationError(_('File size too large, max 2MB {}').format(filename if filename else '').strip())

    def validate_files(self, files):
        result = []

        for file in files:
            ext = file.name.rsplit('.')[-1].lower()
            if ext == 'zip':
                cur = self.validate_zip_files(file)
                if not cur:
                    raise ValidationError('No xml/js-files found in zip')
                result.extend(cur)
            elif ext == 'xml':
                self.validate_size(file.size, file.name)
                result.extend(self.validate_panel_xml(file.read()))
            elif ext == 'js':
                self.validate_size(file.size, file.name)
                result.append((os.path.basename(file.name), file.read()))
            else:
                raise ValidationError('Only zip, xml and js-files allowed')

        return result

    def validate_zip_files(self, file):

        result = []
        zf = zipfile.ZipFile(file)
        for file_name in zf.namelist():
            ext = file_name.rsplit('.')[-1].lower()
            self.validate_size(zf.getinfo(file_name).file_size)
            if ext in ['xml', 'js']:
                result.append((os.path.basename(file_name), zf.open(file_name).read()))

        return result

    def validate_panel_xml(self, xml_content):

        try:
            xml_root = saft_xml_fromstring(xml_content)
        except Exception:
            raise ValueError('Invalid XML')

        result = []

        for panel in xml_root.findall('./Panel'):
            panel_id = panel.findtext('./PanelId')
            filename = '{}.xml'.format(panel_id)

            new_xml = ET.Element('Extensions')
            new_xml.insert(0, panel)

            content = ET.tostring(new_xml, encoding='utf8').decode('utf8')

            result.append((filename, content))
        return result


class RoomControlFile(models.Model):
    control = models.ForeignKey('RoomControl', related_name='files', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    content = models.TextField(default='')

    ts_created = models.DateTimeField(default=now)
    ts_last_update = models.DateTimeField(null=True, blank=True)

    objects = RoomControlFileManager()

    @property
    def label(self):
        return self.name.rsplit('.', 1)[0]

    @property
    def extension(self):
        return self.name.rsplit('.')[-1].lower()

    def save(self, *args, **kwargs):
        if self.ts_created:
            self.ts_last_update = now()
        super().save(*args, **kwargs)


class RoomControl(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    title = models.CharField(_('Rubrik'), max_length=100, blank=True)
    prefix = models.CharField(_('Prefix'), max_length=100, blank=True)
    description = models.TextField(blank=True, max_length=500)

    endpoints = models.ManyToManyField('endpoint.Endpoint', blank=True,
                                       through='EndpointRoomControlConnection',
                                       related_name='room_controls')

    ts_created = models.DateTimeField(auto_now_add=True)
    ts_last_update = models.DateTimeField(null=True, blank=True)

    features_call_end = models.BooleanField(null=True, blank=True)
    features_call_keypad = models.BooleanField(null=True, blank=True)
    features_call_join_webex = models.BooleanField(null=True, blank=True)
    features_call_mid_call_controls = models.BooleanField(null=True, blank=True)
    features_call_start = models.BooleanField(null=True, blank=True)
    features_call_videomute = models.BooleanField(null=True, blank=True)
    features_whiteboard_start = models.BooleanField(null=True, blank=True)
    features_share_start = models.BooleanField(null=True, blank=True)

    features_hide_all = models.BooleanField(null=True, blank=True)

    def get_feature_configuration(self, clear=False):

        result = []

        for attr, name in {
            'features_call_end': 'Call End',
            'features_call_keypad': 'Call KeyPad',
            'features_call_join_webex': 'Call JoinWebex',
            'features_call_mid_call_controls': 'Call MidCallControls',
            'features_call_start': 'Call Start',
            'features_call_videomute': 'Call VideoMute',
            'features_share_start': 'Share Start',
            'features_whiteboard_start': 'Whiteboard Start',
        }.items():
            value = getattr(self, attr)
            if value is None:
                continue
            cur = {
                'key': 'UserInterface Features {}'.format(name).split(),
                'value': 'Auto' if value else 'Hidden',
            }
            result.append(cur)

        if clear:
            result = [{**r, 'value': 'Auto'} for r in result]

        if self.features_hide_all is not None:
            result.append({
                'key': 'UserInterface Features HideAll'.split(),
                'value': 'True' if self.features_hide_all and not clear else 'False',
            })

        return result

    def get_next_filename(self, filename):
        existing_files = [f.name for f in self.files.all()]

        file_index = 0
        fn, ext = os.path.splitext(filename)
        while filename in existing_files:
            file_index += 1
            filename = '{}_{}{}'.format(fn, file_index, ext)

        return filename

    def add_file(self, filename, content):

        try:
            basename, ext = os.path.basename(filename).rsplit('.', 1)
        except ValueError:
            raise ValidationError('Only xml and js files allowed')

        basename = re.sub(r'[^A-z_0-9-]+', '_', basename)  # remove invalid characters

        if ext.lower() in ('xml', 'js'):
            RoomControlFile.objects.update_or_create(control=self, name='{}.{}'.format(basename, ext), content=force_text(content))
        else:
            raise ValidationError('Only xml and js files allowed')

    def get_detail_url(self):
        return reverse('roomcontrol-detail', args=[self.pk])

    def get_export_url(self):
        return reverse('roomcontrol-export', args=[self.pk])

    def get_package_url(self):
        return get_export_url(customer=self.customer, controls=[self])

    def get_zip_content(self, files=None):
        return generate_roomcontrol_zip(self.title, files)

    def get_zip_manifest(self, files=None):
        if not files:
            files = self.files.all()

        return generate_roomcontrol_manifest(files)

    def save(self, *args, **kwargs):
        if self.ts_created:
            self.ts_last_update = now()
        super().save(*args, **kwargs)

    def export_zip_all(self):
        filename, data = generate_roomcontrol_zip('archive', controls=[self])

        RoomControlZipExport.objects.store(control=self, content=data)
        for template in RoomControlTemplate.objects.filter(controls=self):
            RoomControlZipExport.objects.store(template=template, content=data)


class RoomControlTemplate(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    title = models.CharField(_('Rubrik'), max_length=100, blank=True)
    description = models.TextField(blank=True, max_length=500)

    controls = models.ManyToManyField(RoomControl, blank=True, related_name='templates')
    endpoints = models.ManyToManyField('endpoint.Endpoint', blank=True,
                                       through='EndpointRoomControlTemplateConnection',
                                       related_name='room_control_templates')

    ts_created = models.DateTimeField(auto_now_add=True)
    ts_last_update = models.DateTimeField(null=True, blank=True)

    @property
    def files(self):
        return RoomControlFile.objects.filter(control__in=self.controls.values_list('pk'))

    def get_zip_content(self):
        return generate_roomcontrol_zip(self.title, self.files)

    def get_export_url(self):
        return get_export_url(customer=self.customer, templates=[self])

    def get_package_url(self):
        return get_export_url(customer=self.customer, templates=[self])

    def save(self, *args, **kwargs):
        if self.ts_created:
            self.ts_last_update = now()
        super().save(*args, **kwargs)


class EndpointRoomControlConnection(models.Model):

    endpoint = models.ForeignKey('endpoint.Endpoint', on_delete=models.CASCADE)
    control = models.ForeignKey(RoomControl, on_delete=models.CASCADE)


class EndpointRoomControlTemplateConnection(models.Model):

    endpoint = models.ForeignKey('endpoint.Endpoint', on_delete=models.CASCADE)
    template = models.ForeignKey(RoomControlTemplate, on_delete=models.CASCADE)


def new_secret_key():

    try:
        import secrets
        return secrets.token_urlsafe(30)
    except ImportError:
        import uuid
        return str(uuid.uuid4())


class RoomControlDownloadLink(models.Model):
    "Temp model to bypass 128 char length for URL with old url-based packager"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    ts_created = models.DateTimeField(default=now)
    files = models.CharField(max_length=255)
    controls = models.CharField(max_length=255)
    templates = models.CharField(max_length=255)
    endpoints = models.CharField(max_length=255)
    hash = models.CharField(max_length=255)

    secret_key = models.CharField(max_length=255, unique=True, default=new_secret_key, db_index=True)

    def serialize_url_params(self):
        return OrderedDict((k, v) for k, v in [
            ('f', self.files),
            ('c', self.controls),
            ('t', self.templates),
            ('e', self.endpoints),
            ('k', self.hash),
        ] if v)

class RoomControlZipExportManager(CompressedStoreManager):

    def _get_create_kwargs(self, content, **kwargs):
        if 'checksum' in kwargs:
            return kwargs
        checksum = hashlib.sha512(content).hexdigest()
        return {**kwargs, 'checksum': checksum}


class RoomControlZipExport(CompressStoreModel):

    control = models.ForeignKey(RoomControl, null=True, on_delete=models.CASCADE)
    template = models.ForeignKey(RoomControlTemplate, null=True, on_delete=models.CASCADE)
    checksum = models.CharField(max_length=128, db_index=True)

    secret_key = models.CharField(max_length=255, unique=True, default=new_secret_key)

    objects = RoomControlZipExportManager()

    def save(self, *args, **kwargs):
        if not self.secret_key:
            self.secret_key = new_secret_key()
        super().save(*args, **kwargs)
