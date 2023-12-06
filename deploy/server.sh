apt-get install nginx python-virtualenv git vim supervisor postgresql rabbitmq-server redis
apt-get build-dep python-psycopg2 python-ldap

grep -q 'universe' /etc/apt/sources.list || sudo add-apt-repository "deb http://se.archive.ubuntu.com/ubuntu $(lsb_release -sc) universe"
grep -q 'deb-src' /etc/apt/sources.list || sudo add-apt-repository "deb-src http://se.archive.ubuntu.com/ubuntu $(lsb_release -sc) main"

if ! grep -q 'Unattended-Upgrade::Remove-Unused-Dependencies "true"' /etc/apt/apt.conf.d/50unattended-upgrades
then
    echo 'Set Unattended-Upgrade::Remove-Unused-Kernel-Packages and Unattended-Upgrade::Remove-Unused-Dependencies to "true"'
    echo -n 'Continue? > '
    read x
    vim /etc/apt/apt.conf.d/50unattended-upgrades
fi


if ! grep -q conferencecenter /etc/passwd
then
    echo 'Adding user. Leave password empty'
    echo -n 'Continue? > '
    read x
    adduser conferencecenter
fi

mkdir -p /tmp/nginx
mkdir -p /etc/nginx/ssl/

[ -e /home/conferencecenter/ConferenceCenter ] || sudo -u conferencecenter virtualenv /home/conferencecenter/ConferenceCenter

[ -e /etc/nginx/ssl/dhparam.pem ] || openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048
[ -e /etc/nginx/ssl/nginx.key ] || openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/ssl/nginx.key -out /etc/nginx/ssl/nginx.crt

sudo -u conferencecenter /home/conferencecenter/ConferenceCenter/bin/python /home/conferencecenter/ConferenceCenter/conferencecenter/deploy/nginx_config.py --basename django --cert /etc/nginx/ssl/nginx.crt --key /etc/nginx/ssl/nginx.key > /tmp/nginx/mvms.conf
sudo -u conferencecenter /home/conferencecenter/ConferenceCenter/bin/python /home/conferencecenter/ConferenceCenter/conferencecenter/deploy/nginx_config.py --basename django_book --cert /etc/nginx/ssl/nginx.crt --key /etc/nginx/ssl/nginx.key > /tmp/nginx/mvms_book.conf

sudo -u conferencecenter /home/conferencecenter/ConferenceCenter/bin/python /home/conferencecenter/ConferenceCenter/conferencecenter/deploy/supervisor.py > /tmp/mvms.conf

echo 'Supervisor config is located in /tmp/mvms.conf'
echo 'Nginx config is located in /tmp/nginx/*.conf'

echo 'Copy files?'
echo -n ' yN > '
read x
if [ "$x" = "y" ]
then
    cp /tmp/mvms.conf /etc/supervisor/conf.d/
    cp /tmp/nginx/* /etc/nginx/sites-enabled/
fi
