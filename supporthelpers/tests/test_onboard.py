from django.contrib.auth.models import User
from django.http import HttpRequest
from django.urls import reverse

from customer.models import Customer
from provider.models.provider import Provider, Cluster, ClusterSettings
from provider.models.vcs import VCSEProvider
from conferencecenter.tests.base import ConferenceBaseTest, ThreadedTestCase
from shared.onboard import init_db
from supporthelpers.views.onboard import get_setup_view


class OnboardTestCase(ConferenceBaseTest):

    is_staff = False
    cluster: Cluster
    cluster_type: int

    def setUp(self):
        self.setup_mocks()
        super().setUp()
        init_db()

        response = self.client.post(reverse('onboard_setup'), {'customer_name': 'New installation'})
        self.assertEquals(response.status_code, 302)

    def _create_user(self, is_staff=None):
        if is_staff is None:
            is_staff = self.is_staff
        self.user = User.objects.create_user(username='test', password='test', is_staff=is_staff)
        return self.user


class ClusterOnboardMixin(OnboardTestCase):
    def setUp(self):
        super().setUp()

        data = {
            'title': 'New test cluster',
            'type': self.cluster_type,
            'main_sip_domain': '',
            'web_host': 'test.com',
            'phone_ivr': '010-123456',
            'static_vmr_number_start': 1000000,
            'static_vmr_number_stop': 8000000,
            'scheduled_vmr_number_start': 2000000,
            'scheduled_vmr_number_stop': 9000000,
        }
        response = self.client.post(reverse('onboard_cluster'), data)
        try:
            print(response.context['form'].errors)
        except Exception:
            pass
        self.assertEquals(response.status_code, 302)
        self.assertTrue(self.client.session.get('onboard_cluster'))
        self.cluster = Cluster.objects.get()
        self.assertEquals(self.cluster.title, 'New test cluster')

    def tearDown(self):
        super().tearDown()

        self.cluster.refresh_from_db()
        self.assertEquals(self.cluster.title, 'New test cluster')

        response = self.client.get(reverse('onboard_cluster') + '?skip=1')
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(get_setup_view(response.wsgi_request), 'onboard_cluster')
        self.assertTrue(reverse(get_setup_view(response.wsgi_request)))


class CallControlOnboardMixin(OnboardTestCase):
    def setUp(self):
        super().setUp()

        data = {
            'title': 'New test cluster',
            'type': self.cluster_type,
            'main_sip_domain': '',
            'web_host': 'test.com',
            'phone_ivr': '010-123456',
            'static_vmr_number_start': 1000000,
            'static_vmr_number_stop': 8000000,
            'scheduled_vmr_number_start': 2000000,
            'scheduled_vmr_number_stop': 9000000,
        }
        response = self.client.post(reverse('onboard_cluster_callcontrol'), data)
        try:
            print(response.context['form'].errors)
        except Exception:
            pass
        self.assertEquals(response.status_code, 302)
        self.assertTrue(self.client.session.get('onboard_cluster_callcontrol'))
        self.cluster = Cluster.objects.get()

        response = self.client.get(reverse('onboard_cluster') + '?skip=1')
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(get_setup_view(response.wsgi_request), 'onboard_cluster')
        self.assertTrue(reverse(get_setup_view(response.wsgi_request)))

    def tearDown(self):
        super().tearDown()

        self.cluster.refresh_from_db()
        self.assertEquals(self.cluster.title, 'New test cluster')

        response = self.client.get(reverse('onboard_cluster_callcontrol') + '?skip=1')
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(get_setup_view(response.wsgi_request), 'onboard_cluster')
        self.assertNotEqual(get_setup_view(response.wsgi_request), 'onboard_cluster_callcontrol')
        if getattr(self, 'is_staff', None):
            self.assertEqual(get_setup_view(response.wsgi_request), 'provider_dashboard')
        else:
            self.assertTrue(reverse(get_setup_view(response.wsgi_request)))


class UserOnboardTestCase(OnboardTestCase):

    is_staff = True

    def setUp(self):
        self._create_user()
        self.client.login(username=self.user.username, password='test')
        super().setUp()


class PasswordTestCase(OnboardTestCase):
    def setUp(self):
        super().setUp()
        self.client.get(reverse('onboard_cluster') + '?skip=1')
        self.client.get(reverse('onboard_cluster_callcontrol') + '?skip=1')

    def tearDown(self):
        super().tearDown()

        response = self.client.get(reverse('onboard_cluster_callcontrol') + '?skip=1')
        self.assertEqual(response.status_code, 302)
        if response.wsgi_request.user.is_staff:
            self.assertEqual(get_setup_view(response.wsgi_request), 'provider_dashboard')
        else:
            self.assertEqual(get_setup_view(response.wsgi_request), None)

    def test_password(self):
        data = {
            'new_password1': 'password1',
            'new_password2': 'password2',
        }
        response = self.client.post(reverse('onboard_fallback_password'), data)
        self.assertEquals(response.status_code, 200)
        self.assertFalse(self.client.login(username='mividas_fallback', password='password1'))

        data = {
            'new_password1': 'password1',
            'new_password2': 'password1',
        }
        response = self.client.post(reverse('onboard_fallback_password'), data)
        self.assertEquals(response.status_code, 302)
        self.assertTrue(self.client.login(username='mividas_fallback', password='password1'))


class ClusterOnboardTestCase(OnboardTestCase):
    def tearDown(self):
        """Make sure cluster main view works even after created objects"""
        self.test_get()
        super().tearDown()

    def test_get(self):
        response = self.client.get(reverse('onboard_cluster'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('onboard_cluster'))
        self.assertEqual(response.status_code, 200)

    def test_post_acano(self):
        self._test_post(Cluster.TYPES.acano_cluster)

    def test_post_pexip(self):
        self._test_post(Cluster.TYPES.pexip_cluster)
        self.assertTrue(Cluster.objects.get().pexip.default_customer)

    def _test_post(self, type):
        data = {
            'title': 'New test cluster',
            'type': type,
            'main_sip_domain': '',
            'web_host': 'test.com',
            'phone_ivr': '010-123456',
            'static_vmr_number_start': 1000000,
            'static_vmr_number_stop': 8000000,
            'scheduled_vmr_number_start': 2000000,
            'scheduled_vmr_number_stop': 9000000,
        }

        self.assertEqual(Cluster.objects.filter(type=type).count(), 0)

        response = self.client.post(reverse('onboard_cluster'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Cluster.objects.filter(type=type).count(), 1)

        cluster = Cluster.objects.get(type=type)
        self.assertEqual(cluster.get_cluster_settings().get_main_domain(), data['main_sip_domain'])
        self.assertTrue(Customer.objects.filter(lifesize_provider=cluster))


class StaffClusterOnboardTestCase(UserOnboardTestCase, ClusterOnboardTestCase):
    pass


class AcanoOnboardTestCase(ThreadedTestCase, ClusterOnboardMixin):

    cluster_type = Cluster.TYPES.acano_cluster

    def test_get(self):
        response = self.client.get(reverse('onboard_acano', args=[self.cluster.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_single(self):
        data = {
            'title': 'test',
            'ip': '127.0.0.1',
            'username': 'test',
            'password': 'test',
            'set_cdr': '1',
            'sync_tenants': '1',
        }
        response = self.client.post(reverse('onboard_acano', args=[self.cluster.id]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Provider.objects.filter(subtype=Provider.SUBTYPES.acano).count(), 1)
        self.assertEqual(Cluster.objects.filter(type=Provider.TYPES.acano_cluster).count(), 1)

        self.assertEqual(Customer.objects.exclude(acano_tenant_id='').count(), 1)

        self.assertEqual(self.client.session.get('onboard_cluster'), 'acano')

    def test_post_extend(self):

        self.test_post_single()

        data = {
            'form1-title': 'test',
            'form1-ip': '127.0.0.1',
            'form1-username': 'test',
            'form1-password': 'test',
            'form1-set_cdr': '1',
            'form1-sync_tenants': '1',
        }
        response = self.client.get(reverse('onboard_acano_extra', args=[self.cluster.id]))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse('onboard_acano_extra', args=[self.cluster.id]), data)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(Provider.objects.filter(subtype=Provider.SUBTYPES.acano).count(), 2)
        self.assertEqual(Cluster.objects.filter(type=Provider.TYPES.acano_cluster).count(), 1)

    def test_post_existing(self):

        data = {
            'title': 'test',
            'ip': '127.0.0.1',
            'username': 'test',
            'password': 'test',
            'cluster': self.cluster.pk,
        }
        for i in range(2):
            response = self.client.post(reverse('onboard_acano', args=[self.cluster.pk]), data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                Provider.objects.filter(subtype=Provider.SUBTYPES.acano).count(), i + 1
            )
            self.assertEqual(Cluster.objects.filter(type=Provider.TYPES.acano_cluster).count(), 1)


class StaffAcanoOnboardTestCase(UserOnboardTestCase, AcanoOnboardTestCase):
    pass


class VCSOnboardTestCase(CallControlOnboardMixin):

    cluster_type = Cluster.TYPES.vcs_cluster

    def test_get(self):
        response = self.client.get(reverse('onboard_vcs', args=[self.cluster.pk]))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('onboard_vcs', args=[self.cluster.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_single(self):

        data = {
            'title': 'test',
            'ip': '127.0.0.1',
        }
        response = self.client.post(reverse('onboard_vcs', args=[self.cluster.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(VCSEProvider.objects.count(), 1)
        self.assertEqual(Cluster.objects.filter(type=Provider.TYPES.vcs_cluster).count(), 1)

    def test_post_existing(self):
        data = {
            'title': 'test',
            'ip': '127.0.0.1',
            'cluster': self.cluster.pk,
        }
        for i in range(2):
            response = self.client.post(reverse('onboard_vcs', args=[self.cluster.pk]), data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(VCSEProvider.objects.count(), i + 1)
            self.assertEqual(Cluster.objects.filter(type=Provider.TYPES.vcs_cluster).count(), 1)


class StaffVCSOnboardTestCase(UserOnboardTestCase, VCSOnboardTestCase):
    pass


class PexipOnboardTestCase(ClusterOnboardMixin):

    cluster_type = Cluster.TYPES.pexip_cluster

    def test_get(self):
        response = self.client.get(reverse('onboard_pexip', args=[self.cluster.pk]))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('onboard_pexip', args=[self.cluster.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_single(self):
        data = {
            'title': 'test',
            'ip': '127.0.0.1',
            'username': 'test',
            'password': 'test',
            'create_event_policy': '1',
        }

        response = self.client.post(reverse('onboard_pexip', args=[self.cluster.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Provider.objects.filter(subtype=Provider.SUBTYPES.pexip).count(), 1)
        self.assertEqual(Cluster.objects.filter(type=Provider.TYPES.pexip_cluster).count(), 1)

        self.assertEqual(
            ClusterSettings.objects.filter(cluster=self.cluster, customer=None)[
                0
            ].dial_out_location,
            'Test',
        )

    def test_post_existing(self):
        data = {
            'title': 'test',
            'ip': '127.0.0.1',
            'cluster': self.cluster.pk,
            'create_event_policy': '1',
        }

        response = self.client.post(reverse('onboard_pexip', args=[self.cluster.pk]), data)
        self.assertEqual(response.status_code, 302)
        # Pexip has no support for multiple management nodes at the moment
        self.assertNotEqual(self.client.session.get('onboard_cluster'), 'pexip')


class StaffPexipOnboardTestCase(UserOnboardTestCase, PexipOnboardTestCase):
    pass
