#!/bin/sh
env > /tmp/.env
echo -n > /tmp/domains
[ -n "$BOOK_EMAIL_HOSTNAME" ] && echo "$BOOK_EMAIL_HOSTNAME" >> /tmp/domains
[ -n "$MAIN_HOSTNAME" ] && echo "$MAIN_HOSTNAME" >> /tmp/domains
[ -n "$EPM_HOSTAME" ] && echo "$EPM_HOSTAME" >> /tmp/domains
[ -n "`cat /tmp/domains`" ] || echo '_' > /tmp/domains

cat /tmp/domains

exec /usr/sbin/smtpd -d
