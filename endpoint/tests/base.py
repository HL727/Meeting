import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils.timezone import now
from rest_framework.test import APITestCase

from conferencecenter.tests.base import ConferenceBaseTest
from customer.models import Customer
from endpoint import consts
from endpoint.models import CustomerSettings, Endpoint


class EndpointBaseTest(APITestCase, ConferenceBaseTest):

    manufacturer = consts.MANUFACTURER.CISCO_CE

    def _init(self):
        self.endpoint = Endpoint.objects.create(
            title='endpoint1',
            customer=self.customer,
            ip='192.168.1.117',
            username='admin',
            password='CurrentPassword',
            mac_address='11:22:33:44:55:66' if self.manufacturer != consts.MANUFACTURER.POLY_HDX else '00:E0:DB:10:97:85',
            serial_number='12345',
            connection_type=consts.CONNECTION.DIRECT,
            manufacturer=self.manufacturer,
        )
        self.endpoint_auth_error = Endpoint.objects.create(
            title='auth_error',
            customer=self.customer,
            ip='192.168.1.119',
            username='admin',
            hostname='auth_error',
            connection_type=consts.CONNECTION.DIRECT,
            mac_address='11:22:33:44:55:77',
            serial_number='1234a',
            manufacturer=self.manufacturer,
        )
        self.endpoint_response_error = Endpoint.objects.create(
            title='response_error',
            customer=self.customer,
            ip='192.168.1.118',
            username='admin',
            hostname='response_error',
            connection_type=consts.CONNECTION.DIRECT,
            mac_address='11:22:33:44:55:88',
            serial_number='1234b',
            manufacturer=self.manufacturer,
        )

    def _init_related(self):
        from endpoint_backup.models import EndpointBackup
        from endpoint_branding.models import EndpointBrandingFile, EndpointBrandingProfile
        from endpoint_provision.models import EndpointFirmware, EndpointProvision, EndpointTask
        from endpointproxy.models import EndpointProxy

        EndpointFirmware.objects.create(version='test', model=self.endpoint.product_name,
                                                   customer=self.customer, manufacturer=self.endpoint.manufacturer,
                                                   file=ContentFile(b'', 'test.bin'))

        branding_profile = EndpointBrandingProfile.objects.create(customer=self.customer, name='test')
        branding_profile.files.create(type=EndpointBrandingFile.BrandingType.Background, file=ContentFile('test', name='test'))

        provision = EndpointProvision.objects.create(customer=self.customer)
        EndpointTask.objects.create(endpoint=self.endpoint, customer=self.customer, provision=provision)
        EndpointBackup.objects.create(endpoint=self.endpoint, customer=self.customer)
        EndpointProxy.objects.create(customer=self.customer, name='test')


    def setUp(self):
        super().setUp()
        super()._init()
        self._init()
        self.user = User.objects.create_user(username='test', password='test')
        self.client.login(username=self.user.username, password='test')

        self.customer2 = Customer.objects.create(title='test2')
        # make sure existing self.customer is used by default
        self.assertEquals(Customer.objects.values_list('id', flat=True).order_by('title').first(), self.customer.pk)

        CustomerSettings._override_localtime = None

    def tearDown(self):
        CustomerSettings._override_localtime = None
        super().tearDown()

    def book_endpoint_meeting(self, endpoint, external_uri=None):
        from meeting.models import Meeting

        meeting = Meeting.objects.create(
            customer=self.customer,
            backend_active=True,
            provider=self.external,
            ts_start=now(),
            ts_stop=now() + timedelta(hours=1),
            settings=json.dumps({'external_uri': external_uri or 'sip:test@example.org'}),
            room_info=json.dumps([{'endpoint': endpoint.email_key}]),
        )
        meeting.connect_endpoints()
        self.assertTrue(meeting.endpoints.all())
        return meeting
