from django.test import TestCase
from django.urls import reverse
from .base import SupporthelpersTestCaseBase


class UsersListViewTestCase(SupporthelpersTestCaseBase, TestCase):
    "test for supporthelpers.views.users.UserListView"

    @property
    def url(self):
        return reverse('users', args=[])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, '', status_code=200)

    def test_export_to_excel(self):
        response = self.client.get(self.url + '?export_to_excel=1')
        self.assertEqual(response.status_code, 200)



class UserDetailsTestCase(SupporthelpersTestCaseBase, TestCase):
    "test for supporthelpers.views.users.UserDetails"

    @property
    def url(self):
        return reverse('user_details', args=[self.user_id])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, '', status_code=200)

    def test_post_error(self):
        data = {
            'add_member': '',
            'form_action': '',
            'match_member': '',
            'members': '',
            'remove_member': '',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

    def test_post_remove_member_error(self):
        data = {
            'remove_member': '',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

    def test_post_remove_member_valid(self):
        # TODO
        data = {
            'remove_member': '1',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

    def test_post_members_error(self):
        data = {
            'members': '',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

    def test_post_members_valid(self):
        data = {
            'members': '1',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

    def test_post_add_cospaces_error(self):
        data = {
            'form_action': 'add_cospaces',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

    def test_post_add_cospaces_valid(self):
        data = {
            'form_action': 'add_cospaces',
            'cospaces_to_add': '123',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)


class UserInviteViewTestCase(SupporthelpersTestCaseBase, TestCase):
    "test for supporthelpers.views.users.UserInviteViewTestCase"

    @property
    def url(self):
        return reverse('user_invite', args=[self.user_id])

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, '', status_code=200)
