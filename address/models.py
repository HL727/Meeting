import re
from collections import defaultdict
from datetime import date
from typing import Tuple, List, Union
from xml.etree.ElementTree import ParseError

from django.utils.translation import gettext_lazy as _

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.timezone import now
from mptt.managers import TreeManager
from sentry_sdk import capture_exception

from provider.exceptions import ResponseError, AuthenticationError, ResponseConnectionError
from customer.models import Customer
from mptt.models import MPTTModel, TreeForeignKey

from shared.exceptions import format_exception
from shared.serializers import ExcelCreateFileSerializer
from shared.utils import (
    maybe_update_or_create,
    maybe_update,
    partial_update,
    partial_update_or_create,
)


def new_key():
    import uuid
    return str(uuid.uuid4().hex)


class AddressBook(models.Model):

    TYPES = (
        (0, _('Mividas Addressbook')),
        (1, _('External')),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    title = models.CharField(_('Namn'), max_length=255)

    external_url = models.CharField('URL', blank=True, max_length=200)
    external_edit_url = models.CharField(_('URL för redigering'), blank=True, max_length=200)

    type = models.SmallIntegerField(default=0, choices=TYPES)

    secret_key = models.CharField(max_length=64, unique=True, default=new_key)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.secret_key:
            self.secret_key = new_key()

        super().save(*args, **kwargs)
        try:
            ManualSource.objects.get_or_create(address_book=self)
        except Exception:
            pass

    @property
    def is_external(self):
        return self.type == 1

    is_syncing = False

    def sync(self):

        source_types = [
            CMSUserSource,
            CMSCoSpaceSource,
            TMSSource,
            SeeviaSource,
            EPMSource,
            VCSSource,
            ManualLinkSource,
        ]
        self.is_syncing = True
        # TODO sort by last_sync
        for model in source_types:
            for source in model.objects.filter(address_book=self):
                self.sync_source(source)
                self.try_merge_groups()
        self.try_merge_groups()
        self.is_syncing = False

    def sync_source(self, source: 'Source'):
        if source.prefix:
            group = Group.objects.get_or_create_by_path(
                None,
                source.prefix,
                address_book=self,
                source=source,
            )[0]
        else:
            group = Group.objects.get_or_create(
                address_book=self, source=source, parent=None, defaults=dict(title=source.prefix)
            )[0]

        try:
            if source.nested_items:
                root, children, items = source.get_items()
            else:
                items = source.get_items()
                children = []

            self._sync_item_recursive(group, children, items)
        except (ResponseError, AuthenticationError, ParseError) as e:
            source.sync_errors = format_exception(e)
        except Exception as e:
            capture_exception()
            source.sync_errors = format_exception(e)
        else:
            source.sync_errors = ''

        source.last_sync = now()
        source.save()

    def _sync_item_recursive(self, to_group, sub_group_items, items, flatten_groups=False, delete_other=True):

        valid_items = set()
        valid_groups = {to_group.pk}

        existing_group_map = {g.external_id_str: g for g in Group.objects.filter(address_book=self, source=to_group.source)}

        def _recurse(group, children, items):

            for item in items:

                if not any([item.get('sip'), item.get('h323'), item.get('h323_e164')]):
                    continue

                obj, created = maybe_update_or_create(Item, external_id_str=str(item.get('id') or ''), group=group, defaults={
                    'title': (item.get('name') or item.get('title') or '')[:255],
                    'sip': item.get('sip') or '',
                    'h323': item.get('h323') or '',
                    'h323_e164': item.get('h323_e164') or '',
                })

                valid_items.add(obj.id)

            for subgroup, subchildren, subitems in children:
                if flatten_groups:
                    _recurse(group, subchildren, subitems)
                    continue

                cur_group = existing_group_map.get(str(subgroup.get('id') or ''))
                defaults = dict(title=(subgroup.get('name') or subgroup.get('title') or '')[:255], parent=group)
                if not cur_group:
                    cur_group = maybe_update_or_create(Group,
                                                         address_book=self, source=to_group.source,
                                                         external_id_str=str(subgroup.get('id') or ''),
                                                         defaults=defaults,
                                                         )[0]
                else:
                    maybe_update(cur_group, defaults)

                valid_groups.add(cur_group.id)
                _recurse(cur_group, subchildren, subitems)

        _recurse(to_group, sub_group_items, items)

        if delete_other:
            if to_group.parent_id and to_group.parent.source_id != to_group.source_id:
                raise ValueError('Cant sync to subgroup and delete other')
            Item.objects.filter(group__source=to_group.source).exclude(pk__in=valid_items).delete()

            parents = (
                to_group.get_ancestors(include_self=True)
                .filter(source=to_group.source)
                .values_list('id', flat=True)
            )
            Group.objects.filter(source=to_group.source).exclude(pk__in=parents).exclude(
                pk__in=valid_groups
            ).delete()

    def try_merge_groups(self):
        try:
            return self.merge_groups()
        except Exception:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            capture_exception()

    def merge_groups(self):

        sync_groups = {sg.name_paths: sg for sg in SyncGroup.objects.filter(address_book=self)}

        valid_groups = set()

        def _get_valid_sync_group(name_paths: tuple) -> SyncGroup:
            sync_group = _get_sync_group(name_paths)
            valid_groups.add(sync_group.pk)
            if sync_group.name_paths not in sync_groups:
                sync_groups[sync_group.name_paths] = sync_group
            return sync_group

        def _get_sync_group(name_paths: tuple) -> SyncGroup:
            if name_paths in sync_groups:
                return sync_groups[name_paths]
            if not name_paths:
                return SyncGroup.objects.get_or_create(
                    address_book=self, parent=None, title='', customer=self.customer
                )[0]

            return partial_update_or_create(
                SyncGroup,
                address_book=self,
                full_path=SyncGroup.separator.join(name_paths),
                defaults={
                    'title': group.title,
                    'parent': _get_valid_sync_group(name_paths[:-1]),
                    'customer': self.customer,
                },
            )[0]

        for group in Group.objects.filter(address_book=self).prefetch_related(
            'parent', 'parent__parent', 'parent__parent__parent'
        ):
            partial_update(group, {'sync_group': _get_valid_sync_group(group.name_paths)})

        SyncGroup.objects.filter(address_book=self).exclude(pk__in=valid_groups - {None}).delete()

    @property
    def root_groups(self):
        return Group.objects.filter(source__address_book=self, parent__isnull=True)

    @property
    def all_groups(self):
        return Group.objects.get_queryset_descendants(
            self.root_groups, include_self=True
        ).select_related('source')

    def get_root(self, parent=None):

        if parent is None:
            groups = SyncGroup.objects.exclude(title='').filter(
                Q(parent__isnull=True) | Q(parent__title='', parent__parent__isnull=True),
                address_book=self,
            )

            items = Item.objects.filter(
                Q(group__parent__isnull=True, group__title=''),
                group__address_book=self,
            )
        else:
            groups = SyncGroup.objects.filter(address_book=self, parent=parent)
            items = Item.objects.filter(group__address_book=self, group__sync_group=parent)

        return groups.order_by('title'), items.order_by('title')

    def export(self):

        groups = {g.pk: g for g in Group.objects.filter(address_book=self).prefetch_related('source', 'parent')}

        fields = [
                'group',
                'title',
                'description',
                'sip',
                'h323',
                'h323_e164',
                'tel',
                'external_id_str',
            ]

        labels = [Item._meta.get_field(f).verbose_name or f for f in fields]

        labels.extend([
            _('Mapp'),
            _('Typ av mapp'),
            _('Grupp-ID'),
        ])

        rows = []

        for row in Item.objects.filter(group__address_book=self).values_list(*fields):

            group = groups[row[0]]
            group_cols = (group.full_name, group.source.type, group.external_id_str)

            rows.append(row[1:] + group_cols)

        rows.sort(key=lambda x: (x[-3], x[0]))

        return ExcelCreateFileSerializer(data={'headers': map(str, labels[1:]), 'rows': rows}).get_response()

    def search(self, value, group_id=None):

        if group_id:
            try:
                search_group_root = SyncGroup.objects.get(
                    address_book=self, pk=str(group_id).replace('g-', '')
                )
                # TODO has o00000000000000000tg any special meaning? Found in traceback
            except (SyncGroup.DoesNotExist, ValueError):
                return SyncGroup.objects.none(), Item.objects.none()
        else:
            search_group_root = None

        parent_groups, items = self.get_root(search_group_root)

        if not value:
            return parent_groups, items

        all_groups = []
        if search_group_root:
            all_groups.append(search_group_root.id)

        for parent in parent_groups:

            descendants = parent.get_descendants(include_self=True)
            all_groups.extend(descendants.values_list('id', flat=True))

        groups = SyncGroup.objects.filter(
            pk__in=all_groups,
        ).exclude(pk=search_group_root.id if search_group_root else None)

        if search_group_root:
            items = Item.objects.filter(
                group__in=Group.objects.filter(address_book=self, sync_group__in=all_groups)
            )
        else:
            items = Item.objects.filter(
                group__address_book__customer=self.customer, group__address_book=self
            )

        enable_full_text = False  # maybe enable later, needs prefix match
        if 'postgres' not in settings.DATABASES['default']['ENGINE']:
            enable_full_text = False

        if enable_full_text:  # use full text search in postgres
            items = items.filter(Q(title__search=value) | Q(sip__search=value))
            groups = groups.filter(title__search=value)
        else:
            items = items.filter(Q(title__icontains=value) | Q(sip__icontains=value))
            groups = groups.filter(title__icontains=value)

        groups_without_root = groups.exclude(title='', parent__isnull=True)
        return groups_without_root.order_by('title'), items.order_by('title')

    def limit_search(self, value, group_id=None, limit=20, last_id=None, offset=0):

        groups, items = self.search(value, group_id=group_id)

        limit = int(limit)

        result = ([], [])

        find_id = last_id or None

        i = 0
        for group in groups:
            i += 1

            if find_id is not None:
                if group.ext_id == find_id:
                    offset = i - 1
                    find_id = None
                continue
            elif i - offset >= limit:
                break

            result[0].append(group)

        for item in items:
            i += 1

            if find_id is not None:
                if item.ext_id == find_id:
                    offset = i - 1
                    find_id = None
                continue
            elif i - offset > limit:
                break

            result[1].append(item)

        return result

    def copy(self, new_title=None, link_manual=True):

        new_title = new_title or '{} - Copy {}'.format(self.title, date.today())

        new_book = AddressBook.objects.create(title=new_title, customer=self.customer, type=self.type,
                                              external_edit_url=self.external_edit_url, external_url=self.external_url)

        for m in ManualSource.objects.filter(address_book=self):
            link = ManualLinkSource.objects.create(manual_source=m, title=str(self), address_book=new_book, prefix=m.prefix)
            if not link_manual:
                link.merge_into_manual()

        try:
            ManualSource.objects.get_or_create(address_book=new_book)
        except Exception:
            pass

        sources = [
            CMSUserSource,
            CMSCoSpaceSource,
            TMSSource,
            SeeviaSource,
            EPMSource,
            VCSSource,
            ManualLinkSource,
        ]

        for cls in sources:
            for source in cls.objects.filter(address_book=self):
                source.pk = source.id = None
                source.address_book = new_book
                source.save()

        return new_book

    def get_absolute_url(self):
        return '/epm/addressbook/{}/?customer={}'.format(self.pk, self.customer_id)

    def get_soap_url(self):
        if self.is_external:
            return self.external_url
        return 'https://{}/tms/soap/{}/'.format(settings.EPM_HOSTNAME, self.secret_key)


class Source(models.Model):

    nested_items = False

    title = models.CharField(blank=True, max_length=255)
    address_book = models.ForeignKey(AddressBook, null=True, on_delete=models.CASCADE, related_name='sources')
    type = models.CharField(max_length=100)
    prefix = models.CharField(blank=True, max_length=200)
    last_sync = models.DateTimeField(null=True, editable=False)
    sync_errors = models.TextField(blank=True)

    def merge_into_manual(self):
        manual = self.address_book.sources.filter(type='Manual')[0]
        if manual == self:
            return
        self.groups.all().update(source=manual)
        self.delete()

    def __str__(self):
        return self.title or self.type

    def get_items(self) -> Union[List[dict], Tuple[dict, List[dict], List[dict]]]:
        raise NotImplementedError()


class ManualSource(Source):

    nested_items = True

    def save(self, *args, **kwargs):
        self.type = 'Manual'
        super().save(*args, **kwargs)
        Group.objects.get_or_create(source=self, parent=None, defaults=dict(customer=self.address_book.customer))

    def get_items(self):
        try:
            roots = list(Group.objects.filter(source=self, parent__isnull=True))
            assert len(roots), 1
            return roots[0].serialize_tree()
        except IndexError:
            return {}, [], []


class ManualLinkSource(Source):

    nested_items = True

    manual_source = models.ForeignKey(ManualSource, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        self.type = 'Manual link'
        super().save(*args, **kwargs)

    def get_items(self):
        return self.manual_source.get_items()


class CMSUserSource(Source):

    provider = models.ForeignKey('provider.Provider', on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        self.type = 'CMS User'
        super().save(*args, **kwargs)

    def get_api(self):
        return self.provider.get_api(self.address_book.customer)

    def get_items(self):

        api = self.get_api()
        users = api._iter_all_users(tenant_id=self.address_book.customer.acano_tenant_id)

        result = []
        for user in users:
            cur = {
                'name': user.findtext('./name'),
                'sip': user.findtext('./userJid'),
                'id': user.get('id'),
            }
            result.append(cur)
        return result


class TMSSource(Source):

    nested_items = True

    mac = models.CharField(max_length=17)
    phonebook_url = models.URLField()

    def save(self, *args, **kwargs):
        self.type = 'TMS'
        super().save(*args, **kwargs)

    def get_api(self):
        from provider.ext_api.tandberg import TandbergAPI
        return TandbergAPI(self.mac, phonebook_url=self.phonebook_url)

    def get_items(self):
        return self.get_api().recursive_get()


class SeeviaSource(Source):

    nested_items = True

    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    organization_id = models.UUIDField(max_length=36, help_text=_('ID på mapp eller organisation, www.seevia.me/organizations/123456-....'))

    def save(self, *args, **kwargs):
        self.type = 'Seevia'
        super().save(*args, **kwargs)

    def get_api(self):
        from provider.models.provider import SeeviaProvider
        provider = SeeviaProvider(id='invalid', username=self.username, password=self.password)
        return provider.get_api(Customer.objects.first())

    def get_items(self):
        raise ResponseConnectionError('Seevia service is no longer online')


class VCSSource(Source):

    provider = models.ForeignKey('provider.VCSEProvider', on_delete=models.CASCADE)
    limit_domains = models.CharField(max_length=300, blank=True)

    def save(self, *args, **kwargs):
        self.type = 'VCS'
        super().save(*args, **kwargs)

    def get_items(self):

        api = self.provider.get_api(self.address_book.customer)

        registrations = api.get_registrations()

        result = []

        limit_domains = [d.strip() for d in self.limit_domains.split(',') if d.strip()]

        for registration in registrations:

            if limit_domains:
                for d in limit_domains:
                    if registration.get('alias').endswith(d):
                        break
                else:
                    continue

            result.append({
                'name': registration['alias'],
                'sip': registration['alias'] if registration['protocol'] == 'SIP' else '',
                'h323': registration['number'] if registration['protocol'] == 'H323' else '',
            })

        return result


class EPMSource(Source):

    nested_items = True

    org_unit = models.ForeignKey('organization.OrganizationUnit', on_delete=models.CASCADE, null=True, blank=True)
    flatten = models.BooleanField(default=False, blank=True)
    ignore_hide_status = models.BooleanField(default=False, blank=True)

    def save(self, *args, **kwargs):
        self.type = 'Room systems'
        super().save(*args, **kwargs)

    def get_items(self):

        result = defaultdict(list)
        org_unit_children = defaultdict(list)

        from endpoint.models import Endpoint
        endpoints = Endpoint.objects.filter(customer=self.address_book.customer)

        if not self.ignore_hide_status:
            endpoints = endpoints.exclude(hide_from_addressbook=True)

        if self.org_unit:
            org_units = self.org_unit.get_descendants(include_self=True)
            endpoints = endpoints.filter(org_unit__in=org_units)
            for o in org_units:
                parent_id = o.parent_id if not self.flatten else None
                org_unit_children[parent_id].append(o)

        for endpoint in endpoints:
            if self.org_unit_id and not self.flatten:
                parent_id = endpoint.org_unit_id
            else:
                parent_id = None

            result[parent_id].append({
                'id': endpoint.id,
                'name': endpoint.title,
                'sip': endpoint.sip,
                'h323': endpoint.h323,
                'h323_e164': endpoint.h323_e164,
            })

        def _iter(folder_id, folder_name):
            items = list(result[folder_id])
            children = [_iter(folder.id, str(folder)) for folder in org_unit_children[folder_id]]
            item_count = len(items) + sum(c[0]['item_count'] for c in children)
            children = [c for c in children if c[0]['item_count']]
            return {'id': folder_id, 'name': folder_name, 'item_count': item_count}, children, items

        if self.org_unit_id and not self.flatten:
            return _iter(self.org_unit.id, str(self.org_unit))
        if self.flatten:
            return {}, [], _iter(None, 'Root')[2]
        return _iter(None, 'Root')


class CMSCoSpaceSource(Source):

    auto_generated = models.BooleanField(default=False, blank=True)

    provider = models.ForeignKey('provider.Provider', on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        self.type = 'CMS Spaces'
        super().save(*args, **kwargs)

    def get_api(self):
        return self.provider.get_api(self.address_book.customer)

    def get_items(self):

        api = self.get_api()

        from meeting.models import Meeting
        bookings = Meeting.objects.filter(provider=api.provider, backend_active=True).values_list('provider_ref2', flat=True)

        spaces = api._iter_all_cospaces(tenant_id=self.address_book.customer.acano_tenant_id)

        result = []
        for space in spaces:
            if space.get('id') in bookings:
                continue

            if space.findtext('./autoGenerated') == 'true' and not self.auto_generated:
                continue

            cur = {
                'id': space.get('id'),
                'name': space.findtext('./name'),
                'sip': api.get_sip_uri(space.findtext('./uri', '')),
            }
            result.append(cur)
        return result


class GroupManager(TreeManager):
    separator = re.compile(r' *[/>] *')

    def get_or_create_by_path(self, parent_group, full_name, customer=None, **kwargs):
        names = [s.strip() for s in self.separator.split(full_name) if s.strip()]
        return self.get_or_create_by_list(parent_group, names, customer=customer, **kwargs)

    def get_or_create_by_list(self, parent_group, lst, customer=None, **kwargs):

        parent = parent_group
        created = False

        from customer.models import Customer
        default_customer = Customer.objects.first()

        source_filter = {}
        if 'source' in kwargs:
            source_filter = {'source': kwargs.pop('source')}

        if not parent_group and not kwargs.get('address_book'):
            raise ValueError('parent_group or addressbook must be provided')

        if not customer:
            if parent and parent.customer:
                customer = parent.customer
            elif kwargs.get('address_book'):
                customer = kwargs['address_book'].customer

        for name in lst:
            parent, created = self.get_or_create(
                title__iexact=name,
                parent=parent,
                **source_filter,
                defaults={
                    'title': name,
                    'parent': parent,
                    'customer': customer or default_customer,
                    **kwargs,
                },
            )
        return parent, created


class SyncGroup(MPTTModel):

    address_book = models.ForeignKey(AddressBook, null=True, on_delete=models.CASCADE)

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    parent = TreeForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children'
    )
    title = models.CharField(max_length=255)
    full_path = models.TextField()

    separator = ' > '

    @property
    def name_paths(self):
        current = self
        names = []

        while current:
            if current.parent is None and not current.title:
                break

            names.extend(t.strip() for t in current.title.split('>') if t)
            current = current.parent

        return tuple(reversed(names))

    @property
    def full_name(self):
        return ' > '.join(self.name_paths).lstrip(' >')

    @property
    def ext_id(self):
        """used for endpoint search result"""
        return 'g-{}'.format(self.pk)

    def __str__(self):
        return self.title


class Group(MPTTModel):

    address_book = models.ForeignKey(
        AddressBook, null=True, related_name='groups', on_delete=models.CASCADE
    )
    sync_group = models.ForeignKey(SyncGroup, null=True, on_delete=models.SET_NULL)

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    title = models.CharField(max_length=255)

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='groups', null=True)

    external_id_str = models.CharField(max_length=128, db_index=True, blank=True, editable=False)
    external_id = models.PositiveIntegerField(db_index=True, null=True, blank=True, editable=False)

    objects = GroupManager()

    @property
    def ext_id(self):
        "used for endpoint search result"
        return 'g-{}'.format(self.pk)

    @property
    def is_editable(self):
        return not self.source_id or self.source.type == 'Manual'

    def iter_items(self):

        for item in Item.objects.filter(group__in=self.get_descendants(include_self=True)):

            yield item

    @property
    def full_name(self):
        return ' > '.join(self.name_paths).lstrip(' >')

    @property
    def name_paths(self):
        current = self
        names = []

        while current:
            if current.parent is None and not current.title:
                break

            names.extend(t.strip() for t in current.title.split('>') if t)
            current = current.parent

        return tuple(reversed(names))

    def serialize_tree(self):
        def _recurse(groups):

            result = []
            for group in groups:
                subgroups = Group.objects.filter(parent=group)
                items = [item.as_dict() for item in Item.objects.filter(group=group)]

                cur = (group.as_dict(), _recurse(subgroups), items)
                result.append(cur)
            return result

        return _recurse([self])[0]

    def as_dict(self):
        return {
            'id': self.pk,
            'title': self.title,
            'parent': self.parent_id,
        }

    def save(self, *args, **kwargs):

        if not self.source_id and self.parent_id:
            self.source = self.parent.source
        if not self.address_book_id and self.source_id:
            self.address_book = self.source.address_book

        if not self.customer_id and self.parent_id:
            self.customer = self.parent.customer
        if not self.customer_id and self.address_book_id:
            self.customer = self.address_book.customer

        super().save(*args, **kwargs)

        if self.address_book and not self.address_book.is_syncing:
            self.address_book.merge_groups()
            self.refresh_from_db(fields=['sync_group'])

    def __str__(self):
        if not self.title and not self.parent_id:
            return '<Root>'
        return self.title


class Item(models.Model):

    TYPES = (
        (0, _('Virtual Room')),
        (10, _('Physical Room')),
        (20, _('Person')),
    )

    customer = models.ForeignKey(Customer, editable=False, on_delete=models.CASCADE)
    group = TreeForeignKey(Group, verbose_name=_('Grupp'), on_delete=models.CASCADE)

    title = models.CharField(_('Rubrik'), max_length=255)
    description = models.TextField(_('Beskrivning'), blank=True)
    type = models.SmallIntegerField(verbose_name=_('Typ'), choices=TYPES, default=0)

    sip = models.CharField('SIP', max_length=255, blank=True)
    h323 = models.CharField('H323', max_length=255, blank=True)
    h323_e164 = models.CharField(_('H323 E.164'), max_length=100, blank=True)
    tel = models.CharField(_('Telefon'), max_length=100, blank=True)

    external_id_str = models.CharField(max_length=128, db_index=True, blank=True, editable=False)
    external_id = models.PositiveIntegerField(db_index=True, null=True, blank=True, editable=False)

    @property
    def ext_id(self):
        "used for endpoint search result"
        return 'i-{}'.format(self.pk)

    @property
    def is_editable(self):

        return not self.group.source_id or self.group.source.type == 'Manual'

    def as_dict(self):
        return {
            'id': self.pk,
            'group': self.group_id,
            'title': self.title,
            'description': self.description,
            'sip': self.sip,
            'h323': self.h323,
            'h323_e164': self.h323_e164,
            'tel': self.tel,
        }

    def save(self, *args, **kwargs):

        if not self.customer_id:
            self.customer = self.group.customer

        if not self.title:
            self.title = self.sip or self.h323 or self.h323_e164 or ''

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
