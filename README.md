# Docker Tor Proxy

Containerized Tor proxy with current package-based Tor, obfs4, Snowflake and Privoxy.

## Build and run

```sh
./ruh.sh
```

The helper script builds `tor-proxy:latest`, replaces an existing `tor-proxy` container, and binds proxy ports to localhost only:

- `127.0.0.1:9050` SOCKS5 Tor proxy
- `127.0.0.1:8118` HTTP proxy through Privoxy and Tor
- `127.0.0.1:9051` Tor control port

The default Tor control password is `vidalia`, so Vidalia .NET can connect immediately on the same machine:

```txt
Control address: 127.0.0.1
Control port: 9051
Control password: vidalia
Start a local Tor process if the control connection fails: off
```

Set a different control password before enabling remote access:

```sh
TOR_CONTROL_PASSWORD='change-this-password' ./ruh.sh
```

To allow another machine on your LAN or VPN to connect to the control port, publish it on all host interfaces:

```sh
CONTROL_PUBLISH_ADDR=0.0.0.0 TOR_CONTROL_PASSWORD='change-this-password' ./ruh.sh
```

Do not publish proxy or control ports on `0.0.0.0` unless you intentionally want other machines on your network to use them.

## Firefox proxy settings

Recommended Firefox setup:

1. Settings > General > Network Settings > Settings
2. Select Manual proxy configuration
3. Set SOCKS Host to `127.0.0.1`, Port `9050`
4. Select SOCKS v5
5. Enable "Proxy DNS when using SOCKS v5"

If an extension or tool only supports HTTP proxies, use HTTP Proxy `127.0.0.1`, Port `8118`.

## Verify

```sh
curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip
curl --proxy http://127.0.0.1:8118 https://check.torproject.org/api/ip
```

Both commands should return `"IsTor":true`.

## Control port

The control port is available on `127.0.0.1:9051` by default. It uses password authentication. Cookie authentication is disabled in the runtime torrc because external GUI clients cannot read the container cookie file.

Example with `nc`:

```sh
printf 'AUTHENTICATE "vidalia"\r\nGETINFO status/bootstrap-phase\r\nQUIT\r\n' | nc 127.0.0.1 9051
```
