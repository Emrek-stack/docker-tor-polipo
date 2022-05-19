#!/usr/bin/env bash

PRIVOXY_CONFFILE=/etc/privoxy/config
PRIVOXY_PIDFILE=/var/run/privoxy.pid

set -e

if [ ! -f "${PRIVOXY_CONFFILE}" ]; then
	echo "Configuration file ${PRIVOXY_CONFFILE} not found!"
	exit 1
fi

tor -f /etc/tor/torrc &
polipo -c /etc/polipo/polipo &
/usr/sbin/privoxy --no-daemon --pidfile "${PRIVOXY_PIDFILE}" "${PRIVOXY_CONFFILE}"

wait -n
