#!/bin/sh
if [ -e /usr/bin/xvfb-run ]
then
    exec xvfb-run -a node node_modules/orca/bin/orca.js "$@"
else
    exec node node_modules/orca/bin/orca.js "$@"
fi
