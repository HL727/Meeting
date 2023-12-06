import ipaddress

from django.http import HttpRequest
from django.test import TestCase, override_settings

from shared.real_ip import RealIPLookup, XForwardedForMiddleware


class TestRealIP(TestCase):
    def test_load(self):
        self.assertEqual(RealIPLookup(['1.2.3.4']).trusted_ips, [ipaddress.ip_network('1.2.3.4')])

    def test_no_valid_proxy(self):
        self.assertEqual(None, RealIPLookup([], None, '1.2.3.4, 4.5.6.7').get_real_ip())

    def test_real_ip(self):
        self.assertEqual(
            '1.2.3.4', str(RealIPLookup([], '1.2.3.4', '1.2.3.4, 4.5.6.7').get_real_ip())
        )

    def test_forwarded_for(self):
        self.assertEqual(
            '4.5.6.7',
            str(RealIPLookup(['5.6.7.8'], '5.6.7.8', '1.2.3.4, 4.5.6.7, 5.6.7.8').get_real_ip()),
        )

    def test_multiple_forwarded_for(self):
        self.assertEqual(
            '1.2.3.4',
            str(
                RealIPLookup(
                    ['5.6.7.8', '4.5.6.7'], '5.6.7.8', '1.2.3.4, 4.5.6.7, 5.6.7.8'
                ).get_real_ip()
            ),
        )


class TestRealIPMiddleware(TestCase):
    @override_settings(TRUSTED_IPS=['5.6.7.8', '4.5.6.7'])
    def test_middleware(self):

        request = HttpRequest()
        request.META = {
            'HTTP_X_FORWARDED_FOR': '1.2.3.4, 4.5.6.7, 5.6.7.8',
            'HTTP_X_REAL_IP': '5.6.7.8',
            'REMOTE_ADDR': '6.7.8.9',
        }

        XForwardedForMiddleware(lambda r: '').populate_real_ip(request)

        self.assertEqual(request.META['REMOTE_ADDR'], '1.2.3.4')
