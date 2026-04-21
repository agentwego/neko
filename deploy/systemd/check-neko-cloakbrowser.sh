#!/usr/bin/env bash
set -euo pipefail

cd /home/yun/workspace/neko
/usr/bin/docker compose --env-file deploy/.env.cloakbrowser -f deploy/docker-compose.cloakbrowser.yml ps
/usr/bin/systemctl status neko-cloakbrowser.service --no-pager || true
