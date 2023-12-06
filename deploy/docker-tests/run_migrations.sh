#!/bin/bash
. /common.sh

rabbitmq-server > /dev/null &
redis-server > /dev/null &
db &

export DATABASE_URL=postgresql://test:test@localhost/test
ERROR=0

make_migrations() {

if echo -n | python manage.py makemigrations  -v1 --dry-run | egrep 'Add|Remove|Create'
then
    err 'Missing migrations that add or removes fields!'
    ERROR=1
fi

}

migrate() {
if ! python manage.py upgrade_installation -v0
then
    err 'Migration errors'
    ERROR=1
fi
}

log 'Checking migrations (in background)'
make_migrations &
migrate
wait $!

killall postgres rabbitmq-server redis-server

exit $ERROR
