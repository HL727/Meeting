import threading
from threading import Thread
from time import sleep

from django.conf import settings
from django.db import transaction
from django.test import TransactionTestCase

from shared.models import GlobalLock


class LockTestCase(TransactionTestCase):

    def setUp(self):
        self.wait_for_lock = threading.Lock()
        self.wait_for_release = threading.Lock()

        self.lock_thread = Thread(target=self._acquire)
        super().setUp()

    def tearDown(self):
        if self.wait_for_lock.locked():
            self.wait_for_lock.release()
        if self.wait_for_release.locked():
            self.wait_for_release.release()
        if self.lock_thread.is_alive():
            self.lock_thread.join(timeout=1)
        super().tearDown()

    def _acquire(self):

        with GlobalLock.locked('test'):
            self.wait_for_lock.release()
            self.wait_for_release.acquire(timeout=1)

        self.wait_for_release.release()

    def test_lock(self):

        self.wait_for_release.acquire()

        self.wait_for_lock.acquire()
        self.lock_thread.start()

        self.wait_for_lock.acquire(timeout=1)
        self.wait_for_lock.release()

        with transaction.atomic():
            is_locked = GlobalLock.is_locked('test')
        self.assertEqual(GlobalLock.is_locked('test'), True)
        self.assertEqual(is_locked, True)

        self.wait_for_release.release()
        self.lock_thread.join(timeout=1)

        with transaction.atomic():
            is_locked = GlobalLock.is_locked('test')
        self.assertEqual(is_locked, False)

        self.assertEqual(GlobalLock.is_locked('test'), False)
