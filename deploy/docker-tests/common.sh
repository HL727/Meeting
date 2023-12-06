
log() {
    tput -T xterm setaf 3
    echo "$@" > /dev/stderr
    tput -T xterm sgr0
}

err() {
    tput -T xterm setaf 1
    echo ERROR: "$@" > /dev/stderr
    tput -T xterm sgr0
}

db() {
PGDATA=/etc/postgresql/11/main /usr/lib/postgresql/11/bin/postgres \
    -c fsync=off  \
    -c synchronous_commit=off \
    -c bgwriter_lru_maxpages=0 \
    -c full_page_writes=off \
    > /dev/null 2>&1 &
wait-for-it localhost:5432 || (echo 'No databse' ; exit 1 )
}
