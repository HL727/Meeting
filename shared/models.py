import threading
from collections import defaultdict
from contextlib import contextmanager
from threading import Thread
from time import sleep

from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction, DatabaseError, IntegrityError, connection
from django.utils.timezone import now
from jsonfield import JSONField


class Installation(models.Model):

    version = models.CharField(max_length=100)
    ts_started = models.DateTimeField(default=now)

    parent = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)


class CeleryStatus(models.Model):

    id = models.SmallIntegerField(default=1, primary_key=True, unique=True)
    ts_last_check = models.DateTimeField(default=now)


class GlobalOptions(models.Model):

    OPTIONS = [
        (x, x)
        for x in [
            'skip_fallback_user',
            'skip_cluster',
            'skip_cluster_callcontrol',
            'skip_acano',
            'skip_vcs',
        ]
    ]

    option = models.CharField(choices=OPTIONS, max_length=100)
    value = JSONField()


process_lock = defaultdict(threading.Lock)
local_locks = threading.local()


@contextmanager
def run_locked(name, wait=True):
    lock = None
    locked = False
    locked_names = local_locks.__dict__.setdefault('locked_names', set())

    if name in locked_names and wait:
        raise ValueError('Lock %s is already acquired in this thread.' % name)

    try:
        if hasattr(cache, 'lock'):
            lock = cache.lock(name, timeout=180)
            locked = lock.acquire(blocking=wait)
        elif 'sqlite' in settings.DATABASES['default']['ENGINE']:
            lock = process_lock[name]
            locked = lock.acquire(blocking=wait)
        else:
            if settings.TEST_MODE and connection.in_atomic_block and connection.savepoint_ids:
                raise ValueError('Test is running without thread support. Use ThreadedTestCase')
            lock = DatabaseLock(name)
            locked = lock.acquire(blocking=wait)

        if not locked:
            raise DatabaseError('Already locked')

        locked_names.add(name)
        yield
    finally:
        try:
            if locked:
                locked_names.discard(name)
                lock.release()
        except Exception:
            pass


class DatabaseLock:
    """
    Quick and dirty lock using database row. Should be replaced with redis lock instead.
    """

    def __init__(self, name):
        self.name = name
        self.blocking = None
        self.db_error = None
        self.process_lock = process_lock[name]
        self.wait_for_row = threading.Lock()
        self.keep_row_locked = threading.Lock()
        self.thread = Thread(target=self.acquire_row)

    def acquire(self, blocking=True):

        if not self.process_lock.acquire(blocking=blocking):
            return False

        self.db_error = None

        self.keep_row_locked.acquire()

        self.blocking = blocking
        self.init_row()

        self.wait_for_row.acquire()
        self.thread.start()  # will release self.wait_for_row when db row lock is in place (or error)
        with self.wait_for_row:
            pass  # done

        if self.db_error:
            self.keep_row_locked.release()
            if self.thread.is_alive():
                self.thread.join()
            return False

        return True

    def release(self):

        self.keep_row_locked.release()
        try:
            if self.thread.is_alive():
                self.thread.join()
        finally:
            if self.process_lock.locked():
                self.process_lock.release()

        if self.db_error:
            raise self.db_error

    def init_row(self):
        try:
            GlobalLock.objects.filter(name=self.name).first() or GlobalLock.objects.get_or_create(
                name=self.name
            )
        except IntegrityError:
            pass

    def acquire_row(self):

        with transaction.atomic():
            self.init_row()
            try:
                lock = (
                    GlobalLock.objects.select_for_update(of=('self',), nowait=not self.blocking)
                    .filter(name=self.name)
                    .get()
                )
            except DatabaseError as e:
                self.db_error = e
                return
            except Exception:
                self.process_lock.release()
                raise
            finally:
                self.wait_for_row.release()

            lock.ts_last_start = now()
            lock.ts_last_end = None
            lock.save()

            with self.keep_row_locked:  # wait until this lock is release()
                pass

            lock.ts_last_end = now()
            lock.save()


class GlobalLock(models.Model):

    name = models.CharField(max_length=100, unique=True)
    ts_last_start = models.DateField(null=True)
    ts_last_end = models.DateField(null=True)

    @staticmethod
    def locked(name, wait=True):
        return run_locked(name, wait=wait)

    @staticmethod
    def is_locked(name):

        try:
            with run_locked(name, wait=False):
                return False
        except DatabaseError:
            return True
