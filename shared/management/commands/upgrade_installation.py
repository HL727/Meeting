from threading import Lock
from time import sleep

from shared.models import Installation
from django.core.management.commands import migrate
from django.db import DatabaseError
from django.conf import settings
from django.core.cache import cache

from shared.onboard import init_db


class Command(migrate.Command):
    help = "Upgrade installation - run migrations and create default objects"

    _lock_instance = None

    def _log(self, s):
        if not settings.TEST_MODE:
            print(s)

    def _lock(self):
        lock = Lock()  # TODO any value?
        if hasattr(cache, 'lock'):
            try:
                lock = cache.lock('core_migration', timeout=180)
            except Exception:
                lock = cache.lock('core_migration')

        if lock.acquire(blocking=False):
            self._lock_instance = lock
            return lock

    def _release(self):
        if not self._lock_instance:
            return
        try:
            return self._lock_instance.release()
        except Exception as e:
            self._log(str(e))
            return False

    def handle(self, *args, **options):

        try:
            list(Installation.objects.all().only('id'))
            first_install = False
        except DatabaseError:
            first_install = True

        if not self._lock():
            self._log('Upgrade check already running')
            return False
        self._log('Starting upgrade check')

        try:
            super().handle(*args, **options)
            self._init_db(first_install=first_install)
        except Exception:
            self._release()
            if not settings.TEST_MODE:
                sleep(10)  # dont spam errors
            raise
        self._release()

    def _init_db(self, first_install=False):
        last = Installation.objects.all().order_by('-ts_started').first()
        Installation.objects.create(parent=last)

        init_db(first_install=first_install)
