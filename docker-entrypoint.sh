#!/usr/bin/env bash
set -e


tor -f /etc/tor/torrc &
polipo -c /etc/polipo/polipo
wait -n
