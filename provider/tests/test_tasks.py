from datetime import timedelta

from django.conf import settings
from django.utils.timezone import now

from conferencecenter.tests.base import ConferenceBaseTest, ThreadedTestCase
from provider import tasks


class ProviderTaskBaseTest:

    def setUp(self):
        self._init()
        super().setUp()


class ProviderTaskTest(ProviderTaskBaseTest, ConferenceBaseTest):

    def test_sync_cospace_callids(self):
        tasks.sync_cospace_callids()

    def test_store_provider_load(self):
        tasks.store_provider_load()

    def test_clean_stale_data(self):
        tasks.clean_stale_data()

    def test_clean_ghost_calls(self):
        tasks.clean_ghost_calls()

    def test_clear_old_chat_messages(self):
        self.acano.cluster.acano.clear_chat_interval = 10
        self.acano.cluster.acano.save()
        tasks.clear_old_call_chat_messages()

    def send_email_for_cospace(self):
        tasks.send_email_for_cospace(self.customer.pk, '123')

    def test_unbook_expired(self):
        tasks.unbook_expired()

    def test_remove_acano_schedule_cospace(self):

        from provider.models.acano import CoSpace

        CoSpace.objects.create(
            provider=self.acano.cluster,
            provider_ref='cde999',
            customer=self.customer,
            ts_auto_remove=now() + timedelta(hours=1),
        )
        self.assertFalse(self._mock_requests.find_url('DELETE coSpaces/abc123'))

        cospace = CoSpace.objects.create(
            provider=self.acano.cluster,
            provider_ref='abc123',
            customer=self.customer,
            ts_auto_remove=now() - timedelta(hours=1),
        )
        if not settings.CELERY_TASK_ALWAYS_EAGER:
            tasks.remove_schedule_pexip_cospace(
                cospace.provider_ref, cospace.ts_auto_remove.isoformat()
            )

        self.assertTrue(self._mock_requests.find_url('DELETE coSpaces/abc123'))

    def test_remove_pexip_schedule_cospace(self):
        from provider.models.pexip import PexipSpace

        PexipSpace.objects.create(
            cluster=self.pexip.cluster,
            external_id='567',
            customer=self.customer,
            ts_auto_remove=now() + timedelta(hours=1),
        )
        self.assertFalse(self._mock_requests.find_url('DELETE configuration/v1/conference/1234/'))

        cospace = PexipSpace.objects.create(
            cluster=self.pexip.cluster,
            external_id='1234',
            customer=self.customer,
            ts_auto_remove=now() - timedelta(hours=1),
        )

        if not settings.CELERY_TASK_ALWAYS_EAGER:
            tasks.remove_schedule_pexip_cospace(
                cospace.external_id, cospace.ts_auto_remove.isoformat()
            )

        self.assertTrue(self._mock_requests.find_url('DELETE configuration/v1/conference/1234/'))

    def test_set_cospace_stream_urls(self):
        tasks.set_cospace_stream_urls()

    def test_send_call_stats(self):
        tasks.send_call_stats()


class SyncTaskTest(ProviderTaskBaseTest, ConferenceBaseTest):
    def test_sync_acano_users(self):
        tasks.sync_acano_users()

    def test_cache_ldap_data(self):
        tasks.cache_ldap_data()

    def test_update_status_file(self):
        tasks.update_status_file()

    def test_check_celery(self):
        tasks.check_celery()


class StatisticsTaskTest(ProviderTaskBaseTest, ConferenceBaseTest):

    def test_update_vcs_statistics(self):
        tasks.update_vcse_statistics()

    def test_update_pexip_statistics(self):
        tasks.update_pexip_statistics()


class ThreadedStatisticsTaskTest(ProviderTaskBaseTest, ThreadedTestCase, ConferenceBaseTest):
    def test_recount_stats(self):
        tasks.recount_stats()

    def test_update_provider_statistics(self):
        tasks.update_provider_statistics(self.pexip.pk)



class RecordingTaskTest(ConferenceBaseTest):
    def setUp(self):
        self._init()
        super().setUp()

    def test_check_recordings(self):
        tasks.check_recordings()
