set -e

export DOCKER_BUILDKIT=1

dockerfiles() {
    cat deploy/docker/Dockerfile-base deploy/docker/Dockerfile-ui deploy/docker/Dockerfile deploy/docker/Dockerfile-test
}

dockerfiles | docker build --target mividas-core-base-test -t mividas-core-base-test -f - .
dockerfiles | docker build --target mividas-core-js-base -t mividas-core-js-base -f - .

cd `dirname $0`/..

exec docker-compose -p mividas-core --project-directory `pwd` \
    -f deploy/docker-run/docker-compose.dev.yml "${@:-up}"
