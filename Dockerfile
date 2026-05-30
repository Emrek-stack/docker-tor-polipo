FROM node:22-bookworm-slim AS react-vendor

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --omit=dev \
    && mkdir -p /out/vendor \
    && cp node_modules/react/umd/react.production.min.js /out/vendor/react.production.min.js \
    && cp node_modules/react-dom/umd/react-dom.production.min.js /out/vendor/react-dom.production.min.js

FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Istanbul

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        obfs4proxy \
        privoxy \
        python3 \
        snowflake-client \
        socat \
        tini \
        tzdata \
        tor \
        tor-geoipdb \
    && rm -rf /var/lib/apt/lists/*

COPY torrc /etc/tor/torrc
COPY privoxy/config /etc/privoxy/config
COPY privoxy/tor-hardening.action /etc/privoxy/tor-hardening.action
COPY dashboard/static /opt/tor-dashboard/static
COPY --from=react-vendor /out/vendor /opt/tor-dashboard/vendor
COPY tor-dashboard.py /usr/local/bin/tor-dashboard.py
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN install -d -o debian-tor -g debian-tor -m 0700 /var/lib/tor \
    && chmod -R 0755 /opt/tor-dashboard \
    && chmod 0644 /etc/tor/torrc /etc/privoxy/config /etc/privoxy/tor-hardening.action \
    && chmod 0755 /usr/local/bin/tor-dashboard.py \
    && chmod 0755 /usr/local/bin/docker-entrypoint.sh \
    && tor --verify-config -f /etc/tor/torrc

ENTRYPOINT ["tini", "--", "/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 8080 8118 9050 9051
