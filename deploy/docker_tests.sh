set -e

TARGET="$(pwd)"

if [ -z "$CI" ]
then
rm -rf build/
git clone . build
cd build
fi

export DOCKER_BUILDKIT=1
export BASE_DOCKER_TAG="${CI_COMMIT_BRANCH:-${CI_COMMIT_TAG:-latest}}"

WHAT="${1:-all}"

NUMBER="${CI_JOB_ID:-${BITBUCKET_BUILD_NUMBER:-unknown}}"

dockerfiles() {
    cat deploy/docker/Dockerfile-base deploy/docker/Dockerfile-ui deploy/docker/Dockerfile deploy/docker/Dockerfile-test
}

if ! [ "$NOBUILD" = "1" ]
then
dockerfiles | docker build --target mividas-core-test \
	--cache-from=${CI_REGISTRY_IMAGE}/mividas-core-js-base:$BASE_DOCKER_TAG \
	--cache-from=${CI_REGISTRY_IMAGE}/mividas-core-js-base:master \
	--build-arg BUILDKIT_INLINE_CACHE=1 \
	-t mividas-core-test:$NUMBER -f - .
dockerfiles | docker build --target mividas-core-ui-test \
	--cache-from=${CI_REGISTRY_IMAGE}/mividas-core-js-base:$BASE_DOCKER_TAG \
	--cache-from=${CI_REGISTRY_IMAGE}/mividas-core-js-base:master \
	--build-arg BUILDKIT_INLINE_CACHE=1 \
    -t mividas-core-ui-test:$NUMBER -f - .
fi

[ -z "$CI" ] && rm -rf build

if [ "$WHAT" = 'build' ]
then
    exit 0
fi

ERROR=''

if [ "$WHAT" = 'lint' -o "$WHAT" = 'all' ]
then
    if ! docker run --rm --init mividas-core-ui-test:$NUMBER npx eslint -c .eslintrc-build.json   'js-ui/**/*.vue' 'js-ui/**/*.js'
    then
        ERROR="$ERROR jslint"
    fi
    if ! docker run --rm --init mividas-core-test:$NUMBER /run_lint.sh
    then
        ERROR="$ERROR pythonlint"
    fi
fi

if [ "$WHAT" = 'security' -o "$WHAT" = 'all' ]
then
    docker pull aquasec/trivy:latest
    # backend
    dockerfiles | docker build --target mividas-core-vulnscan -t mividas-core-vulnscan:$NUMBER --build-arg "TRIVY_FAIL=0" -f - .
    if ! docker run --name "mividas-core-vulnscan-$NUMBER" mividas-core-vulnscan:$NUMBER ; then
        ERROR="$ERROR security"
    fi
    docker cp "mividas-core-vulnscan-$NUMBER":/gl-container-scanning-report.json "$TARGET/"trivy-scanning-report-backend.json || true
    docker rm -f "mividas-core-vulnscan-$NUMBER"
    # ui
    dockerfiles | docker build --target=mividas-core-ui-vulnscan -t mividas-core-ui-vulnscan:$NUMBER -f - .
    if ! docker run --name "mividas-core-ui-vulnscan-$NUMBER" mividas-core-ui-vulnscan:$NUMBER ; then
        ERROR="$ERROR security"
    fi
    docker cp "mividas-core-ui-vulnscan-$NUMBER":/gl-container-scanning-report.json "$TARGET/"trivy-scanning-report-ui.json || true
    docker rm -f "mividas-core-vulnscan-$NUMBER"
fi

if [ "$WHAT" = 'migrations' -o "$WHAT" = 'all' ]
then
    if ! docker run --rm --init mividas-core-test:$NUMBER /run_migrations.sh
    then
        ERROR="$ERROR migrations"
    fi
fi

if [ "$WHAT" = 'test' -o "$WHAT" = 'exchange' -o "$WHAT" = 'all' ]
then
docker rm mividas-core-test-$NUMBER || true
if ! docker run \
    --init \
    --name mividas-core-test-$NUMBER \
    -e EMAIL_URL=${EMAIL_URL:-dummymail://} \
    -e CELERY_BROKER_URL=amqp://guest@localhost// \
    mividas-core-test:$NUMBER /run_tests.sh "$WHAT"
then
    ERROR="$ERROR test"
fi
docker cp mividas-core-test-$NUMBER:/tmp/coverage.xml "$TARGET/" || true
docker cp mividas-core-test-$NUMBER:/tmp/xunit.xml "$TARGET/" || true
docker rm -f mividas-core-test-$NUMBER
fi

if ! [ -z "$ERROR" ]
then
    echo 'ERRORS: ' $ERROR
    exit 1
fi
