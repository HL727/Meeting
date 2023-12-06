from typing import Type

from django.contrib.auth.models import User

from address.models import AddressBook, Group, Item, EPMSource, CMSUserSource, ManualSource, CMSCoSpaceSource, \
    VCSSource, ManualLinkSource, Source
from conferencecenter.tests.base import ConferenceBaseTest
from endpoint.models import Endpoint
from organization.models import OrganizationUnit


class AddressBookTestBase(ConferenceBaseTest):

    def setUp(self):
        self._init()

        self.assertEqual(Group.objects.all().count(), 0)
        book: AddressBook = AddressBook.objects.create(customer=self.customer)
        self.book = book

        root = Group.objects.get(address_book=book)
        group = Group.objects.create(title='test', customer=self.customer, parent=root)
        subgroup = Group.objects.create(title='test 2', parent=group, customer=self.customer)

        self.item = Item.objects.create(
            group=group, title='My Item nr 1 åäö!"#¤%', sip='sip:test@example.org'
        )
        self.item2 = Item.objects.create(
            group=subgroup, title='Item2with very long first name', h323='test@example.org'
        )
        self.item3 = Item.objects.create(group=root, title='Item3', h323='test@example.org')

        self.item_count = Item.objects.filter(group__address_book=self.book).count()

        self.group = group
        self.subgroup = subgroup

    def get_single_url(self, book_id, suffix):
        return '/json-api/v1/addressbook/{}/{}'.format(book_id, suffix or '')


class SyncTestCase(AddressBookTestBase):

    def setUp(self):
        User.objects.create_user(username='test', password='test', is_staff=True)
        self.client.login(username='test', password='test')
        super().setUp()


    def _sync(self, source):
        result = source.get_items()
        if source.nested_items:
            self.assertEqual(len(result), 3)
            self.assertTrue(isinstance(result[0], dict))
            self.assertTrue(isinstance(result[1], (list, tuple)))
            self.assertTrue(isinstance(result[2], (list, tuple)))
            items = []
            def _rec(lst):
                items.extend(lst[2])
                for sub in lst[1]:
                    _rec(sub)
            _rec(result)
        else:
            self.assertTrue(isinstance(result, (list, tuple)))
            items = result
        self.assertGreater(len(items), 0)

        self.book.sync()
        self.assertFalse(source.sync_errors)

        new_item_count = Item.objects.filter(group__address_book=self.book).count()
        self.assertEqual(new_item_count, self.item_count + len(items))
        self.item_count = new_item_count

        return result

    def _create_sync(self, data: dict, model_type: Type[Source]):
        response = self.client.post(self.get_single_url(self.book.id, 'source/'), data)
        self.assertEquals(response.status_code, 200)
        return model_type.objects.get(pk=response.json()['source_id'])

    def test_sync_epm(self):
        Endpoint.objects.create(customer=self.customer, connection_type=Endpoint.CONNECTION.PASSIVE, sip='test@example.org')
        org_unit = OrganizationUnit.objects.create(customer=self.customer)

        org_unit2 = OrganizationUnit.objects.create(customer=self.customer, parent=org_unit)
        Endpoint.objects.create(customer=self.customer, connection_type=Endpoint.CONNECTION.PASSIVE, org_unit=org_unit2, sip='test@example.org')

        source = self._create_sync({'type': 'epm'}, EPMSource)
        self._sync(source)

        source2 = EPMSource.objects.create(address_book=self.book, org_unit=org_unit2, flatten=True)
        result = self._sync(source2)
        self.assertEqual(result[1], [])
        self.assertGreater(len(result[2]), 0)

    def test_sync_cms_user(self):
        source = self._create_sync({'type': 'cms_user', 'provider': self.acano.pk}, CMSUserSource)
        self._sync(source)

    def test_sync_cms_cospaces(self):
        source = self._create_sync({'type': 'cms_spaces', 'provider': self.acano.pk}, CMSCoSpaceSource)
        self._sync(source)

    def test_sync_cms_cospaces_subgroups(self):
        source = self._create_sync(
            {'type': 'cms_spaces', 'provider': self.acano.pk, 'prefix': 'Sub1 > Sub2 > Sub3'},
            CMSCoSpaceSource,
        )
        self._sync(source)

        groups = Group.objects.values_list('title', flat=True)
        tree = {'Sub1', 'Sub2', 'Sub3'}
        self.assertEqual(tree, set(groups) & tree)

    def test_sync_vcs(self):
        self._create_sync({'type': 'vcs', 'provider': self.vcse.pk}, VCSSource)
        self.book.sync()
        #  self._sync(source)  # TODO mock api

    def test_sync_manual(self):
        source = ManualLinkSource.objects.create(address_book=self.book, manual_source=ManualSource.objects.get(address_book=self.book))
        self._sync(source)

    def test_sync_tms(self):
        pass  # TODO

    def test_sync_seevia(self):
        pass  # TODO
