"""
Django settings for conferencecenter project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import re
import sys
from datetime import timedelta

import urllib3
import environ

from license.validator import LicenseValidator

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env_real = environ.Env(
    DEBUG=(bool, False)
)

ENV_FILE = os.environ.get('ENV_FILE') or os.path.join(BASE_DIR, '.env')

if os.path.exists(ENV_FILE):
    env_real.read_env(ENV_FILE)


def env(key, default=None, extra=None):
    if extra:
        result = env_real(key, default, extra)
    else:
        result = env_real(key, default=default)
    return re.sub(r'(^|[^\\])\\\$', r'\1$', result) if isinstance(result, str) else result

# Use custom ca if provided in env
from . import custom_ca

custom_ca.update_ca()


urllib3.disable_warnings()

# Hostnames (defaults will be set at end of file)
ALLOWED_HOSTS = []
HOSTNAME = env('MAIN_HOSTNAME', '')
EPM_HOSTNAME = env('EPM_HOSTNAME', '')
API_HOSTNAME = env('API_HOSTNAME', '')

BOOK_EMAIL_HOSTNAME = env('BOOK_EMAIL_HOSTNAME', '')
BASE_URL = env('BASE_URL', '')  # calculated from hostname below
EPM_BASE_URL = env('EPM_BASE_URL', '')  # calculated from hostname below

# EPM proxy settings
EPM_PROXY_PORT_INTERVAL = [11000, 11500]
EPM_PROXY_SERVER_PORT = int(env('MIVIDAS_PROXY_PORT') or 2222)
EPM_PROXY_HOST = env('EPM_PROXY_HOST') or 'proxyserver'
EPM_PROXY_AUTHORIZED_KEYS = env('EPM_PROXY_AUTHORIZED_KEYS') or '/home/epmproxy/.ssh/authorized_keys'

# EPM Security
EPM_EVENT_CUSTOMER_SECRET = False  # Require customer secret key in event urls
EPM_EVENT_ENDPOINT_SECRET = False  # Require endpoint secret key in event urls
EPM_REQUIRE_PROXY_PASSWORD = False  # Require password for proxy registration
EPM_REQUIRE_PROXY_HASH = False  # Require hmac for all requests after reqistration
EPM_ENABLE_OBTP = True  # TODO license
EPM_ENABLE_CALENDAR = True  # TODO license

# Acano (Cisco Meeting Server) settings
MEETING_EXPIRE_ROOM = 4  # hours
ENABLE_AUTO_LDAP_SYNC = False
INITIAL_FORM_CALL_ID = ''  # prefilled in create cospace form
CLEAR_CHAT_INTERVAL = None  # minutes
SET_CALLID_TO_URIS = False

ACANO_TEMP_COSPACE_RANGE = env_real.json('ACANO_TEMP_COSPACE_RANGE', default='') or [100000000, 999999999]  # booked meetings will be randomized between these
ACANO_ALWAYS_CREATE_RECORDING_CALL = False

# Pexip settings
PEXIP_TEMP_COSPACE_RANGE = env_real.json('PEXIP_TEMP_COSPACE_RANGE', default='') or [100000000, 999999999]  # booked meetings will be randomized between these

# Statistics settings
ENABLE_ORGANIZATION = True
ENABLE_GROUPS = False
SEND_USER_STATS_URLS = []
INTERNAL_CALL_LEGS = []  # uri/name that match members of list will be regarded as internal legs and will be ignored
STATS_PHONE_DOMAINS = []
ORCA = 'http://orca:9091/'

# Invite message settings
INTERNAL_NUMBER_SERIES = env_real.json('INTERNAL_NUMBER_SERIES', default=[]) or []  # numbers within (min, max) is regarded as {internal_number} in invite messages
DEFAULT_MESSAGE_LOGO = ''
ADD_CUSTOM_MESSAGE_TYPES = []
ENABLE_PATIENT_MESSAGES = False
ENABLE_OLD_OUTLOOK_PLUGIN = False

# Scheduling API
REQUIRE_EXTENDED_KEY = env_real.bool('REQUIRE_EXTENDED_KEY', True)  # must be False for old outlook-plugin
EXTENDED_API_KEY = env('EXTENDED_API_KEY', '')
EMAIL_REQUIRE_EXTENDED_KEY = EXTENDED_API_KEY and env('EMAIL_REQUIRE_EXTENDED_KEY') in ('1', 'true', 'True', 'yes')

# Ldap sync settings
LDAP_USER_MATCHED_CALLBACK = 'organization.utils.update_cms_ldap_user'
LDAP_SET_ORGANISATION_FIELDS = []
LDAP_SERVER = env('LDAP_SERVER')
LDAP_SSL_INSECURE = env('LDAP_SSL_INSECURE')
LDAP_CERT_FILE = ''

AUTHENTICATION_BACKENDS = None

if env('LDAP_SERVER'):
    from ldapauth.settings import get_ldap_settings

    vars().update(get_ldap_settings(env))

# Log settings
LOG_DIR = '{}/cdrdata'.format(BASE_DIR)

# Celery settings
CELERY_BROKER_URL = env('CELERY_BROKER', '') or env('CELERY_BROKER_URL', '')
CELERY_DISABLE_BEAT = env('CELERY_DISABLE_BEAT', '') in ('1', 'true', 'True', 'yes')  # Use e.g. if multiple instances uses the same database
CELERY_ALWAYS_EAGER = None  # has been renamed
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TIME_LIMIT = 90  # Overridden for some tasks in conferencecenter.celery
CELERY_TASK_SOFT_TIME_LIMIT = CELERY_TASK_TIME_LIMIT - 40
ACTIVATE_CELERY = True
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "max_retries": 5,
    "interval_start": 0,
    "interval_step": 0.5,
    "interval_max": 2,
}

ASYNC_CDR_HANDLING = True  # Process cdr events from pexip/acano/endpoint using celery

# Misc settings
EXTENDED_API_KEYS = [k.strip() for k in env('EXTENDED_API_KEYS', '').split(',')]  # api keys with extra permissions
API_KEYS = [k.strip() for k in env('API_KEYS', '').split(',')]  # only used for initial installation
READONLY_CALL_SECRET = None  # url key to display list of ongoing calls
ALLOW_SENTRY = env('ALLOW_SENTRY') in (True, 'yes', '1', 'True', 'true')
TRUSTED_IPS = [net.strip() for net in (env('TRUSTED_IPS') or '').split(',') if net.strip()]

# Flags
LICENSE = LicenseValidator(
    env('LICENSE'),
    env_real.list('FLAGS', default='') or [],
    env_real.json('EXTRA_SETTINGS', default='') or {},
).parse_full()

FLAGS = LICENSE.flags
EXTRA_SETTINGS = LICENSE.settings

# Error log (overridden below)
SENTRY_DSN = 'https://5d2372bc75934420a2f21d2935862018:d073cab2a5744acb99feb8c2a05e952e@sentry.infra.mividas.com/2'

# Django settings:

DEBUG = env('DEBUG')
SECRET_KEY = env('SECRET_KEY', '')
LOGIN_REDIRECT_URL = '/'

ADMINS = ()

APPEND_SLASH = True

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
XFF_TRUSTED_PROXY_DEPTH = 1
XFF_HEADER_REQUIRED = False
XFF_CLEAN = False

CSRF_COOKIE_HTTPONLY = True

# Application definition

INSTALLED_APPS = (
    'whitenoise.runserver_nostatic',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.postgres',

    'bootstrap3',
    #'south',
    'reversion',
    'django_extensions',
    'debug_toolbar',
    'axes',
    'mptt',
    'rest_framework',
    'django_filters',
    'timezone_field',
    'drf_yasg',
    'django_celery_beat',

    'provider',
    'ext_sync',
    'ui_message',
    'cdrhooks',
    'supporthelpers',
    'statistics',
    'adminusers',
    'address',
    'emailbook',
    'json_api',
    'ldapauth',
    'organization',
    'recording',
    'calendar_invite',
    'endpoint',
    'endpointproxy',
    'endpoint_provision',
    'endpoint_data',
    'endpoint_backup',
    'endpoint_branding',
    'room_analytics',
    'numberseries',
    'debuglog',
    'tracelog',
    'shared',
    'meeting',
    'customer',
    'roomcontrol',
    'policy',
    'policy_auth',
    'policy_rule',
    'policy_script',
    'theme',
    'datastore',
    'api_key',
    'exchange',
    'msgraph',
    'license',
    'audit',
    'demo_generator',
    'shared.monkey_patch',
)

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
}

SWAGGER_SETTINGS = {
    'DEFAULT_AUTO_SCHEMA_CLASS': 'json_api.swagger.MividasAutoSchema',
    'DEFAULT_INFO': 'json_api.urls.swagger_info',
}

if AUTHENTICATION_BACKENDS is None:
    AUTHENTICATION_BACKENDS = [
        'axes.backends.AxesBackend',
        'django.contrib.auth.backends.ModelBackend',
    ]

AXES_DISABLE_ACCESS_LOG = True
AXES_FAILURE_LIMIT = 10
AXES_COOLOFF_TIME = timedelta(minutes=5)

MIDDLEWARE = (
    'shared.real_ip.XForwardedForMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'shared.middleware.DefaultLocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'audit.middleware.AuditLogMiddleware',
    'customer.middleware.CustomerMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'axes.middleware.AxesMiddleware',
)

ROOT_URLCONF = 'conferencecenter.urls'

WSGI_APPLICATION = 'conferencecenter.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
        'default': env_real.db('DATABASE_URL', 'psql://mividas_core:mividas_core@db/mividas_core'),
        }


if env('DATABASE_POOL_HOST'):
    DATABASES['direct'] = DATABASES['default']

    is_celery = any('celery' in arg for arg in sys.argv)

    DATABASES['default'] = {
        **DATABASES['default'],
        'HOST': env('DATABASE_POOL_HOST'),
        'PORT': 5432,
        'CONN_MAX_AGE': 10 if is_celery else 300,
        'DISABLE_SERVER_SIDE_CURSORS': True,
    }


CACHE_URL = env('CACHE_URL')
REDIS_HOST = env('REDIS_HOST')

if REDIS_HOST:
    if not CACHE_URL:
        CACHE_URL = 'redis://{}/1?ignore_exceptions=1&socket_connect_timeout=3'.format(REDIS_HOST)
    if not CELERY_BROKER_URL:
        CELERY_BROKER_URL = 'redis://{}/0'.format(REDIS_HOST)

if CACHE_URL:
    CACHES = {
        'default': env_real.cache_url_config(CACHE_URL),
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
    SESSION_CACHE_ALIAS = 'default'
    AXES_HANDLER = 'axes.handlers.cache.AxesCacheHandler'


CELERY_BROKER_URL = CELERY_BROKER_URL or 'amqp://mividas_core:mividas_core@rabbitmq/mividas_core'


# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'sv-se'
DEFAULT_LANGUAGE = env('DEFAULT_LANGUAGE', '') or 'en-us'

TIME_ZONE = env('TIMEZONE') or 'Europe/Stockholm'
CELERY_TIMEZONE = TIME_ZONE

LANGUAGES = (
    ('en', 'English'),
    ('sv', 'Swedish'),
)

USE_I18N = True

USE_L10N = True

USE_TZ = True

TEST_MODE = (sys.argv[0].endswith('manage.py') and 'test' in sys.argv) or 'pytest' in sys.argv

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

FILE_UPLOAD_PERMISSIONS = 0o644
BOOTSTRAP3 = {
    'jquery_url': '/site_media/static/js/jquery-1.11.0.min.js',
    'base_url': '/site_media/static/js/bootstrap/',
}

MEDIA_URL = '/site_media/media/'
MEDIA_ROOT = '%s/site_media/media' % BASE_DIR

STATIC_URL = '/site_media/static/'
STATIC_ROOT = '%s/site_media/static' % BASE_DIR

STATICFILES_DIRS = [
    '%s/static' % BASE_DIR,
]

EMAIL_CONFIG = env_real.email_url(
    'EMAIL_URL', default='smtp://localhost:25')

vars().update(EMAIL_CONFIG)

SERVER_EMAIL = env('SERVER_EMAIL', 'no-reply@{}'.format(HOSTNAME or 'localhost'))
DEFAULT_FROM_EMAIL = env('SERVER_EMAIL', 'no-reply@{}'.format(HOSTNAME or 'localhost'))

VUETIFY_THEMES = {}
'''
VUETIFY_THEMES = {
    'logo': 'url',
    'logoBackground': '#00ffff',
    'light': {
        'pink': '#ff1c1c',
        'orange': '#ff1c1c',
        'primary': '#ff1c1c',
    },
}
'''

# Version info

def _readfile(basename, default):
    try:
        with open(os.path.join(BASE_DIR, basename)) as fd:
            return fd.read().strip()
    except Exception:
        return default

VERSION = _readfile('version.txt', '')
COMMIT = _readfile('commit.txt', '')
if COMMIT:
    RELEASE = 'mividas-core@{}+{}'.format(VERSION.lstrip('v'), COMMIT).replace('@+', '')
else:
    RELEASE = ''


def get_override_template_dirs():
    result = []
    branding = os.path.join(BASE_DIR, 'templates_branding')
    if os.path.isfile(branding):
        with open(branding) as fd:
            result.append(os.path.join(BASE_DIR, 'templates', 'branding', fd.read().strip()))
    elif os.path.isdir(branding):
        result.append(branding)

    if os.path.exists(os.path.join(BASE_DIR, '..', 'opt', 'templates')):
        result.append(os.path.join(BASE_DIR, '..', 'opt', 'templates'))
    return result


TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [
                *get_override_template_dirs(),
                os.path.join(BASE_DIR, 'templates'),
            ],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                    'django.template.context_processors.static',
                    'shared.context_processors.menu',
                    'shared.context_processors.global_settings',
                    ],
                },
            },
        ]

SITE_ID = 1

LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]

try:
    from .local_settings import *  # noqa
except Exception:
    try:
        from mividascore.local_settings import *  # noqa
    except Exception:
        pass
try:
    from ..opt.settings import *  # noqa
except Exception:
    pass


ENABLE_CORE = LICENSE.has_flag('core:enable_core')
ENABLE_EPM = LICENSE.has_flag('core:enable_epm')
ENABLE_DEMO = LICENSE.has_flag('core:demo', 'core:enable_demo')


if 'core:portal_enable_patient_sip' in FLAGS:
    ENABLE_PATIENT_MESSAGES = True

if not DEBUG:
    CSRF_COOKIE_SECURE = True

HOSTNAME = HOSTNAME or 'core.localhost'
ALLOWED_HOSTS = (env('ALLOWED_HOSTS', '') or '*').split(',')

EPM_HOSTNAME = EPM_HOSTNAME or HOSTNAME or ALLOWED_HOSTS[0].strip('*') or 'epm-example.mividas.com'
API_HOSTNAME = API_HOSTNAME or HOSTNAME or ALLOWED_HOSTS[0].strip('*') or 'epm-example.mividas.com'
BOOK_EMAIL_HOSTNAME = BOOK_EMAIL_HOSTNAME or EPM_HOSTNAME

BASE_URL = BASE_URL or 'https://{}'.format(HOSTNAME)
EPM_BASE_URL = EPM_BASE_URL or 'https://{}'.format(EPM_HOSTNAME)

STATICFILES_STORAGE = 'conferencecenter.static.NotStrictCompressedManifestStaticFilesStorage'
WHITENOISE_KEEP_ONLY_HASHED_FILES = True
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_IMMUTABLE_FILE_TEST = r'^.+\.[0-9a-f]{8,12}\..+$'

if not SECRET_KEY:
    if not DEBUG:
        from warnings import warn
        warn('SECRET_KEY not set in env! FIX!')
    import hashlib
    SECRET_KEY = hashlib.md5(BASE_DIR.encode('utf-8')).hexdigest()

if CELERY_ALWAYS_EAGER is not None:  # backwards-compatibility
    CELERY_TASK_ALWAYS_EAGER = CELERY_ALWAYS_EAGER

TEST_RUNNER = 'xmlrunner.extra.djangotestrunner.XMLTestRunner'
TEST_OUTPUT_FILE_NAME = '/tmp/xunit.xml'

# If true then tests should be run against the live EWS instance
EXCHANGE_LIVE_TESTS = env('EXCHANGE_LIVE_TESTS')
# Run integration tests against local installation
RUN_INTEGRATION_TESTS = env('RUN_INTEGRATION_TESTS') in ('1', 'true')

VERBOSE = env('VERBOSE', '') in ('', '1', 'True', 'true', 'DEBUG')  # default true
VERBOSE_LEVEL = env('VERBOSE', '')
SYSLOG_SERVER = env('SYSLOG_SERVER') or ''

if VERBOSE:
    if ENABLE_EPM and ENABLE_CORE:
        facility = 'core_rooms'
    else:
        facility = 'core' if ENABLE_CORE else 'rooms'

    ignore = {'axes'} if TEST_MODE else set()
    apps = [app for app in INSTALLED_APPS if '.' not in app and app not in ignore]
    if EXCHANGE_LIVE_TESTS:
        apps.append('exchangelib')

    from .sentry import get_verbose_logging

    LOGGING = get_verbose_logging(
        apps,
        'DEBUG' if VERBOSE_LEVEL == 'DEBUG' else 'INFO',
        syslog_server=SYSLOG_SERVER,
        facility=facility,
    )


if DEBUG and not FLAGS:
    print(
        'No flags enabled. Maybe add settings to .env?\n'
        'FLAGS=core:enable_core,core:enable_epm,core:enable_analytics'
        'or \n'
        'LICENSE={"valid_until": "2022-10-07", "contact": null, "addons": [{"type": "epm:endpoint", "value": 100, "valid_from": "2022-02-09", "valid_until": "2023-02-09"}, {"type": "epm:endpoint_addon", "value": 50, "valid_from": "2022-02-09", "valid_until": "2023-02-09"}]}'
    )

if TEST_MODE or DEBUG:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


MIGRATION = ''
if 'makemigrations' in sys.argv:
    MIGRATION = 'make'
elif 'migrate' in sys.argv:
    MIGRATION = 'run'

IS_POSTGRES = 'postgre' in DATABASES['default']['ENGINE']

if 'runserver' in sys.argv:
    try:
        from django.core.management.commands.runserver import Command

        Command.default_port = 8006
    except Exception:
        pass

ENABLE_SENTRY = True  # default true, but with empty dsn. Error log uses sentry waypoints
if ENABLE_SENTRY:
    from .sentry import sentry_init

    sentry_init(
        {
            'dsn': SENTRY_DSN,
            'release': RELEASE,
            'server_name': HOSTNAME,
            'environment': HOSTNAME,
        },
        env,
    )
