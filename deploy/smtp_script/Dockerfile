FROM alpine:3.14 AS mividas-core-smtp-server
RUN apk add --no-cache opensmtpd curl && apk --purge del apk-tools

COPY cmd.sh entrypoint.sh /
COPY smtpd.conf /etc/smtpd/
RUN chmod 755 /cmd.sh ; \
  echo '@ nobody' > /etc/virtual ; \
  touch /tmp/.env

# TODO try to get opensmtpd to run on non-root port

ENTRYPOINT /entrypoint.sh

