#!/bin/ash
ssh-keygen -A
! [ -e /etc/ssh/persistant/ssh_host_rsa_key ] && ssh-keygen -N '' -q -t rsa -f /etc/ssh/persistant/ssh_host_rsa_key
! [ -e /home/epmproxy/.ssh ] && mkdir -p /home/epmproxy/.ssh
chmod 711 /home/epmproxy/.ssh

if ! [ -e /home/epmproxy/.ssh/authorized_keys ]; then
    echo >> /home/epmproxy/.ssh/authorized_keys
    chmod 666 /home/epmproxy/.ssh/authorized_keys
fi

stop() {
    kill -SIGTERM "$SSH_PID"
    wait "$SSH_PID"
}
trap stop SIGINT SIGTERM
/usr/sbin/sshd -D -e "$@" &

SSH_PID="$!"

wait
exit $?
