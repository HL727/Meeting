set -e
export BASE="$1"
export PASSWORD="$2"
export VERSION="${3:-latest}"
export USER="${4:-${CI_REGISTRY_USER:-${REGISTRY_USER:-bitbucket}}}"
NUMBER="${CI_JOB_ID:-${BITBUCKET_BUILD_NUMBER:-unknown}}"

upload() {
    [ -z "$ONLY_TAG" ] && docker login -u "$USER" -p "$PASSWORD" "`dirname $BASE`"
    export NAME="$1:$NUMBER"
    export REP="$BASE/${2:-$1}:$VERSION"
    echo "$REP"
    docker tag "$NAME" "$REP"
    [ -z "$ONLY_TAG" ] && docker push "$REP"
    return 0
}
upload mividas-core
upload mividas-core-static
upload mividas-smtp-forward
upload mividas-smtp-forward mividas-core-smtp-forward
upload mividas-proxy-server
upload mividas-proxy-server mividas-core-proxy-server
