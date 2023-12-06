#!/bin/bash
. /common.sh

ERROR=0

check_safety() {
    IGNORE="-i 39642 -i 42497 -i 42498"
    if ! safety check --cache --bare $IGNORE
    then
        safety check --cache --full-report $IGNORE
        ERROR=1
    fi
}

lint() {
if ! PYTHONPATH=. python -m flake8
then
    ERROR=1
fi
# PYTHONPATH=. python -m mypy .
}

log 'Checking packages'
check_safety

log 'Lint'
lint

exit $ERROR
