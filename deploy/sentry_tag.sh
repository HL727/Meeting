set -e

export SENTRY_ORG=mividas
export SENTRY_URL=https://sentry.infra.mividas.com/

if [ -z "$CI" ]
then
rm -rf build/
git clone . build
cd build
fi

if ! [ -z "$SENTRY_AUTH_TOKEN" ]
then

export DOCKER_BUILDKIT=1

dockerfiles() {
    cat deploy/docker/Dockerfile-base deploy/docker/Dockerfile-ui deploy/docker/Dockerfile
}

NUMBER="${CI_JOB_ID:-${BITBUCKET_BUILD_NUMBER:-unknown}}"

dockerfiles | docker build -t mividas-core-js-all:$NUMBER --target=mividas-core-build -f - .

docker rm -f mividas-core-js-all-$NUMBER || true
docker create --name mividas-core-js-all-$NUMBER mividas-core-js-all:$NUMBER
docker cp mividas-core-js-all-$NUMBER:/code/static/dist static/dist || true
docker rm mividas-core-js-all-$NUMBER

export VERSION_PREFIX="${DEPLOY_VERSION:-${BITBUCKET_TAG:-${CI_COMMIT_TAG:-${VERSION:-`cat version.txt`}}}}+"
export COMMIT="${BITBUCKET_COMMIT:-${CI_COMMIT_SHA:-`git rev-parse HEAD 2>/dev/null || echo -n `}}"
export SENTRY_VERSION="mividas-core@`echo -n "$VERSION_PREFIX" | sed 's/^[v+]//'`$COMMIT"

[ -e scripts/sentry-cli ] || (wget https://downloads.sentry-cdn.com/sentry-cli/1.60.1/sentry-cli-Linux-x86_64 -O scripts/sentry-cli && chmod 755 scripts/sentry-cli )

scripts/sentry-cli releases new -p core -p core-js-ui "$SENTRY_VERSION"
scripts/sentry-cli releases set-commits "$SENTRY_VERSION" --commit "Mividas / Mividas Core@$COMMIT"
scripts/sentry-cli releases files "$SENTRY_VERSION" upload-sourcemaps -u '~/site_media/static/dist/' static/dist/

fi
[ -z "$CI" ] && rm -rf build
exit 0
