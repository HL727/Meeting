#!/bin/bash
. /common.sh

rabbitmq-server > /dev/null &
redis-server > /dev/null &
db

export DATABASE_URL=postgresql://test:test@localhost/test

ERROR=0


tests() {
export DATABASE_URL=postgresql://test:test@localhost/test_django
export MIGRATIONS=1  # catch field errors
if coverage run manage.py test --settings=conferencecenter.settings_test endpoint endpoint_provision
then

    log 'Collecting coverage report'

    coverage combine
    ( coverage xml -o /tmp/coverage.xml && sed -i "s~<source>/code</source>~<source>./</source>~" /tmp/coverage.xml ) &
    coverage report
    wait $!

else
    err 'Failed tests!'
    ERROR=1
fi
}

test_exchange() {
    EXCHANGE_LIVE_TESTS=1 python manage.py test --settings=conferencecenter.settings_test --parallel 2 exchange msgraph
}

log 'Running tests'
if [ "$1" = "exchange" ]
then
    test_exchange
else
    tests
fi

killall postgres rabbitmq-server redis-server

exit $ERROR
