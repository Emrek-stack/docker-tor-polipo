#!/usr/bin/env bash
docker build . -t tor:1.1 &&
docker run --name tor -d -p 8123:8123 -p 8118:8118 tor:1.1 -p