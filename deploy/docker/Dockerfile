FROM mividas-core-base AS mividas-core-build

WORKDIR /code/
COPY . /code/

COPY --from=mividas-core-build-js /usr/share/nginx/html/site_media/static/dist/ /code/static/dist/
RUN python manage.py collectstatic --noinput && touch /code/site_media/static/staticfiles.json \
    && rm -rf /code/static/ && mkdir /code/static

 # Make sure to copy dirs to Dockerfile-test
RUN mkdir -p /code/site_media/media/_is_default /code/site_media/static /code/cdrdata/_is_default && \
    chown -R mividas /code/site_media/media/ /code/site_media/static/ /code/cdrdata/

# fix for COPY with --chown below when running with userns-remap
USER root
RUN chown -R root:root /code/ ; find /code/site_media -name '*.map' -delete


USER mividas

# nginx. merge js build and django static
FROM nginx AS mividas-core-static
LABEL maintainer="Mividas Video Solutions AB <info@mividas.com>"
# TODO remove next line (COPY). Keep temporarly until all docker compose files are updates
COPY --from=mividas-core-build --chown=www-data:www-data /code/site_media/ /usr/share/nginx/html/site_media/

RUN mkdir -p /usr/share/nginx/html/site_media/media/ && chown -R www-data.www-data /usr/share/nginx/html/site_media/

# django app, copy files and cleanup
FROM python:3.8-slim-buster AS cleanup_files

COPY --from=mividas-core-build /code/ /code/

RUN rm -rf /code/js-ui/ /code/static/* /code/deploy/ \
    /code/*/tests/ /code/*/tests.py \
    package*json .eslint* setup.cfg pyproject.toml

RUN python -m compileall -b -j 0 /code/ && find /code/ -name '*.py' \
    ! -path '*/bin/*' ! -path '*/migrations/*' ! -name manage.py ! -path '*/test*' \
    ! -name '__init__.py' ! -name http_status_check.py ! -name custom_ca.py ! -name wait_for_services.py \
     -delete

# TODO
COPY --from=mividas-core-build /code/conferencecenter/tests/mock_data/response.py /code/conferencecenter/tests/mock_data/
RUN touch /code/conferencecenter/tests/__init__.py /code/conferencecenter/tests/mock_data/__init__.py


# django app
FROM mividas-core-base AS mividas-core
ARG COMMIT
ARG VERSION
LABEL maintainer="Mividas Video Solutions AB <info@mividas.com>"
LABEL version="$VERSION"
LABEL commit="$commit"

WORKDIR /code/

COPY --from=cleanup_files --chown=root:root /code/ /code/
COPY --from=mividas-core-build --chown=root:root /code/site_media/static/staticfiles.json /code/site_media/static/

RUN apt-get remove -y --allow-remove-essential apt*
RUN touch /code/conferencecenter/local_settings.py && chown -R mividas /code/site_media/media/ /code/cdrdata/ /code/conferencecenter/local_settings.py
VOLUME /code/site_media/media/

RUN ( ! [ -z "$COMMIT" ] && echo "$COMMIT" > commit.txt || true ) ; \
    ( ! [ -z "$VERSION" ] && echo "$VERSION" > version.txt || true )

USER mividas


FROM mividas-core AS mividas-core-vulnscan
COPY --from=aquasec/trivy:latest /usr/local/bin/trivy /usr/local/bin/trivy
ARG TRIVY_FAIL=1
ENV TRIVY_SKIP_FILES=/usr/local/bin/trivy,/opt/venv/lib/python3.8/site-packages/slapdtest/certs/server.key,/opt/venv/lib/python3.8/site-packages/slapdtest/certs/client.key
USER root
COPY .trivyignore .
RUN trivy rootfs --no-progress --format json --output "/gl-container-scanning-report.json" /
RUN trivy rootfs --no-progress /
RUN trivy rootfs --exit-code "${TRIVY_FAIL:-1}" --severity HIGH,CRITICAL --ignore-unfixed --no-progress /
CMD trivy rootfs --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed --no-progress /


FROM mividas-core

USER root
# Firmware files etc can be very large and needs to be written to disk
RUN ! [ -e /tmp ] || ( mkdir -p /tmp  chmod 777 /tmp )
USER mividas

VOLUME /tmp
