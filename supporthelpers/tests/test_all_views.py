from django.conf import settings
from django.urls import reverse

from conferencecenter.tests.mock_data.acano import distinct_ids
from meeting.models import Meeting
from organization.models import CoSpaceUnitRelation
from .base import SupporthelpersTestCaseBase


class IndexViewTestCase(SupporthelpersTestCaseBase):

    valid_response = 200 if settings.ENABLE_CORE else 302

    def test_get(self):
        response = self.client.get(reverse('index', args=[]))
        self.assertEqual(response.status_code, 200)

    def test_status(self):
        response = self.client.get(reverse('index', args=[]) + '?get_status=1')
        self.assertEqual(response.status_code, self.valid_response)

    def test_counters(self):
        response = self.client.get(reverse('index', args=[]) + '?get_counters=1')
        self.assertEqual(response.status_code, self.valid_response)
        self.assertFalse(response.json().get('error'))


class IndexViewPexipTestCase(IndexViewTestCase):

    provider_subtype = 2


class WebinarViewTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('webinar', args=[]))
        self.assertEqual(response.status_code, 200)

    def test_post_error(self):
        data = {
            'customer': '',
            'enable_chat': '',
            'force_encryption': '',
            'group': '',
            'moderator_password': '',
            'password': '',
            'title': '',
            'uri': '',
        }
        response = self.client.post(reverse('webinar', args=[]), data)
        self.assertEqual(response.status_code, 200)

    def test_post_valid(self):
        data = {
            'title': 'Ett webinar',
            'uri': 'test',
            'password': '1234',
            'moderator_password': '9999',
            'group': 'mindspace',
            'enable_chat': 1,
            'customer': self.customer.pk,
        }
        response = self.client.post(reverse('webinar', args=[]), data)
        self.assertEqual(response.status_code, 200)

        # unbook
        data = {
            'unbook': Meeting.objects.get(webinars__isnull=False).pk,
        }
        response = self.client.post(reverse('webinar', args=[]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_unbook_error(self):
        data = {
            'unbook': '2',
        }
        response = self.client.post(reverse('webinar', args=[]), data)
        self.assertEqual(response.status_code, 404)


class CoSpaceIndexTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('cospaces', args=[]))
        self.assertEqual(response.status_code, 200)

    def test_acano_excel_export(self):
        response = self.client.get(reverse('cospaces', args=[]) + '?export_to_excel=1')
        self.assertEqual(response.status_code, 200)

    def test_pexip_excel_export(self):
        self.customer.lifesize_provider = self.pexip
        self.customer.save()
        response = self.client.get(reverse('cospaces', args=[]) + '?export_to_excel=1')
        self.assertEqual(response.status_code, 200)


class CoSpaceIndexPexipTestCase(CoSpaceIndexTestCase):

    provider_subtype = 2


class CoSpaceDetailsViewTestCase(SupporthelpersTestCaseBase):

    def test_get(self):
        response = self.client.get(reverse('cospaces_details', args=[self.cospace_id]))
        self.assertEqual(response.status_code, 200)

    def test_post_remove_member_valid(self):
        data = {
            'remove_member': '1',
        }
        response = self.client.post(reverse('cospaces_details', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_clear_chat_valid(self):
        data = {
            'clear_chat': '1',
        }
        response = self.client.post(reverse('cospaces_details', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_add_member_valid(self):
        data = {
            'form_action': 'add_member',
            'add_member': 'test@example.org',
        }
        response = self.client.post(reverse('cospaces_details', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_add_members_all_valid(self):
        data = {
            'form_action': 'add_member',
            'members': 'all',
        }
        response = self.client.post(reverse('cospaces_details', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 302)


class CoSpaceFormViewTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('cospaces_edit', args=[self.cospace_id]))
        self.assertEqual(response.status_code, 200)

    def test_post_error(self):
        data = {
            'form_action': 'edit_cospace',
        }
        response = self.client.post(reverse('cospaces_edit', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 200)

    def test_post_valid(self):
        data = {
            'cospace': self.cospace_id,
            'title': 'Test',
            'uri': 'test',
            'call_id': '1234',
            'layout': 'telepresence',
            'password': '10203040',
            'group': '',
            'enable_chat': 'off',
            'lobby_pin': '3010045',
            'customer': self.customer.pk,
            'form_action': 'edit_cospace',
            'org_unit': 'Root > Sub',
        }
        response = self.client.post(reverse('cospaces_edit', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(CoSpaceUnitRelation.objects.get(provider_ref=self.cospace_id).unit)

    def test_post_remove_cospace_valid(self):
        data = {
            'remove_cospace': self.cospace_id,
        }
        response = self.client.post(reverse('cospaces_edit', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 302)


class CoSpaceFormViewRegularFormTestCase(CoSpaceFormViewTestCase):

    cospace_id = distinct_ids['cospace_with_user']


class CospaceInviteViewTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('cospaces_invite', args=[self.cospace_id]))
        self.assertEqual(response.status_code, 200)

    def test_post_invite_error(self):
        data = {
            'form_action': 'invite',
        }
        response = self.client.post(reverse('cospaces_invite', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_invite_valid(self):
        data = {
            'form_action': 'invite',
            'emails': 'test@example.org',
        }
        response = self.client.post(reverse('cospaces_invite', args=[self.cospace_id]), data)
        self.assertEqual(response.status_code, 302)


class CoSpaceFormNewViewTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('cospaces_add_old', args=[]))
        self.assertEqual(response.status_code, 200)

    def test_post_error(self):
        data = {
            'form_action': 'edit_cospace',
        }
        response = self.client.post(reverse('cospaces_add_old', args=[]), data)
        self.assertEqual(response.status_code, 200)

    def test_post_valid(self):
        data = {
            'title': 'Test',
            'uri': 'test',
            'call_id': '1234',
            'layout': 'telepresence',
            'password': '10203040',
            'group': '',
            'enable_chat': 'on',
            'lobby_pin': '3010045',
            'customer': self.customer.pk,
            'form_action': 'edit_cospace',
        }
        response = self.client.post(reverse('cospaces_add_old', args=[]), data)
        self.assertEqual(response.status_code, 302)


class CoSpaceListViewTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('cospaces_list', args=[]))
        self.assertEqual(response.status_code, 200)

    def test_export_excel(self):
        response = self.client.get(reverse('cospaces_list', args=[]) + '?export_to_excel=1&filter=1')
        self.assertEqual(response.status_code, 200)


class MeetingsTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('meetings', args=[]))
        self.assertEqual(response.status_code, 200)


class CallHandlerTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('call_handler', args=[self.call_id]))
        self.assertEqual(response.status_code, 200)

    def test_get_ajax(self):
        response = self.client.get(reverse('call_handler', args=[self.call_id]) + '?ajax=1')
        self.assertEqual(response.status_code, 200)

    def test_clustered(self):

        acano2 = self.acano
        acano2.pk = None
        acano2.save()
        self.acano.clustered.add(acano2)

        response = self.client.get(reverse('call_handler', args=[self.call_id]))
        self.assertEqual(response.status_code, 200)

    def test_clustered_ajax(self):

        acano2 = self.acano
        acano2.pk = None
        acano2.save()
        self.acano.clustered.add(acano2)

        response = self.client.get(reverse('call_handler', args=[self.call_id]) + '?ajax=1')
        self.assertEqual(response.status_code, 200)

    def test_post_valid(self):
        data = {
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_dialout_valid(self):
        data = {
            'uri': 'test@mindspacecloud.com',
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_hangup_valid(self):
        data = {
            'hangup': self.call_leg_id,
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_mute_valid(self):
        data = {
            'mute': '1',
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_unmute_valid(self):
        data = {
            'unmute': '1',
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_email_valid(self):
        data = {
            'recording_key': '1234',
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_recording_valid(self):
        data = {
            'recording_key': '1234',
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_layout_valid(self):
        data = {
            'layout': '1',
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_delete_call_valid(self):
        data = {
            'delete_call': '1',
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_clear_chat_valid(self):
        data = {
            'clear_chat': '1',
        }
        response = self.client.post(reverse('call_handler', args=[self.call_id]), data)
        self.assertEqual(response.status_code, 302)


class TenantViewTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('tenants', args=[]))
        self.assertEqual(response.status_code, 200)

    def test_post_error(self):
        data = {
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)

    def test_post_valid(self):
        data = {
            'name': 'test',
            'callbranding_url': 'http://test',
            'invite_text_url': 'http://test',
            'ivrbranding_url': 'http://tst',
            'create_customer': '1',
            'customer_ous': 'example',
            'create_ldap': '1',
            'ldap_server': '010c4c7d-ce57-4d04-b5db-edca20412534',
            'ldap_filter': '(uid=1)',
            'ldap_mapping': 'cf89d355-c4dd-47c3-af4a-afe08fa009f3',
            'ldap_base_dn': 'dc=example,dc=org',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_remove_error(self):
        data = {
            'post_action': 'remove',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_remove_valid(self):
        data = {
            'post_action': 'remove',
            'tenant': [],
            'callbranding': [],
            'ivrbranding': [],
            'ldapsource': [],
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 302)

    def test_post_update_callbrandning_error(self):
        data = {
            'post_action': 'update_callbranding',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)

    def test_post_update_callbrandning_valid(self):
        data = {
            'post_action': 'update_callbranding',
        }
        self.client.post(reverse('tenants', args=[]), data)
        # self.assertEqual(response.status_code, 302)  # TODO

    def test_sync(self):
        from customer.models import Customer
        customer_count = Customer.objects.all().count()

        def _count_and_reset_ids():
            nonlocal customer_count
            old_customer_count = customer_count
            customer_count = Customer.objects.all().count()
            Customer.objects.all().update(acano_tenant_id='something')
            return old_customer_count, customer_count

        data = {
            'post_action': 'sync',
            'sync-name_conflict': 'add_suffix',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)

        old_customer_count, new_customer_count = _count_and_reset_ids()
        self.assertGreater(new_customer_count, old_customer_count)

        # again -> ids are changed, add suffix due to conflict
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)

        old_customer_count, new_customer_count = _count_and_reset_ids()
        self.assertGreater(new_customer_count, old_customer_count)

        # skip -> no change
        data = {
            'post_action': 'sync',
            'sync-name_conflict': 'skip',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)

        old_customer_count, new_customer_count = _count_and_reset_ids()
        self.assertEqual(new_customer_count, old_customer_count)

        # ignore -> add duplicates
        data = {
            'post_action': 'sync',
            'sync-name_conflict': 'ignore',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)

        new_customer_count = Customer.objects.all().count()
        self.assertGreater(new_customer_count, customer_count)

        # add suffix -> add even more
        data = {
            'post_action': 'sync',
            'sync-name_conflict': 'add_suffix',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)

        self.assertGreater(new_customer_count, customer_count)
        customer_count = new_customer_count

        # merge -> no change when id is set
        data = {
            'post_action': 'sync',
            'sync-name_conflict': 'add_suffix',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(new_customer_count, customer_count)
        customer_count = new_customer_count

        # merge -> change when id is set
        Customer.objects.all().update(acano_tenant_id='', lifesize_provider=None)

        data = {
            'post_action': 'sync',
            'sync-name_conflict': 'add_suffix',
        }
        response = self.client.post(reverse('tenants', args=[]), data)
        self.assertEqual(response.status_code, 200)
        self.assertNotEquals('', Customer.objects.get(title='Test', lifesize_provider__isnull=False).acano_tenant_id)

        self.assertEqual(new_customer_count, customer_count)
        customer_count = new_customer_count


class RestClientTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('rest_client', args=[]) + '?url=coSpaces')
        self.assertEqual(response.status_code, 200)

    def test_post_valid(self):
        data = {
            'method': 'TEST',
            'data': '<test>value</test>',
        }
        response = self.client.post(reverse('rest_client', args=[]) + '?url=coSpaces', data)
        self.assertEqual(response.status_code, 200)


class RestClientPexipTestCase(RestClientTestCase):

    provider_subtype = 2


class MeetingListTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('meetings', args=[]))
        self.assertEqual(response.status_code, 200)


class MeetingDebugDetailsTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        response = self.client.get(reverse('meeting_debug_details', args=[self.meeting.pk]))
        self.assertEqual(response.status_code, 200)


class SettingsListTestCase(SupporthelpersTestCaseBase):
    def test_get(self):
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(reverse('onboard_settings'))
        self.assertEqual(response.status_code, 200)


