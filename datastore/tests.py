
from conferencecenter.tests.base import ConferenceBaseTest
from datastore import models
from datastore.utils.acano import sync_all_acano
from datastore.utils.pexip import sync_all_pexip


class DataStoreTestCase(ConferenceBaseTest):

    def setUp(self):
        self._init()
        super().setUp()

    def _check_acano_count(self):
        self.assertEqual(models.acano.CoSpace.objects.count(), 1)
        self.assertEqual(models.acano.User.objects.count(), 3)
        self.assertEqual(models.acano.CoSpaceAccessMethod.objects.count(), 1)

    def test_sync_acano(self):
        sync_all_acano(self.acano)
        self._check_acano_count()
        sync_all_acano(self.acano)
        self._check_acano_count()

    def test_sync_acano_incremental(self):
        sync_all_acano(self.acano, incremental=True)
        self._check_acano_count()

    def _check_pexip_count(self):
        self.assertEqual(models.pexip.Conference.objects.count(), 2)
        self.assertEqual(models.pexip.EndUser.objects.count(), 2)
        self.assertEqual(models.pexip.ConferenceAlias.objects.count(), 2)

    def test_sync_pexip(self):
        sync_all_pexip(self.pexip)
        self._check_pexip_count()
        sync_all_pexip(self.pexip)
        self._check_pexip_count()

    def test_sync_pexip_incremental(self):
        sync_all_pexip(self.pexip, incremental=True)
        self._check_pexip_count()
