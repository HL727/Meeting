
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCKER_DEVSERVER = os.environ.get('DOCKER_DEVSERVER') == '1'
VERBOSE = 'DEBUG'  # print debug info in console

HOSTNAME = '127.0.0.1:8002'
BASE_URL = 'http://127.0.0.1:8002/'

if True:  # Use live javascript ui, using `npm run serve`. Uses a lot of resources.
    INTERNAL_IPS = ('127.0.0.1', '172.17.0.1', '192.168.1.135')
else:
    # Use one off compilation.
    # Run npm run build and remove hash suffix from app and chunk-vendors in both
    # static/dist/js and static/dist/css
    """
    npm run build && for x in app chunk-vendors; do
        mv static/dist/js/$x.*.js static/dist/js/$x.js \
        && mv static/dist/css/$x.*.css static/dist/css/$x.css \
    ; done
    """
    INTERNAL_IPS = ()

# NOTE: You need to include a license in .env.
# Until signing requirements are in place you can add this to .env:
# FLAGS=core:enable_core,core:enable_epm,core:enable_analytics


if DOCKER_DEVSERVER and not os.environ.get('SQLITE'):
    pass
elif 1:  # sqlite
    DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
                }
    }
else:  # postgres. Run pip install psycopg2
    DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql_psycopg2',
                'NAME': '',
                'USER': '',

                'PASSWORD': '',
                'HOST': 'localhost',

                }
    }


ALLOW_SENTRY = False  # Don't actually send traceback, only log it

ALLOWED_HOSTS = ['*']
EPM_HOSTNAME = ''
EPM_PROXY_HOST = 'localhost'
EPM_PROXY_AUTHORIZED_KEYS = os.path.join(BASE_DIR, '..', 'authorized_keys')

COSPACE_CALLID_SYNC_CALLBACKS = []
ORCA = os.path.join(BASE_DIR, 'orca.sh')  # or http://orca-server:9091/

SEND_USER_STAT_URLS = [
        #'https://portaldomain/user_call_stats/\?key=shared key'
        ]

DEFAULT_ACANO_DOMAIN = 'example.org'

PORTAL_URL = 'https://portal.example.org'

PASSWORD_EXPIRE_FILES = [
        ('Example server', 'http://localhost/userlist.json'),
]

API_DOMAIN = 'book.eample.org'

# CELERY

ACTIVATE_CELERY = True
CELERY_TASK_ALWAYS_EAGER = False  # Set to True to run sceduled tasks directly instead of in background (Meeting must be unbooked manually)

if DOCKER_DEVSERVER:
    pass
elif 1:  # redis. Run pip install -U "celery[redis]"
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
else:  # rabbitmq.
    CELERY_BROKER_URL = 'amqp://guest@localhost//'
