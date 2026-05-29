#!/usr/bin/env bash
set -Eeuo pipefail

TOR_CONFFILE=/etc/tor/torrc
RUNTIME_TOR_CONFFILE=/run/torrc
PRIVOXY_CONFFILE=/etc/privoxy/config
PRIVOXY_PIDFILE=/run/privoxy.pid
TOR_CONTROL_PORT="${TOR_CONTROL_PORT:-9051}"
TOR_CONTROL_INTERNAL_PORT="${TOR_CONTROL_INTERNAL_PORT:-19051}"
TOR_CONTROL_PASSWORD="${TOR_CONTROL_PASSWORD:-vidalia}"
TOR_DASHBOARD_PORT="${TOR_DASHBOARD_PORT:-8080}"
tor_pid=
socks_forward_pid=
control_forward_pid=
privoxy_pid=
dashboard_pid=

for file in "$TOR_CONFFILE" "$PRIVOXY_CONFFILE"; do
	if [[ ! -r "$file" ]]; then
		echo "Configuration file $file is missing or not readable" >&2
		exit 1
	fi
done

shutdown() {
	trap - TERM INT
	kill -TERM "$tor_pid" "$socks_forward_pid" "$control_forward_pid" "$privoxy_pid" "$dashboard_pid" 2>/dev/null || true
	wait "$tor_pid" "$socks_forward_pid" "$control_forward_pid" "$privoxy_pid" "$dashboard_pid" 2>/dev/null || true
}

trap shutdown TERM INT

cp "$TOR_CONFFILE" "$RUNTIME_TOR_CONFFILE"
{
	echo "ControlPort 127.0.0.1:${TOR_CONTROL_INTERNAL_PORT}"
	tor --hash-password "$TOR_CONTROL_PASSWORD" | tail -n 1 | sed 's/^/HashedControlPassword /'
} >> "$RUNTIME_TOR_CONFFILE"
chmod 0600 "$RUNTIME_TOR_CONFFILE"

tor -f "$RUNTIME_TOR_CONFFILE" &
tor_pid=$!

socat TCP-LISTEN:9050,fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:19050 &
socks_forward_pid=$!

socat TCP-LISTEN:"$TOR_CONTROL_PORT",fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:"$TOR_CONTROL_INTERNAL_PORT" &
control_forward_pid=$!

/usr/sbin/privoxy --no-daemon --pidfile "$PRIVOXY_PIDFILE" "$PRIVOXY_CONFFILE" &
privoxy_pid=$!

TOR_CONTROL_HOST=127.0.0.1 \
TOR_CONTROL_PORT="$TOR_CONTROL_INTERNAL_PORT" \
TOR_CONTROL_PASSWORD="$TOR_CONTROL_PASSWORD" \
TOR_SOCKS_HOST=127.0.0.1 \
TOR_SOCKS_PORT=19050 \
TOR_DASHBOARD_HOST=0.0.0.0 \
TOR_DASHBOARD_PORT="$TOR_DASHBOARD_PORT" \
	/usr/local/bin/tor-dashboard.py &
dashboard_pid=$!

wait -n "$tor_pid" "$socks_forward_pid" "$control_forward_pid" "$privoxy_pid" "$dashboard_pid"
exit_code=$?

shutdown
exit "$exit_code"
