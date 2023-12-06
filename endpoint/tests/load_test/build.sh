REGISTRY_BASE_PROD=registry.mividas.com/mividas-tools

docker build -t ${REGISTRY_BASE:-local/}endpoint-simulator:0.1 -f Dockerfile ..
