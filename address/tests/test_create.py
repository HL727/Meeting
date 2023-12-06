import json

from rest_framework.test import APITestCase

from address.models import AddressBook, Item
from conferencecenter.tests.base import ConferenceBaseTest
from django.urls import reverse
from django.contrib.auth.models import User



class ItemCreateBase(ConferenceBaseTest, APITestCase):
    def setUp(self):
        self._init() # base

        self.api = self._get_api()
        self.bulk_url = reverse('item-bulk-create')

        self.address_book = AddressBook.objects.create(title='test', customer=self.customer)
        self.root_group = self.address_book.root_groups.first()

        self.user = User.objects.create_superuser(username='test', password='test', email='test@example.org')
        self.client.login(username='test', password='test')

    def _get_api(self):
        provider = self.customer.get_provider()
        return provider.get_api(self.customer)


class ItemCreateTest(ItemCreateBase):

    @property
    def url(self):
        return '/json-api/v1/addressbook_item/'

    def test_group_create(self):
        data = {
            'title': 'test2',
            'sip': 'test@example.org',
            'group': self.root_group.pk,
        }

        response = self.client.post(self.url, data)
        self.assertContains(response, 'test2', status_code=201)

        response = self.client.get(
            '/json-api/v1/addressbook/{}/items/'.format(self.address_book.pk)
        )
        self.assertContains(response, text='"is_editable":true', status_code=200)


class ItemUpdateTest(ItemCreateBase):

    @property
    def url(self):
        return '/json-api/v1/addressbook_item/1/'

    def test_update(self):
        Item.objects.create(group=self.root_group, title='test', sip='test', pk=1)
        response = self.client.patch(self.url, {'title': 'test2', 'group': self.root_group.pk})
        self.assertContains(response, 'test2', status_code=200)


class ItemCreateBulkTest(ItemCreateBase):
    def test_authentication(self):
        c = self.client

        data = {}
        result = c.post(self.bulk_url, data)

        self.assertEqual(result.status_code, 400)

        c.logout()

        result = c.post(self.bulk_url, data)
        self.assertEqual(result.status_code, 403)

    def _get_multiple_item_data(self):
        return [
            {
                'title': 'test2',
                'sip': 'test@example.org',
                'group_path': 'test1 > test2',
            },
            {
                'title': 'test3',
                'sip': 'test@example.org',
                'group_path': 'test1 > test3',
            },
        ]

    def test_invalid_root(self):
        c = self.client

        data = {
            'group': 9999,
            'items': self._get_multiple_item_data(),
        }
        result = c.post(self.bulk_url, json.dumps(data), content_type='application/json')
        self.assertEqual(result.status_code, 400)
        self.assertNotEqual(None, result.json().get('group'))

    def test_no_root(self):
        c = self.client

        data = {
            'items': self._get_multiple_item_data(),
        }
        result = c.post(self.bulk_url, json.dumps(data), content_type='application/json')
        self.assertEqual(result.status_code, 400)
        self.assertNotEqual(None, result.json().get('group'))

    def test_create_valid(self):
        c = self.client

        data = {
            'group': self.root_group.pk,
            'items': self._get_multiple_item_data(),
        }

        result = c.post(self.bulk_url, json.dumps(data), content_type='application/json')
        self.assertEqual(result.status_code, 201)

        self.root_group.refresh_from_db()
        self.assertEqual(self.root_group.get_descendants().count(), 3)
        self.assertEqual(set(self.root_group.get_descendants().values_list('title', flat=True)), {'test1', 'test2', 'test3'})

