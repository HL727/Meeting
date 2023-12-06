import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from traceback import print_exception, print_exc

from cacheout import memoize

from conferencecenter import settings
from endpoint.ext_api.base import EndpointProviderAPI
from endpoint.ext_api.poly_base import PolyBaseProviderAPI
from endpoint.models import Endpoint, CustomerSettings

# Default, do not change
ENABLE_ALL = ('studio_x', 'group', 'hdx', 'trio')
ENABLE_CHECKS_ALL = (
    'check_status',
    'check_dial_info',
    'check_passive_status',
    'check_events_status',
    'check_addressbook_status',
    'check_dial',
    'check_set_dial_info',
    'check_add_ca_certificates',
    'check_default_call_control_arguments',
    'check_set_password',
    'check_passive_configuration',
)

# Active checks:

ENABLE = ENABLE_ALL
ENABLE_CHECKS = ENABLE_CHECKS_ALL


class LiveTestBase:
    def __init__(self):

        self.correct_values = {}
        self.endpoints = []
        self.apis = []
        self._logs = []
        self._exceptions = []
        self._requests = {}

        EndpointProviderAPI.request_callback = self.request_callback

    def _get_api(self, manufacturer: Endpoint.MANUFACTURER):
        endpoint = Endpoint.objects.filter(manufacturer=manufacturer).first()
        if endpoint:
            return endpoint.get_api()
        print('Missing Endpoint for manufacturer', manufacturer.name, file=sys.stderr)
        return None

    def _add_endpoint(self, api, **kwargs):

        if api is None:
            return

        self.endpoints.append(api.endpoint)
        self.apis.append(api)
        self.correct_values[api.endpoint.pk] = kwargs

    def log(self, *args, ex=None):
        self._logs.append(args)
        if ex:
            self._exceptions.append(ex)
        print(*args, file=sys.stderr)

    def request_callback(self, api, url, response=None):
        data = response.text if response else str(sys.exc_info())
        try:
            if response:
                data = response.json()
        except ValueError:
            pass

        target = self._requests.setdefault(api.__class__.__name__, {}).setdefault(url, [])
        if data not in target:
            target.append(data)

    def print_all_logs(self):

        if self._exceptions:
            print('\n\nExceptions\n=========\n', file=sys.stderr)
            for ex in self._exceptions:
                print_exception(type(ex), ex, ex.__traceback__, limit=5)

        print('\n\n\nResults\n============\n', file=sys.stderr)
        for log in self._logs:
            print(*log, file=sys.stderr)

        log_filename = os.path.join(settings.BASE_DIR, 'last_url_results')
        print(
            '\n\nSaving all API data to:\n{}.json\n  and\n{}.python'.format(
                log_filename, log_filename
            )
        )
        with open(log_filename + '.json', 'w') as fd:
            json.dump(self._requests, fd, indent=2)
        with open(log_filename + '.py', 'w') as fd:
            fd.write(str(self._requests))

    def run(self):

        with ThreadPoolExecutor(10) as pool:
            pool.map(self.run_api, self.apis)

        self.print_all_logs()

    def run_api(self, api):

        for check_fn_name, name in [
            ('check_status', 'get_status'),
            ('check_dial_info', 'get_dial_info'),
            ('check_passive_status', 'get_passive_status'),
            ('check_events_status', 'check_events_status'),
            ('check_addressbook_status', 'get_addressbook_status'),
            ('check_dial', 'call_control'),
            ('check_set_dial_info', 'set_dial_info'),
            ('check_default_call_control_arguments', 'call_control'),
            ('check_add_ca_certificates', 'add_ca_certificates'),
            ('check_set_password', 'set_password'),
            ('check_passive_configuration', 'passive_configuration'),
        ]:
            if check_fn_name not in ENABLE_CHECKS:
                print('Ignoring {} for {}'.format(check_fn_name, api.__class__.__name__))
                continue

            try:
                fn = getattr(self, check_fn_name)
                fn(api)
            except Exception as e:
                self.log(
                    '{} Exception {}'.format(api.__class__.__name__, name),
                    e,
                    ex=e,
                )
                traceback.print_exc(limit=3)

    def _compare(self, api, section, data, correct, required, require_only_included=False):

        for k, v in correct.items():
            if data.get(k) != v:
                self.log(
                    '{} {} key {} is wrong. "{}" != "{}"'.format(
                        api.__class__.__name__, section, k, data.get(k), v
                    ),
                )

        for k in required:
            if k in data and require_only_included:
                continue

            if not data.get(k):
                self.log(
                    '{} {} key {} is not set'.format(
                        api.__class__.__name__,
                        section,
                        k,
                    )
                )


class LiveTest(LiveTestBase):
    def __init__(self):
        super().__init__()

        _get_api = self._get_api
        self.studio_x = _get_api(Endpoint.MANUFACTURER.POLY_STUDIO_X)
        self.group = _get_api(Endpoint.MANUFACTURER.POLY_GROUP)
        self.hdx = _get_api(Endpoint.MANUFACTURER.POLY_HDX)
        self.trio = _get_api(Endpoint.MANUFACTURER.POLY_TRIO)
        self.cisco = _get_api(Endpoint.MANUFACTURER.CISCO_CE)

        if 'studio_x' in ENABLE:
            self._add_endpoint(
                self.studio_x,
                dial_info={
                    'sip_proxy': 'video.mividas.com',
                    'h323_gatekeeper': 'video.mividas.com',
                    'sip': 'polyx30@video.mividas.com',
                    'h323': 'polyx30@video.mividas.com',
                    'name': 'StudioX30-5D98DAFC',
                    'sip_display_name': 'StudioX30',
                },
            )
        if 'group' in ENABLE:
            self._add_endpoint(
                self.group,
                dial_info={
                    'sip_proxy': 'video.mividas.com',
                    'h323_gatekeeper': 'video.mividas.com',
                    'sip': 'poly500@video.mividas.com',
                    'h323': 'poly500@video.mividas.com',
                    'name': 'Mividas Poly Group 500',
                },
            )
        if 'hdx' in ENABLE:
            self._add_endpoint(
                self.hdx,
                dial_info={
                    'sip_proxy': 'video.mividas.com',
                    'h323_gatekeeper': 'video.mividas.com',
                    'sip': 'hdx9000@video.mividas.com',
                    'h323': 'hdx9000@video.mividas.com',
                    'name': 'TestHDX9000',
                },
            )
        if 'trio' in ENABLE:
            self._add_endpoint(
                self.trio,
                dial_info={
                    'sip_proxy': 'video.mividas.com',
                    'h323_gatekeeper': 'video.mividas.com',
                    'sip': 'trio8800@video.mividas.com',
                    'h323': 'trio8800@video.mividas.com',
                    'name': 'Mividas Trio 8800',
                },
            )
        if 'cisco' in ENABLE:
            self._add_endpoint(
                self.cisco,
                dial_info={
                    'sip_proxy': 'video.mividas.com',
                    'sip': 'labrat@video.mividas.com',
                },
            )

    @memoize(15)
    def get_status_data(self, api):
        return api.get_status_data()

    @memoize(15)
    def get_configuration_data(self, api):
        return api.get_configuration_data()

    def check_status(self, api: PolyBaseProviderAPI):

        status = api.get_status(self.get_status_data(api))

        correct = self.correct_values[api.endpoint.id].get('status') or {}
        required = ('uptime', 'status', 'volume')

        self._compare(api, 'get_status', status, correct, required)

        api.endpoint.update_status(status_data=self.get_status_data(api), raise_exceptions=True)

    def check_dial_info(self, api: PolyBaseProviderAPI):

        dial_info = api.get_dial_info(configuration_data=self.get_configuration_data(api))
        correct = self.correct_values[api.endpoint.id].get('dial_info') or {}
        required = ('sip', 'name', 'sip_proxy')

        self._compare(api, 'dial_info', dial_info, correct, required)

    def check_passive_status(self, api: PolyBaseProviderAPI):

        passive_status = api.get_passive_status(configuration_data=self.get_configuration_data(api))
        correct = self.correct_values[api.endpoint.id].get('passive_status') or {}
        required = ('url', 'is_set')

        self._compare(api, 'get_passive_status', passive_status, correct, required)

    def check_passive_configuration(self, api: PolyBaseProviderAPI):

        configurations = api.get_passive_provisioning_configuration()

        c_settings = CustomerSettings.objects.get_for_customer(api.customer)

        required = {
            'server_name': settings.EPM_HOSTNAME,
            'customer_key': c_settings.secret_key,
            'endpoint_key': api.endpoint.event_secret_key,  # TODO applicable for all models?
        }

        for conf in configurations:
            for k, r in list(required.items()):
                if conf['value'] and r in str(conf['value']):
                    required.pop(k)
                    break

        for k, r in required.items():
            self.log(
                '{} value {} ("{}") missing from passive configuration'.format(
                    api.__class__.__name__,
                    k,
                    r,
                )
            )

    def check_events_status(self, api: PolyBaseProviderAPI):

        event_status = api.check_events_status(
            status_data=self.get_status_data(api), delay_fix=True
        )

        assert event_status in (True, False)

    def check_addressbook_status(self, api: PolyBaseProviderAPI):

        passive_status = api.get_addressbook_status(
            configuration_data=self.get_configuration_data(api)
        )
        correct = self.correct_values[api.endpoint.id].get('events_status') or {}
        required = ('is_set', 'id')

        self._compare(
            api,
            'get_addressbook_status',
            passive_status,
            correct,
            required,
            require_only_included=True,
        )

    def check_dial(self, api: PolyBaseProviderAPI):

        api.call_control('dial', 'testcall@video.mividas.com')
        sleep(5)

        status = api.get_status()
        correct = {
            'in_call': 'testcall@video.mividas.com',
            'status': Endpoint.STATUS.IN_CALL,
        }

        required = ('call_duration',)

        try:
            self._compare(api, 'call_control', status, correct, required)
        finally:
            api.call_control('disconnect')

    def check_set_dial_info(self, api: PolyBaseProviderAPI):

        dial_info = api.get_dial_info(configuration_data=self.get_configuration_data(api))
        saved_dial_info = api.get_saved_dial_info()

        matching = {k: v for k, v in dial_info.items() if saved_dial_info.get(k) == v}

        assert matching

        api.set_dial_info(matching)

    def check_default_call_control_arguments(self, api: PolyBaseProviderAPI):
        """Should not raise exceptions"""

        error = None

        for args in (
            ('answer',),
            ('reject',),
            ('mute', False),
            ('mute', True),
        ):
            try:
                api.call_control(*args)
            except Exception as ex:
                error = error or ex
                print_exc()

        if error:
            raise error

    def check_add_ca_certificates(self, api: PolyBaseProviderAPI):

        api.add_ca_certificates(
            '''-----BEGIN CERTIFICATE-----
MIIFYDCCBEigAwIBAgIQQAF3ITfU6UK47naqPGQKtzANBgkqhkiG9w0BAQsFADA/
MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNVBAMT
DkRTVCBSb290IENBIFgzMB4XDTIxMDEyMDE5MTQwM1oXDTI0MDkzMDE4MTQwM1ow
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwggIiMA0GCSqGSIb3DQEB
AQUAA4ICDwAwggIKAoICAQCt6CRz9BQ385ueK1coHIe+3LffOJCMbjzmV6B493XC
ov71am72AE8o295ohmxEk7axY/0UEmu/H9LqMZshftEzPLpI9d1537O4/xLxIZpL
wYqGcWlKZmZsj348cL+tKSIG8+TA5oCu4kuPt5l+lAOf00eXfJlII1PoOK5PCm+D
LtFJV4yAdLbaL9A4jXsDcCEbdfIwPPqPrt3aY6vrFk/CjhFLfs8L6P+1dy70sntK
4EwSJQxwjQMpoOFTJOwT2e4ZvxCzSow/iaNhUd6shweU9GNx7C7ib1uYgeGJXDR5
bHbvO5BieebbpJovJsXQEOEO3tkQjhb7t/eo98flAgeYjzYIlefiN5YNNnWe+w5y
sR2bvAP5SQXYgd0FtCrWQemsAXaVCg/Y39W9Eh81LygXbNKYwagJZHduRze6zqxZ
Xmidf3LWicUGQSk+WT7dJvUkyRGnWqNMQB9GoZm1pzpRboY7nn1ypxIFeFntPlF4
FQsDj43QLwWyPntKHEtzBRL8xurgUBN8Q5N0s8p0544fAQjQMNRbcTa0B7rBMDBc
SLeCO5imfWCKoqMpgsy6vYMEG6KDA0Gh1gXxG8K28Kh8hjtGqEgqiNx2mna/H2ql
PRmP6zjzZN7IKw0KKP/32+IVQtQi0Cdd4Xn+GOdwiK1O5tmLOsbdJ1Fu/7xk9TND
TwIDAQABo4IBRjCCAUIwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAQYw
SwYIKwYBBQUHAQEEPzA9MDsGCCsGAQUFBzAChi9odHRwOi8vYXBwcy5pZGVudHJ1
c3QuY29tL3Jvb3RzL2RzdHJvb3RjYXgzLnA3YzAfBgNVHSMEGDAWgBTEp7Gkeyxx
+tvhS5B1/8QVYIWJEDBUBgNVHSAETTBLMAgGBmeBDAECATA/BgsrBgEEAYLfEwEB
ATAwMC4GCCsGAQUFBwIBFiJodHRwOi8vY3BzLnJvb3QteDEubGV0c2VuY3J5cHQu
b3JnMDwGA1UdHwQ1MDMwMaAvoC2GK2h0dHA6Ly9jcmwuaWRlbnRydXN0LmNvbS9E
U1RST09UQ0FYM0NSTC5jcmwwHQYDVR0OBBYEFHm0WeZ7tuXkAXOACIjIGlj26Ztu
MA0GCSqGSIb3DQEBCwUAA4IBAQAKcwBslm7/DlLQrt2M51oGrS+o44+/yQoDFVDC
5WxCu2+b9LRPwkSICHXM6webFGJueN7sJ7o5XPWioW5WlHAQU7G75K/QosMrAdSW
9MUgNTP52GE24HGNtLi1qoJFlcDyqSMo59ahy2cI2qBDLKobkx/J3vWraV0T9VuG
WCLKTVXkcGdtwlfFRjlBz4pYg1htmf5X6DYO8A4jqv2Il9DjXA6USbW1FzXSLr9O
he8Y4IWS6wY7bCkjCWDcRQJMEhg76fsO3txE+FiYruq9RUWhiF1myv4Q6W+CyBFC
Dfvp7OOGAN6dEOM4+qR9sdjoSYKEBpsr6GtPAQw4dy753ec5
-----END CERTIFICATE-----'''.strip()
        )

    def check_set_password(self, api):

        api.set_password('admin', api.endpoint.password)


def run():

    LiveTest().run()
