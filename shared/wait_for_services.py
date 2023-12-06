import os
import sys
from time import sleep, monotonic

os.environ['ALLOW_SENTRY'] = '0'


def run(timeout=60, migration_extra=60):

    expires = monotonic() + timeout

    from django.conf import settings

    if settings.REDIS_HOST:
        if not wait_for_redis(expires):
            return False

    if not wait_for_db(expires):
        return False

    if not wait_for_celery(expires):
        return False

    if os.environ.get('MIGRATE') or 'migrate' in sys.argv or 'upgrade_installation' in sys.argv:
        print('Proceeding to database migrations')
        return True

    if not wait_for_db_migrations(expires + migration_extra):
        return False

    return True


def check_time(expires: float):
    if expires < monotonic():
        return False
    return True


def wait_for_db(expires: float):

    print('Waiting for database server')

    while True:

        if not check_time(expires):
            print('Giving up waiting for DB')
            return

        try:
            from django.db import connection

            connection.cursor()
        except Exception:
            print('Database has not started yet')
            sleep(0.5)
            continue
        else:
            print('Database is up')
            return True


def wait_for_db_migrations(expires: float):
    from shared.models import Installation

    print('Waiting for database migrations')

    while True:

        if not check_time(expires):
            print('Giving up waiting for DB migrations')
            return

        try:
            Installation.objects.all()[0]
        except Exception:
            print('Database has not been initialized')
            sleep(0.5)
            continue
        else:
            print('Database is up')
            return True


def wait_for_redis(expires: float):
    from django_redis import get_redis_connection

    print('Waiting for redis')

    while True:

        if not check_time(expires):
            print('Giving up waiting for redis')
            return

        try:
            conn = get_redis_connection()
            conn.set('test', b'test', 1)
            if conn.get('test') != b'test':
                raise ValueError()
        except Exception:
            sleep(0.5)
        else:
            print('Redis is up')
            return True


def wait_for_celery(expires: float):
    print('Waiting for celery')

    while True:
        if not check_time(expires):
            print('Giving up waiting for celery')
            return

        try:
            from celery.app.control import Inspect
            from conferencecenter.celery import app

            Inspect(app=app).stats()
        except Exception:
            sleep(0.5)
        else:
            print('Celery is up')
            return True


if __name__ == '__main__':
    import django

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conferencecenter.settings')
    django.setup()
    if not run():
        sys.exit(1)
