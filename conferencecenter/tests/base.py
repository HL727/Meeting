import json
import re
from collections import namedtuple
from os import environ
from typing_extensions import Literal

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils.timezone import now
from datetime import timedelta

from conferencecenter.tests.mock_data.mividas_stream import mividas_stream_post
from conferencecenter.tests.mock_data.quickchannel import quickchannel_post
from datastore.models.base import ProviderSync
from provider.ext_api.acano import AcanoAPI
from provider.ext_api.base import RecordingProviderAPI
from provider.ext_api.clearsea import ClearSeaAPI
from provider.ext_api.lifesize import LifeSizeAPI
from provider.ext_api.pexip import PexipAPI
from provider.ext_api.seevia import SeeviaAPI
from provider.ext_api.tandberg import TandbergAPI
from provider.ext_api.vcse import VCSExpresswayAPI
from recording.ext_api.quickchannel import QuickChannelAPI
from recording.ext_api.mividas_stream import MividasStreamAPI
from recording.ext_api.recvc import RecVcAPI
from recording.ext_api.videocenter import VideoCenterAPI
from .mock_data.acano import acano_post
from .mock_data.clearsea import clearsea_post
from .mock_data.lifesize import lifesize_post
from .mock_data.recording_base import recording_base_post
from .mock_data.recvc import recvc_post
from .mock_data.seevia import seevia_post
from .mock_data.tms import tandberg_post
from .mock_data.videocenter import videocenter_post
from .mock_data.vcse import vcse_post
from .mock_data.pexip import pexip_post
from .mock_data import state as mock_state
from . import mocker
from meeting.models import Meeting
from provider.models.provider_data import ClearSeaAccount
from provider.models.provider import Provider, VideoCenterProvider, SeeviaProvider
from provider.models.vcs import VCSEProvider
from customer.models import Customer, CustomerKey
from ext_sync.models import SeeviaSync
from ui_message.models import Message
from .mock_response import LoggedResponsesList, MockLogHandler

LIFESIZE_IP = environ.get('LIFESIZE_IP') or ''
ACANO_IP = environ.get('ACANO_IP') or ''
CLEARSEA_IP = environ.get('CLEARSEA_IP') or ''
VIDEOCENTER_IP = environ.get('VIDEOCENTER_IP') or ''

ADD_TIME_INDEX = 0

class ThreadedTestCase(TestCase):

    @classmethod
    def _databases_support_transactions(cls):
        return False


@override_settings(REQUIRE_EXTENDED_KEY=False, ENABLE_OLD_OUTLOOK_PLUGIN=True)
class ConferenceBaseTest(TestCase):

    provider_subtype = 1
    disable_clearsea = False
    only_internal = False
    rec_provider_type = 0

    _initialized = False

    mocker = mocker

    def setUp(self):
        self._initialized = False
        super().setUp()

    def _init(self):

        from endpoint.models import CustomerSettings

        if self._initialized:
            return  # TODO error?
        self._initialized = True

        global ADD_TIME_INDEX

        seconds = ADD_TIME_INDEX * 60
        ADD_TIME_INDEX += 1

        mock_state.url_state = 'initial'

        def _get_login(provider_name):
            data = getattr(settings, 'TEST_AUTH', {}).get(provider_name)

            if not data:
                return {'username': 'servertest', 'password': 'test'}

            return {'username': data['username'], 'password': data['password']}

        Customer.always_enable_external = False
        self.customer_shared_key = 'test_key'
        self.customer = Customer.objects.create(title='test', shared_key=self.customer_shared_key, meeting_add_seconds_before=seconds, meeting_add_seconds_after=seconds)

        c_settings = CustomerSettings.objects.get_for_customer(self.customer)
        c_settings.secret_key = 'ep123customerkey'
        c_settings.save()

        self.key2 = CustomerKey.objects.create(customer=self.customer, shared_key='example.org', active=True)

        self.lifesize = Provider.objects.create(type=0, ip=LIFESIZE_IP or '127.0.0.1', title='test_lifesize', is_standard=True, **_get_login('lifesize'))
        self.acano = Provider.objects.create(type=0, subtype=1, ip=ACANO_IP or '127.0.0.1', title='test_acano', is_standard=True, **_get_login('acano'))
        self.pexip = Provider.objects.create(type=0, subtype=Provider.SUBTYPES.pexip, ip='127.0.0.1', title='test_pexip', is_standard=True, **_get_login('pexip'))
        self.pexip.cluster.pexip.default_customer = self.customer
        self.pexip.cluster.pexip.save()
        self.clearsea = Provider.objects.create(type=1, ip=CLEARSEA_IP or '127.0.0.1', title='test_clearsea', is_standard=True, **_get_login('clearsea'))
        self.internal = Provider.objects.create(type=2, ip='127.0.0.1', title='test_internal', is_standard=True)
        self.external = Provider.objects.create(type=3, ip='127.0.0.1', title='test_external', is_standard=True)
        self.videocenter = VideoCenterProvider.objects.create(title='test', ip=VIDEOCENTER_IP or '127.0.0.1', hostname='127.0.0.1', recording_key='1234', **_get_login('videocenter'))

        self.recvc = VideoCenterProvider.objects.create(title='test', ip='127.0.0.1', hostname='127.0.0.1', recording_key='1234', **_get_login('recvc'), type=10)
        self.quickchannel = VideoCenterProvider.objects.create(title='test', ip='127.0.0.1', hostname='127.0.0.1', recording_key='1234', **_get_login('quickchannel'), type=20)
        self.mividas_stream = VideoCenterProvider.objects.create(title='test', ip='127.0.0.1', hostname='127.0.0.1', recording_key='1234', **_get_login('mividas_stream'), type=40)

        self.cms_native = VideoCenterProvider.objects.create(title='test', ip='127.0.0.1', hostname='127.0.0.1', recording_key='1234', type=30)

        self.cms_rtmp = VideoCenterProvider.objects.create(title='test', ip='127.0.0.1', hostname='127.0.0.1', recording_key='1234', type=15)

        self.vcse = VCSEProvider.objects.create(title='vcse test', hostname='vcs.example.org')

        self.seevia = SeeviaProvider.objects.create(title='test', is_test=True, username='test', password='test')
        SeeviaSync.objects.create(customer=self.customer, provider=self.seevia, base_dir='123', sync_minutes=10000)

        if getattr(self, 'provider_subtype', 1) == 1:
            self.customer.lifesize_provider = self.acano
        elif getattr(self, 'provider_subtype', 1) == 2:
            self.customer.lifesize_provider = self.pexip
        else:
            self.customer.lifesize_provider = self.lifesize

        self.customer.clearsea_provider = self.clearsea

        if getattr(self, 'rec_provider_type', 1) == 10:
            self.customer.videocenter_provider = self.recvc
        elif getattr(self, 'rec_provider_type', 1) == 20:
            self.customer.videocenter_provider = self.quickchannel
        elif getattr(self, 'rec_provider_type', 1) == 15:
            self.customer.videocenter_provider = self.cms_rtmp
        elif getattr(self, 'rec_provider_type', 1) == 30:
            self.customer.videocenter_provider = self.cms_native
        elif getattr(self, 'rec_provider_type', 1) == 40:
            self.customer.videocenter_provider = self.mividas_stream
        else:
            self.customer.videocenter_provider = self.videocenter

        self.customer.save()

        settings.TEST_MODE = True

        message_data = "\n".join('{}={}'.format(p.strip('{}'), p) for p in Message.get_placeholder_names())

        for code, _title in Message.TYPES:
            Message.objects.get_or_create(type=code, title='Msg %s' % code, content=message_data)

        self.setup_mocks()
        self._clear_cache()

    def mock_url(self, url, callback):
        self._mock_handler.add_response(url, callback)

    def setup_mocks(self):

        self._mock_requests = LoggedResponsesList()

        handler = MockLogHandler(self._mock_requests)
        self._mock_handler = handler

        if not LIFESIZE_IP:
            LifeSizeAPI.override_post = handler.decorate(lifesize_post)
        if not ACANO_IP:
            AcanoAPI.override_post = handler.decorate(acano_post)
        if not CLEARSEA_IP:
            ClearSeaAPI.override_post = handler.decorate(clearsea_post)
        if not VIDEOCENTER_IP:
            VideoCenterAPI.override_post = handler.decorate(videocenter_post)

        PexipAPI.override_post = handler.decorate(pexip_post)
        SeeviaAPI.override_post = handler.decorate(seevia_post)
        TandbergAPI.override_post = handler.decorate(tandberg_post)
        VCSExpresswayAPI.override_post = handler.decorate(vcse_post)
        QuickChannelAPI.override_post = handler.decorate(quickchannel_post)
        RecVcAPI.override_post = handler.decorate(recvc_post)
        MividasStreamAPI.override_post = handler.decorate(mividas_stream_post)
        RecordingProviderAPI.override_embed_callback_post = handler.decorate(recording_base_post)

        from endpoint.tests.mock_data import init as init_endpoint_mock

        init_endpoint_mock(handler.decorate)

    def _filter_requests(self, method):

        if isinstance(method, str):
            method = [method]

        result = []
        for req in self._mock_requests:
            if req.method in method:
                result.append(req)

        return result

    def _get_post_requests(self):
        return self._filter_requests('POST')

    def _get_change_requests(self):
        return self._filter_requests(['PUT', 'POST'])

    def assertSentAPIValueEquals(self, url: str, key: str, value, index=0):
        reqs = self._mock_requests.find_urls_all(url)
        self.assertTrue(reqs)
        if isinstance(reqs[index], dict):
            req_data = reqs[index]
        else:
            req_data = json.loads(reqs[index].data)
        if key not in req_data:
            self.fail('Key {} not in request data: {}'.format(key, req_data.keys()))
        self.assertEqual(req_data[key], value)

    def assertSentAPIValueNotEquals(self, url: str, key: str, value, index=0, allow_missing=True):
        reqs = self._mock_requests.find_urls_all(url)
        if not reqs and allow_missing:
            return
        self.assertTrue(reqs)
        if isinstance(reqs[index], dict):
            req_data = reqs[index]
        else:
            req_data = json.loads(reqs[index].data)
        if key not in req_data and not allow_missing:
            self.fail('Key {} not in request data: {}'.format(key, req_data.keys()))
        self.assertNotEquals(req_data.get(key), value)

    def _clear_cache(self):
        ProviderSync.check_has_cached_values.cache.clear()
        import customer.models as customer
        customer.clear_cache(self)
        import statistics.models as statistics
        statistics.clear_cache(self)
        from datastore.utils import pexip
        pexip.theme_cache.clear()
        pexip.tenant_cache.clear()

        from endpoint import models as endpoint

        endpoint.clear_cache(self)

    def _book_meeting(self, **data):

        kwargs = dict(
            title='test',
            ts_start=now(),
            ts_stop=now() + timedelta(hours=1),
            customer=self.customer,
            provider=self.customer.get_provider(),
            creator='test',
            creator_ip='127.0.0.1',
            backend_active=True,
            provider_ref='61170',
            provider_secret='asdf',
            provider_ref2='22f67f91-1948-47ec-ad4f-4793458cfe0c' if self.customer.get_provider().is_acano else 123,
        )
        kwargs.update(data)

        meeting = Meeting.objects.create(**kwargs)

        if self.customer.clearsea_provider_id:
            external_provider = self.customer.clearsea_provider
            if meeting.should_book_external_client:
                meeting.book_external(external_provider)

        if kwargs.get('backend_active'):
            meeting.activate()

        return meeting

    def switch_provider(self, new_provider: Literal['acano', 'pexip']):
        if new_provider == 'acano':
            self.customer.lifesize_provider = self.acano
            self.customer.save()
        elif new_provider == 'pexip':
            self.customer.lifesize_provider = self.pexip
            self.customer.save()
        else:
            raise KeyError(new_provider)

        self.api = self._get_api()

    def set_url_state(self, state):
        mock_state.url_state = state

    def compare_data(self, meeting):

        if not meeting.backend_active or (LIFESIZE_IP == CLEARSEA_IP == ''):
            return

        info = meeting.api.get_info(meeting)
        if meeting.provider.type == Provider.TYPES.lifesize and meeting.provider.subtype == 0:
            lines = info.get('buffer', '').split('\n')
            values = dict(line.strip().split(':', 1) for line in lines if ':' in line)

            self.assertEqual(values.get('DTSTART'), meeting.ts_start_lifesize_corrected)
            self.assertEqual(values.get('DTEND'), meeting.ts_stop_lifesize_corrected)
            self.assertEqual(values.get('RRULE', ''), meeting.recurring)
            self.assertEqual(values.get('EXDATE', ''), meeting.recurring_exceptions_corrected)

        external = meeting.get_external_account()
        if external:
            info = external.provider.get_api(meeting.customer).get_info(external)
            self.assertEqual(external.backend_active, info.get('enabled'))
            if external.backend_active:
                self.assertEqual(len(info['endpoints']), 1)
                self.assertEqual(info['endpoints'][0]['dialString'], meeting.dialstring)

    def tearDown(self):

        for c in ClearSeaAccount.objects.filter(backend_active=True):
            c.provider.get_api(c.meeting.customer).unbook(c)
        for m in Meeting.objects.filter(backend_active=True):
            m.api.unbook(m)

        for p in Provider.objects.all():

            if p.is_acano and hasattr(self, 'customer'):
                p.get_api(self.customer).unbook_cached_values()


class AcanoProviderBaseTest(ConferenceBaseTest):

    provider_subtype = Provider.SUBTYPES.acano


class PexipProviderBaseTest(ConferenceBaseTest):

    provider_subtype = Provider.SUBTYPES.pexip
