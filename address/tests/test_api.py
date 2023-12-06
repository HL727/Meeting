from django.contrib.auth.models import User

from address.models import AddressBook
from address.tests.test_sync import AddressBookTestBase


class AddressBookAPITestCase(AddressBookTestBase):

    def setUp(self):
        super().setUp()
        User.objects.create_user(username='test', password='test', is_staff=True)
        self.client.login(username='test', password='test')

    def get_url(self, book_id, suffix):
        return '/json-api/v1/addressbook/{}/{}'.format(book_id, suffix or '')

    def test_copy(self):

        response = self.client.post(self.get_url(self.book.id, 'copy/'), {'new_title': 'Copy'})
        self.assertEqual(response.status_code, 200)
        new_id = response.json()['id']

        providers = self.client.get('/json-api/v1/addressbook/providers/').json()

        data = {
            'type': 'manual_link',
            'title': 'Test',
            'manual_source': providers['manual'][0]['id'],
        }
        response = self.client.post(self.get_url(new_id, 'source/'), data)
        self.assertEqual(response.status_code, 200)

        source_id = [s for s in response.json()['sources'] if s['type'] == 'Manual link'][0]['id']
        response = self.client.post(self.get_url(new_id, 'make_source_editable/'), {'id': source_id})
        self.assertEqual(response.status_code, 200)

    def test_copy_without_title(self):
        response = self.client.post(self.get_url(self.book.id, 'copy/'), {'new_title': 'Copy'})
        self.assertEqual(response.status_code, 200)

    def test_source_links(self):

        response = self.client.post(self.get_url(self.book.id, 'copy/'), {'new_title': 'Copy'})
        self.assertEqual(response.status_code, 200)
        new_id = response.json()['id']

        links_response = self.client.post(self.get_url(self.book.id, 'check_source_links/'), {'id': self.book.sources.get(type='Manual').pk})
        self.assertEqual(links_response.status_code, 200)
        self.assertEquals(len(links_response.json()), 1)

        AddressBook.objects.get(pk=new_id).delete()

        links_response = self.client.post(self.get_url(self.book.id, 'check_source_links/'), {'id': self.book.sources.get(type='Manual').pk})
        self.assertEqual(links_response.status_code, 200)
        self.assertEquals(len(links_response.json()), 0)

        links_response2 = self.client.get(self.get_url(self.book.id, 'source_links/'))
        self.assertEqual(links_response2.content, links_response.content)




