set -e

cd `dirname $0`
mkdir -p core/config
touch core/config/local_settings.py

docker-compose -p 'mividas-core' -f docker-compose.yml "$@"
