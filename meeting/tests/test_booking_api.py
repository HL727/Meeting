import urllib.parse

from django.urls import reverse
from django.test import TestCase, override_settings
from django.test.client import MULTIPART_CONTENT

from supporthelpers.tests.base import SupporthelpersTestCaseBase, SupporthelpersTestCasePexipBase


class UserCospacesListViewTestCase(SupporthelpersTestCaseBase, TestCase):
    "test for meeting.api_views.UserCospacesListView"

    @property
    def url(self):
        return reverse('api_user_cospaces', args=[]) + '?user_jid={}&key={}&extended_key=test'.format(self.user_jid, self.customer_shared_key)

    def test_get(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.url)
        self.assertContains(response, 'OK', status_code=200)

        meeting = self._book_meeting()
        from meeting.models import Meeting

        Meeting.objects.filter(provider=self.customer.lifesize_provider).update(
            provider=self.customer.lifesize_provider.cluster
        )
        # self.assertIn(meeting.provider_ref2, [str(c['id']) for c in response.json()['cospaces']])

        with override_settings(EXTENDED_API_KEYS=['test']):
            response2 = self.client.get(self.url)

        self.assertNotIn(
            meeting.provider_ref2, [str(c['id']) for c in response2.json()['cospaces']]
        )


class UserCospacesListViewPexipTestCase(
    UserCospacesListViewTestCase, SupporthelpersTestCasePexipBase
):
    def test_email(self):
        from datastore.utils.pexip import sync_all_pexip
        from meeting.models import Meeting

        Meeting.objects.all().delete()  # scheduled cospaces are filtered
        sync_all_pexip(self.pexip.cluster)

        from datastore.models import pexip

        email = pexip.Email.objects.create(provider=self.pexip.cluster, email='email@example.org')
        pexip.Conference.objects.create(
            provider=self.pexip.cluster, name='EMAIL', is_active=True, cid=654, email=email
        )

        with override_settings(EXTENDED_API_KEYS=['test']):
            url = reverse(
                'api_user_cospaces', args=[]
            ) + '?email={}&key={}&extended_key=test'.format(email.email, self.customer_shared_key)
            response = self.client.get(url)
        self.assertContains(response, 'EMAIL', status_code=200)


class UserStatusViewTestCase(SupporthelpersTestCaseBase, TestCase):
    "test for meeting.api_views.UserStatusView"

    @property
    def url(self):
        return reverse('api_user_status', args=[]) + '?user_jid={}&key={}&extended_key=test'.format(self.user_jid, self.customer_shared_key)

    def test_get(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.url)
        self.assertContains(response, 'OK', status_code=200)
        self.assertEqual(response.json()['user_exists'], True)

    def test_get_invalid_user(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.url.replace(self.user_jid, 'invalid'))
        self.assertContains(response, 'OK', status_code=200)
        self.assertEqual(response.json()['user_exists'], False)

    def test_get_invalid_customer(self):
        response = self.client.get(self.url.replace(self.customer_shared_key, 'invalid'))
        self.assertEqual(response.status_code, 403)
        self.assertNotEquals(response.json()['status'], 'OK')
        self.assertFalse(response.json().get('user_exists'))


class UserStatusViewPexipTestCase(UserStatusViewTestCase, SupporthelpersTestCasePexipBase):
    pass


class UserCospaceChangeTestCase(SupporthelpersTestCaseBase, TestCase):
    """Test changing user cospace"""

    def setUp(self):
        from api_key.models import BookingAPIKey

        super().setUp()
        with override_settings(EXTENDED_API_KEYS=["test"]):
            BookingAPIKey.objects.populate_system_keys()
        BookingAPIKey.objects.all().update(enable_cospace_changes=True)

    @property
    def url(self):
        return self.get_url(self.user_jid)

    def get_url(self, user_jid, extended_key='test'):
        return reverse(
            "api_user_cospace_change", args=[self.cospace_id]
        ) + "?user_jid={}&key={}&extended_key={}".format(
            user_jid, self.customer_shared_key, extended_key
        )

    def test_get(self):
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.get(self.get_url(self.user_jid))
        self.assertContains(response, "", status_code=400)

    def test_post_invalid(self):
        data = {
            "password": "00099",
        }
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.post(self.get_url(self.user_jid), data)
            self.assertContains(response, "Error", status_code=400)

    def test_put_invalid(self):
        data = {
            "password": "00099",
        }
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.put(self.get_url(self.user_jid), data)
            self.assertContains(response, "Error", status_code=400)

    def test_post_valid(self):
        data = {
            "name": "test",
            "password": "00099",
        }
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.post(self.get_url(self.user_jid), data)
            self.assertContains(response, self.cospace_id, status_code=200)

    def test_post_valid_invalid_key(self):
        data = {
            "name": "test",
            "password": "00099",
        }
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.post(self.get_url(self.user_jid, 'test2'), data)
            self.assertContains(response, '', status_code=403)

    def test_put_valid(self):
        data = {
            "name": "test",
            "password": "00099",
            "moderator_password": "00098",
        }
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.put(
                self.get_url(self.user_jid),
                urllib.parse.urlencode(data),
            )
            self.assertContains(response, self.cospace_id, status_code=200)

    def test_patch(self):
        data = {
            "password": "00099",
        }
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.patch(
                self.get_url(self.user_jid),
                urllib.parse.urlencode(data),
                content_type=MULTIPART_CONTENT,
            )
            self.assertContains(response, self.cospace_id, status_code=200)

    def test_patch_moderator_password(self):
        data = {
            "moderator_password": "00099",
        }
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.patch(
                self.get_url(self.user_jid),
                urllib.parse.urlencode(data),
                content_type=MULTIPART_CONTENT,
            )
            self.assertContains(response, self.cospace_id, status_code=200)


class UserCospaceChangePexipTestCase(UserCospaceChangeTestCase, SupporthelpersTestCasePexipBase):
    pass


class UserCospaceInviteMessageTestCase(SupporthelpersTestCaseBase, TestCase):
    "test for meeting.api_views.UserCospaceInviteMessage"

    @property
    def url(self):
        return self.get_url(self.user_jid)

    def get_url(self, user_jid):
        return reverse('api_user_cospace_invite', args=[self.cospace_id]) + '?user_jid={}&key={}&extended_key=test'.format(user_jid, self.customer_shared_key)

    def test_get(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.url)
        self.assertContains(response, 'OK', status_code=200)

    def test_get_user_without_space(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.get_url(self.user_jid_without_space))
        self.assertContains(response, 'OK', status_code=200)


class UserCospaceInviteMessagePexipTestCase(UserCospaceInviteMessageTestCase, SupporthelpersTestCasePexipBase):

    def test_email(self):
        from datastore.utils.pexip import sync_all_pexip

        sync_all_pexip(self.pexip.cluster)

        from datastore.models import pexip

        email = pexip.Email.objects.create(provider=self.pexip.cluster, email='email@example.org')
        conf = pexip.Conference.objects.create(
            provider=self.pexip.cluster, name='EMAIL', is_active=True, cid=654, email=email
        )

        with override_settings(EXTENDED_API_KEYS=['test']):
            url = reverse(
                'api_user_cospace_invite', args=[conf.cid]
            ) + '?email={}&key={}&extended_key=test'.format(email.email, self.customer_shared_key)
            response = self.client.get(url)
        self.assertContains(response, 'EMAIL', status_code=200)


class UserUserInviteMessageTestCase(SupporthelpersTestCaseBase, TestCase):
    "test for meeting.api_views.UserUserInviteMessage"

    @property
    def url(self):
        return self.get_url(self.user_jid)

    def get_url(self, user_jid):
        return reverse('api_user_invite') + '?user_jid={}&key={}&extended_key=test'.format(user_jid, self.customer_shared_key)

    def test_get(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.url)
        self.assertContains(response, 'OK', status_code=200)

    def test_get_user_without_space(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.get_url(self.user_jid_without_space))
        self.assertContains(response, 'OK', status_code=200)


class UserUserInviteMessagePexipTestCase(UserUserInviteMessageTestCase, SupporthelpersTestCasePexipBase):
    def test_get(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.url)
        self.assertContains(response, 'not found', status_code=404)

    def test_get_user_without_space(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.get_url(self.user_jid_without_space))
        self.assertContains(response, 'not found', status_code=404)


class UserRecordingsListTestCase(SupporthelpersTestCaseBase, TestCase):
    "test for meeting.api_views.UserRecordingsListView"

    def setUp(self):
        from recording.models import AcanoRecording

        super().setUp()

        self.meeting = self._book_meeting(provider_ref2=self.cospace_id, creator=self.user_jid)

        AcanoRecording.objects.create(cospace_id=self.cospace_id, path='test', title='testrecordingtitle')

    @property
    def url(self):
        return reverse('api_user_recordings') + '?user_jid={}&key={}&extended_key=test'.format(self.user_jid, self.customer_shared_key)

    def test_get(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.url)
        self.assertContains(response, 'OK', status_code=200)
        self.assertContains(response, 'testrecordingtitle', status_code=200)

    def test_get_cospace_id(self):
        with override_settings(EXTENDED_API_KEYS=['test']):
            response = self.client.get(self.url + '&cospace_id=invalid')
        self.assertContains(response, 'OK', status_code=200)
        self.assertEqual(response.json()['recordings'], [])


class AddressBookSearchTestCase(SupporthelpersTestCaseBase):
    def setUp(self):
        super().setUp()
        from address.models import AddressBook, Group, Item
        from endpoint.models import CustomerSettings

        self.address_book = AddressBook.objects.create(title="test", customer=self.customer)
        self.root = Group.objects.create(
            title="", address_book=self.address_book, customer=self.customer
        )
        self.group = Group.objects.create(
            title="sub", parent=self.root, address_book=self.address_book, customer=self.customer
        )
        Item.objects.create(title="root", group=self.root, sip="root@example.org")
        Item.objects.create(title="ABC123", group=self.group, sip="test@example.org")

        c_settings = CustomerSettings.objects.get_for_customer(self.customer)
        c_settings.default_portal_address_book = self.address_book
        c_settings.save()

    def get_url(self, q=""):
        return reverse(
            "api_addressbook_search"
        ) + "?user_jid={}&key={}&extended_key=test&q={}".format(
            self.user_jid, self.customer_shared_key, q
        )

    def test_get_empty(self):

        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.get(self.get_url(""))
            self.assertContains(response, "root@example.org", status_code=200)
            self.assertNotContains(response, "test@example.org", status_code=200)

    def test_get_group(self):

        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.get(
                self.get_url("&group={}".format(self.group.sync_group_id)),
            )
            self.assertNotContains(response, "root@example.org", status_code=200)
            self.assertContains(response, "test@example.org", status_code=200)

    def test_get_query(self):

        with override_settings(EXTENDED_API_KEYS=["test"]):

            response = self.client.get(self.get_url("ABC123"))
            self.assertContains(response, "test@example.org", status_code=200)

    def test_get_non_match(self):

        with override_settings(EXTENDED_API_KEYS=["test"]):

            response = self.client.get(self.get_url("ABC1234"))
            self.assertNotContains(response, "test@example.org", status_code=200)

    def test_get_without_address_book(self):
        self.address_book.delete()
        with override_settings(EXTENDED_API_KEYS=["test"]):
            response = self.client.get(self.get_url())
        self.assertNotContains(response, "test@example.org", status_code=200)
