#!/usr/bin/env bash
set -Eeuo pipefail

IMAGE_NAME="${IMAGE_NAME:-tor-proxy:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-tor-proxy}"
CONTROL_PUBLISH_ADDR="${CONTROL_PUBLISH_ADDR:-127.0.0.1}"
TOR_CONTROL_PORT="${TOR_CONTROL_PORT:-9051}"
TOR_CONTROL_PASSWORD="${TOR_CONTROL_PASSWORD:-vidalia}"
TOR_DASHBOARD_PORT="${TOR_DASHBOARD_PORT:-8080}"

docker build --pull -t "$IMAGE_NAME" .

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker run -d \
	--name "$CONTAINER_NAME" \
	--restart unless-stopped \
	-e TOR_CONTROL_PASSWORD="$TOR_CONTROL_PASSWORD" \
	-e TOR_CONTROL_PORT="$TOR_CONTROL_PORT" \
	-e TOR_DASHBOARD_PORT="$TOR_DASHBOARD_PORT" \
	-p 127.0.0.1:$TOR_DASHBOARD_PORT:$TOR_DASHBOARD_PORT \
	-p 127.0.0.1:8118:8118 \
	-p 127.0.0.1:9050:9050 \
	-p "$CONTROL_PUBLISH_ADDR:$TOR_CONTROL_PORT:$TOR_CONTROL_PORT" \
	"$IMAGE_NAME"

docker ps --filter "name=$CONTAINER_NAME"
cat <<EOF

Tor control settings for Vidalia .NET:
  Control address: 127.0.0.1
  Control port:    $TOR_CONTROL_PORT
  Control password: $TOR_CONTROL_PASSWORD
  Start local Tor if control connection fails: off

Tor web dashboard:
  http://127.0.0.1:$TOR_DASHBOARD_PORT

EOF
