FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Istanbul

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        obfs4proxy \
        privoxy \
        snowflake-client \
        socat \
        tini \
        tzdata \
        tor \
        tor-geoipdb \
    && rm -rf /var/lib/apt/lists/*

COPY torrc /etc/tor/torrc
COPY privoxy/config /etc/privoxy/config
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN install -d -o debian-tor -g debian-tor -m 0700 /var/lib/tor \
    && chmod 0644 /etc/tor/torrc /etc/privoxy/config \
    && chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && tor --verify-config -f /etc/tor/torrc

ENTRYPOINT ["tini", "--", "/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 8118 9050 9051
