import django
import os.path

os.environ.setdefault('FLAGS', 'core:enable_core,core:enable_epm,core:enable_analytics')
os.environ.setdefault(
    'LICENSE',
    '{"valid_until": "2024-10-07", "contact": null, "addons": [{"type": "epm:endpoint", "value": 100, "valid_from": "2022-02-09", "valid_until": "2023-02-09"}, {"type": "epm:endpoint_addon", "value": 50, "valid_from": "2022-02-09", "valid_until": "2023-02-09"}]}',
)

from .settings import *  # noqa


class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        if django.VERSION[0] < 2:
            return 'notmigrations'
        return None


if os.environ.get('MIGRATIONS') != '1':
    MIGRATION_MODULES = DisableMigrations()

PASSWORD_HASHERS = (
            'django.contrib.auth.hashers.MD5PasswordHasher',
            )

CELERY_TASK_ALWAYS_EAGER = True
DEBUG = False
INTERNAL_IPS = ()
TIME_ZONE = 'UTC'
USE_TZ = True

if os.path.exists('/tmp/'):
    TMP = '/tmp'
else:
    TMP = os.path.dirname(os.path.abspath(__file__))

if os.environ.get('SQLITE') == '1':
    DATABASES = {
        # 'default': {
        #     'ENGINE': 'django.db.backends.sqlite3',
        #     'NAME': os.path.join(TMP, 'core_test_db.sqlite3'),
        #     'OPTIONS': {
        #         'timeout': 20,
        #     },
        # }
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'mividas',
            'USER': 'wingching',

            'PASSWORD': 'wingching',
            'HOST': 'localhost',
        }
    }
    IS_POSTGRES = False
