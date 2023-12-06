#!/bin/ash

if [ -z "$1" ]
then
exit
fi

while true
do

sleep 5

rm /tmp/output
curl "$1" -kO /tmp/output || continue

ssh-keygen -lf /tmp/output && mv /tmp/output/ /home/epmproxy/.ssh/authorized_keys2

done

