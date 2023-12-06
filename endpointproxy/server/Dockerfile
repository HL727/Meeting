FROM alpine:3.14 AS mividas-proxy-server
RUN apk add --no-cache openssh-server && apk --purge del apk-tools

RUN adduser -S epmproxy && sed -i s/epmproxy:!/"epmproxy:*"/g /etc/shadow
RUN mkdir -m 0700 /home/epmproxy/.ssh && chown epmproxy /home/epmproxy/.ssh
RUN mkdir -m 0700 /etc/ssh/persistant/

VOLUME /etc/ssh/persistant/
VOLUME /home/epmproxy/.ssh/

COPY --chown=0:0 sshd_config /etc/ssh/
RUN chmod 600 /etc/ssh/sshd_config
COPY entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
