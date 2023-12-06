from os import environ, path
import sys

sys.path.append('..')
sys.path.append('.')

environ.setdefault('DJANGO_SETTINGS_MODULE', 'conferencecenter.settings')
from django.template import Template, Context

#django.setup()
from django.conf import settings

root = settings.BASE_DIR.rstrip('/')
venv = path.dirname(root)

home = environ.get('HOME').rstrip('/')
log_root = '{}/logs/'.format(home)

sock_root = '{}/sock/'.format(home)

template = Template('''
[program:conferencecenter_django]
command={{ venv }}/bin/gunicorn conferencecenter.wsgi --log-file {{ log_root }}django.log --workers 5 -t 120 -b unix:{{ sock_root }}django.sock
directory={{ root }}
environment=PYTHONPATH='{{ root }}:{{ root }}/../',LANG='en_US.UTF-8',LC_ALL='en_US.UTF-8'
user=conferencecenter
group=www-data
autostart=true
autorestart=true

[program:conferencecenter_book]
command={{ venv }}/bin/gunicorn conferencecenter.wsgi_book --log-file {{ log_root }}django_book.log --workers 5 -t 120 -b unix:{{ sock_root }}django_book.sock
directory={{ root }}
environment=PYTHONPATH='{{ root }}:{{ root }}/../',LANG='en_US.UTF-8',LC_ALL='en_US.UTF-8'
user=conferencecenter
group=www-data
autostart=true
autorestart=true


[program:conferencecenter_celery]
command={{ venv }}/bin/celery worker -B -c 4 -A provider.tasks --loglevel=info -f {{ log_root }}/celery.log --pidfile={{ sock_root }}celery.pid  -Ofair
directory={{ root }}
environment=PYTHONPATH='{{ root }}:{{ root }}/../',LANG='en_US.UTF-8',LC_ALL='en_US.UTF-8'
user=conferencecenter
group=www-data
autostart=true
autorestart=true
''')

print((template.render(Context(locals()))))
