from os import environ, path
import sys
from time import sleep

sys.path.append('..')
sys.path.append('.')

environ.setdefault('DJANGO_SETTINGS_MODULE', 'conferencecenter.settings')
from django.template import Template, Context

#django.setup()
from django.conf import settings

import argparse

parser = argparse.ArgumentParser(description='Create config')
parser.add_argument('--basename', nargs='?',
                    help='basename of sock and log')
parser.add_argument('--cert', nargs='?',
                    help='Public key')
parser.add_argument('--key', nargs='?',
                    help='Public key')

args = parser.parse_args()


root = settings.BASE_DIR.rstrip('/')
domains = settings.ALLOWED_HOSTS

name = args.basename or 'django'

home = environ.get('HOME').rstrip('/')
log_root = '{}/logs/'.format(home)
sock = '{}/sock/{}.sock'.format(home, name)
log_name = '{}.log'.format(name)

cert_public = args.cert or '/etc/nginx/ssl/{}/cert.crt'.format(domains[0])
cert_private = args.key or '/etc/nginx/ssl/{}/cert.key'.format(domains[0])

dhparam = None
for name in ['dhparam.pem', 'dhparams.pem']:
    cur = '/etc/nginx/ssl/{}'.format(name)
    if path.exists(cur):
        dhparam = cur


errors = []
if not dhparam:
    errors.append('No dhparam exists, run openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048')

if not path.exists(cert_public):
    errors.append('public key {} does not exist'.format(cert_public))
if not path.exists(cert_private):
    errors.append('private key {} does not exist'.format(cert_private))

if errors:
    for e in errors:
        sys.stderr.write(e + '\n')
    sleep(2)


template = Template('''
server {
        listen 443;

        root {{root}};
        access_log  {{log_root}}access_{{ log_name }};
        error_log {{log_root}}error_{{ log_name }};
server_name {{domains|join:" "}};

ssl on;
ssl_certificate {{cert_public}};
ssl_certificate_key {{cert_private}};
ssl_dhparam {{dhparam}};

ssl_session_timeout 5m;

ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
ssl_ciphers 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-DSS-AES128-GCM-SHA256:kEDH+AESGCM:ECDHE-RSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA:ECDHE-ECDSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-DSS-AES128-SHA256:DHE-RSA-AES256-SHA256:DHE-DSS-AES256-SHA:DHE-RSA-AES256-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA256:AES128-SHA:AES256-SHA:AES:CAMELLIA:DES-CBC3-SHA:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!aECDH:!EDH-DSS-DES-CBC3-SHA:!EDH-RSA-DES-CBC3-SHA:!KRB5-DES-CBC3-SHA';
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;

#add_header Strict-Transport-Security "max-age=31536000; includeSubdomains";


        location /site_media/ {
                if ($query_string) { expires max; }
                break;
        }

    location /Acano/branding/ {
        alias /home/branding/default/;
    }

        location ~ ^deploy/ { internal; }
        location ~ /.git/ { internal; }


        location /admin_media/ {
                alias /usr/lib/pymodules/python2.7/django/contrib/admin/media/;
        }
        location /admin/media/ {
                alias /usr/lib/pymodules/python2.7/django/contrib/admin/media/;
        }
        location /robots.txt {
                alias /home/robots.txt;
        }
        location / {
                proxy_pass_header Server;
                proxy_set_header Host $http_host;
                proxy_redirect off;
fastcgi_param REMOTE_ADDR $remote_addr;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Scheme $scheme;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_connect_timeout 10;
                proxy_read_timeout 90;
                proxy_pass http://unix:{{sock}};
        }
# what to serve if upstream is not available or crashes

}
''')

print((template.render(Context(locals()))))
