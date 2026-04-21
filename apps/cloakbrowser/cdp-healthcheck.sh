#!/usr/bin/env bash
set -euo pipefail
port="${CLOAKBROWSER_CDP_PORT:-9222}"
proxy_port="${CLOAKBROWSER_PROXY_PORT:-9223}"
server_port="${NEKO_SERVER_BIND##*:}"

curl -fsS "http://127.0.0.1:${port}/json/version" >/dev/null
curl -fsS "http://127.0.0.1:${proxy_port}/json/version" >/dev/null
curl -fsS "http://127.0.0.1:${server_port}/health" >/dev/null
