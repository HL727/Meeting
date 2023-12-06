import base64
import hashlib
import json
import zipfile
from datetime import datetime
from io import BytesIO
from collections import OrderedDict
from typing import List, TYPE_CHECKING, Tuple, Optional

from django.template.defaultfilters import date as format_date, slugify
from django.utils.timezone import now
from django.urls import reverse

from conferencecenter import settings
from django.utils.encoding import force_text

if TYPE_CHECKING:
    from roomcontrol.models import RoomControlFile


def get_files(
    files=None, controls=None, templates=None
) -> Tuple[List['RoomControlFile'], Optional[datetime]]:
    from roomcontrol.models import RoomControlFile

    all_files: List['RoomControlFile'] = []
    if files:
        all_files.extend(files)
    if controls:
        all_files.extend(RoomControlFile.objects.filter(control__in=controls))
    if templates:
        all_files.extend(RoomControlFile.objects.filter(control__templates__in=templates))

    last_ts = None

    for file in sorted(all_files, key=lambda f: f.pk):
        if file.name and file.content:
            last_ts = max(last_ts or file.ts_created, file.ts_last_update or file.ts_created)

    return sorted(all_files, key=lambda f: f.pk), last_ts


def generate_roomcontrol_zip(title, files=None, controls=None, templates=None):

    all_files, last_ts = get_files(files=files, controls=controls, templates=templates)

    b = BytesIO()
    zf = zipfile.ZipFile(b, "w")

    processed = set()
    for file in sorted(all_files, key=lambda f: f.pk):
        if file.pk in processed:  # TODO warn about name conflicts
            continue
        processed.add(file.pk)
        if file.name and file.content:
            last_ts = max(last_ts or file.ts_created, file.ts_last_update or file.ts_created)
            zf.writestr(
                zipfile.ZipInfo(filename=file.name, date_time=(file.ts_last_update or file.ts_created).timetuple()),
                file.content
            )

    zf.writestr(
                zipfile.ZipInfo(filename='manifest.json', date_time=(last_ts or now()).timetuple()),
                json.dumps(generate_roomcontrol_manifest(all_files, ts=last_ts), indent=2))
    zf.close()

    return '{}-{}.zip'.format(slugify(title), format_date(now(), 'Ymd-Hi')), b.getvalue()


def generate_roomcontrol_manifest(files=None, ts=None):
    result = {'macros': [], 'panels': []}

    for f in files:
        if f.extension == 'js':
            result['macros'].append({
                'payload': f.name,
                'type': 'zip',
                'id': f.label
            })
        if f.extension == 'xml':
            result['panels'].append({
                'payload': f.name,
                'type': 'zip',
                'id': f.label
            })

    datestr = format_date(ts or now(), 'Ymd-Hi')
    manifest = {
        'version': '1',
        'profile': {
            'macro': {
                'items': result['macros']
            },
            'roomcontrol': {
                'items': result['panels']
            }
        },
        'profileName': 'mividas-export-{}'.format(datestr),
        'generatedAt': datestr
    }

    return manifest


def generate_roomcontrol_commands(files=None, controls=None, templates=None):

    all_files, last_ts = get_files(files=files, controls=controls, templates=templates)

    macros = []
    activate = []
    panels = []

    for f in all_files:
        if f.extension == 'js':
            macros.append(
                {
                    'command': ['Macros', 'Macro', 'Save'],
                    'arguments': {
                        'Name': f.label,
                    },
                    'body': f.content,
                }
            )
            activate.append(
                {
                    'command': ['Macros', 'Macro', 'Activate'],
                    'arguments': {
                        'Name': f.label,
                    },
                }
            )
        elif f.extension == 'xml':
            panels.append(
                {
                    'command': ['UserInterface', 'Extensions', 'Panel', 'Save'],
                    'arguments': {
                        'PanelId': f.label,
                    },
                    'body': f.content,
                }
            )

    return macros, panels, activate


def b64encode_object_ids(objs):
    if not objs:
        return b''
    pks = sorted(obj.pk for obj in objs)
    return base64.b64encode(json.dumps(pks).encode())


def get_export_url_params(files=None, controls=None, templates=None, endpoint=None):
    url_files = b64encode_object_ids(files)
    url_controls = b64encode_object_ids(controls)
    url_templates = b64encode_object_ids(templates)
    url_endpoint = base64.b64encode(json.dumps(endpoint.pk).encode()) if endpoint else b''

    url_hash = hashlib.sha224(
        b''.join([settings.SECRET_KEY.encode(), url_files, url_controls, url_templates, url_endpoint])
    ).hexdigest()

    return OrderedDict((k, v) for k, v in [
        ('f', url_files),
        ('c', url_controls),
        ('t', url_templates),
        ('e', url_endpoint),
        ('k', url_hash),
    ] if v)


def get_export_url(customer, files=None, controls=None, templates=None, endpoint=None):
    from roomcontrol.models import RoomControlDownloadLink

    params = get_export_url_params(files=files, controls=controls, templates=templates, endpoint=endpoint)

    dl = RoomControlDownloadLink.objects.create(customer=customer,
                                                files=force_text(params.get('f','')),
                                                controls=force_text(params.get('c','')),
                                                templates=force_text(params.get('t', '')),
                                                endpoints=force_text(params.get('e', '')),
                                                hash=force_text(params.get('k', '')))

    export_url = '{}{}?dl={}'.format(settings.EPM_BASE_URL,
                                     reverse('roomcontrol-package'),
                                     dl.secret_key,
                                  )

    return export_url


