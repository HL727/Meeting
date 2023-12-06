set -e

if [ -z "$CI" ]
then
rm -rf build/
git clone . build
cd build
fi

export DOCKER_BUILDKIT=1
export BUILDKIT_PROGRESS=plain
export BASE_DOCKER_TAG="${CI_COMMIT_BRANCH:-${CI_COMMIT_TAG:-latest}}"

export NUMBER="${CI_JOB_ID:-${BITBUCKET_BUILD_NUMBER:-unknown}}"

# ##################
# Concatenate docker files:
# ##################

dockerfiles() {
    cat deploy/docker/Dockerfile-base deploy/docker/Dockerfile-ui deploy/docker/Dockerfile
}

# ##################
# Build base:
# ##################

build_base() {

dockerfiles | docker build \
	-t mividas-core-base:$BASE_DOCKER_TAG \
	-t ${CI_REGISTRY_IMAGE:-local}/mividas-core-base:$NUMBER \
	--cache-from=${CI_REGISTRY_IMAGE}/mividas-core-base:$BASE_DOCKER_TAG \
	--cache-from=${CI_REGISTRY_IMAGE}/mividas-core-base:master \
	--build-arg BUILDKIT_INLINE_CACHE=1 \
	--target=mividas-core-base \
	-f - . &

dockerfiles | docker build \
	-t mividas-core-js-base:$BASE_DOCKER_TAG \
	-t ${CI_REGISTRY_IMAGE:-local}/mividas-core-js-base:$NUMBER \
	--cache-from=${CI_REGISTRY_IMAGE}/mividas-core-js-base:$BASE_DOCKER_TAG \
	--cache-from=${CI_REGISTRY_IMAGE}/mividas-core-js-base:master \
	--build-arg BUILDKIT_INLINE_CACHE=1 \
	--target=mividas-core-js-base \
	-f - . &
wait

}

# ##################
# Build containers:
# ##################

build_containers() {

export COMMIT=${BITBUCKET_COMMIT:-${CI_COMMIT_SHA:-`git rev-parse HEAD 2>/dev/null || echo -n`}}
export VERSION=${DEPLOY_VERSION:-${BITBUCKET_TAG:-${CI_COMMIT_TAG:-${VERSION:-`cat version.txt`-${CI_PIPELINE_ID}}}}}

dockerfiles | docker build -t mividas-core-static:$NUMBER --target=mividas-core-static -f - .
dockerfiles | docker build -t mividas-core:$NUMBER -f - \
    --build-arg "COMMIT=$COMMIT" --build-arg "VERSION=$VERSION" \
    .
git checkout .dockerignore || true

docker build -t mividas-smtp-forward:$NUMBER deploy/smtp_script
docker build -t mividas-proxy-server:$NUMBER endpointproxy/server

}

# ##################
# Run build scripts:
# ##################

build_base

if [ -z "$ONLY_BUILD_BASE" ]
then
	build_containers
fi

[ -z "$CI" ] && rm -rf build
exit 0
