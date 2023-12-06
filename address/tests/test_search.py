from django.test import TestCase

from address.models import AddressBook, Group, Item, SyncGroup
from address.tests.test_sync import AddressBookTestBase
from conferencecenter.tests.base import ConferenceBaseTest
from provider.ext_api.tandberg import TandbergAPI
from defusedxml.cElementTree import fromstring as safe_xml_fromstring


class AddressTest(TestCase):

    def test_address(self):

        from provider.models.provider import Provider
        from customer.models import Customer

        customer = Customer.objects.create(title='test')
        Provider.objects.create(title='test', ip='127.0.0.1', type=1)

        group = Group.objects.create(title='test', customer=customer)
        group2 = Group.objects.create(title='test 2', parent=group, customer=customer)

        Item.objects.create(group=group, title='test')
        Item.objects.create(group=group2, title='test')

        self.assertEqual(sum(1 for x in group.iter_items()), 2)

        from ext_sync.models import LdapSync, LdapSyncState
        from provider.models.provider import LdapProvider

        ldap = LdapSync.objects.create(customer=customer,
            provider=LdapProvider.objects.create(title='test', ip='127.0.0.1'),
            sync_address_book=True,
            )

        sync = LdapSyncState.objects.create(ldap=ldap)
        self.assertEqual(len(sync.get_valid()), 2)


class SearchTest(AddressBookTestBase):

    def test_search_root(self):
        groups, items = self.book.search('')
        self.assertEqual(len(groups), 1)
        self.assertEqual({g.title for g in groups}, {'test'})
        self.assertEqual({i.title for i in items}, {'Item3'})

        groups, items = self.book.search('Item3')
        self.assertEqual({i.title for i in items}, {'Item3'})

    def test_search_group(self):

        groups, items = self.book.search('', Group.objects.get(title='test').sync_group_id)
        self.assertEqual(len(groups), 1)
        self.assertEqual({i.title for i in items}, {'My Item nr 1 åäö!"#¤%'})

        groups, items = self.book.search('My item', Group.objects.get(title='test').sync_group_id)
        self.assertEqual({i.title for i in items}, {'My Item nr 1 åäö!"#¤%'})

    def test_isolation(self):

        book2 = AddressBook.objects.create(customer=self.customer, title='OTHER')
        g0 = Group.objects.create(address_book=book2, title='OTHER0')
        g1 = Group.objects.create(address_book=book2, title='OTHER1', parent=g0)
        g2 = Group.objects.create(address_book=book2, title='OTHER2', parent=g1)

        Item.objects.create(group=g0, title='OTHER0', sip='test@example.org')
        Item.objects.create(group=g1, title='OTHER1', sip='test@example.org')
        Item.objects.create(group=g2, title='OTHER2', sip='test@example.org')

        book2.sync()
        groups, items = self.book.search('')
        self.assertTrue(groups and items)
        self.book.sync()

        # working search in other book
        groups, items = book2.search('')
        self.assertEqual({g.title for g in groups}, {'OTHER0'})
        self.assertEqual({i.title for i in items}, set())

        groups, items = book2.search('', group_id=g0.ext_id)
        self.assertEqual({g.title for g in groups}, {'OTHER1'})
        self.assertEqual({i.title for i in items}, {'OTHER0'})

        groups, items = book2.search('OTHER')
        self.assertEqual({g.title for g in groups}, {'OTHER0', 'OTHER1', 'OTHER2'})
        self.assertEqual({i.title for i in items}, {'OTHER0', 'OTHER1', 'OTHER2'})

        # not included in other book
        groups, items = self.book.search('')
        self.assertFalse([g for g in groups if 'OTHER' in g.title])
        self.assertFalse([i for i in items if 'OTHER' in i.title])

        groups, items = self.book.search('', group_id=g1.ext_id)
        self.assertFalse([g for g in groups if 'OTHER' in g.title])
        self.assertFalse([i for i in items if 'OTHER' in i.title])

        groups, items = self.book.search('OTHER')
        self.assertFalse([g for g in groups if 'OTHER' in g.title])
        self.assertFalse([i for i in items if 'OTHER' in i.title])

    def test_group_merge(self):

        group_trees = sorted(g.full_name for g in Group.objects.filter(address_book=self.book))
        sync_group_trees = sorted(
            g.full_name for g in SyncGroup.objects.filter(address_book=self.book)
        )
        self.assertEqual(group_trees, sync_group_trees)

    def test_limit(self):
        for _i in range(10):
            Item.objects.create(group=self.subgroup, title='test')

        groups, items = self.book.search('', self.subgroup.sync_group_id)
        self.assertEqual(len(groups), 0)
        self.assertEqual(len(items), 11)

        groups, items = self.book.limit_search('', self.subgroup.sync_group_id, limit=5)
        self.assertEqual(len(groups), 0)
        self.assertEqual(len(items), 5)

        self.book.limit_search('', self.subgroup.sync_group_id, limit=5, last_id=6)

    def test_tms_search(self):

        book = self.book

        headers = {
            'HTTP_SOAPACTION': 'http://www.tandberg.net/2004/06/PhoneBookSearch/Search',
        }

        data = TandbergAPI.get_search_xml('00:00:00:00:00', 'item2')

        response = self.client.post(book.get_soap_url().replace(book.secret_key, 'invalid'), data, content_type='text/xml', **headers)
        self.assertEqual(response.status_code, 404)

        response = self.client.post(book.get_soap_url(), data, content_type='text/xml', **headers)
        self.assertContains(response, 'Item2with very long first name', status_code=200)

        safe_xml_fromstring(response.content)

        data = TandbergAPI.get_search_xml('00:00:00:00:00', 'no exist')
        response = self.client.post(book.get_soap_url(), data, content_type='text/xml', **headers)
        self.assertNotContains(response, 'Item2with very long first name', status_code=200)
