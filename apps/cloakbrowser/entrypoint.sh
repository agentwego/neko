#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99.0}"
export HOME="${HOME:-/home/neko}"
export USER="${USER:-neko}"
export CLOAKBROWSER_PROFILE_DIR="${CLOAKBROWSER_PROFILE_DIR:-/home/neko/.config/cloakbrowser}"
export CLOAKBROWSER_CDP_PORT="${CLOAKBROWSER_CDP_PORT:-9222}"
export CLOAKBROWSER_WINDOW_SIZE="${CLOAKBROWSER_WINDOW_SIZE:-1920,1080}"
export CLOAKBROWSER_START_URL="${CLOAKBROWSER_START_URL:-about:blank}"
export CLOAKBROWSER_REMOTE_DEBUGGING_ADDRESS="${CLOAKBROWSER_REMOTE_DEBUGGING_ADDRESS:-0.0.0.0}"
export CLOAKBROWSER_BIN="${CLOAKBROWSER_BIN:-/opt/cloakbrowser-bin/chrome}"
export CLOAKBROWSER_STEALTH_ARGS_ENABLED="${CLOAKBROWSER_STEALTH_ARGS_ENABLED:-true}"
export CLOAKBROWSER_FINGERPRINT_PLATFORM="${CLOAKBROWSER_FINGERPRINT_PLATFORM:-windows}"

mkdir -p "${CLOAKBROWSER_PROFILE_DIR}/Default" /home/neko/Downloads
chown -R "${USER}:${USER}" "${CLOAKBROWSER_PROFILE_DIR}" /home/neko/Downloads 2>/dev/null || true

mapfile -t CLOAK_ARGS < <(
python3 - <<'PY'
import os
from cloakbrowser.config import get_default_stealth_args
if os.environ.get('CLOAKBROWSER_STEALTH_ARGS_ENABLED', 'true').lower() not in {'0', 'false', 'no'}:
    fingerprint_platform = os.environ.get('CLOAKBROWSER_FINGERPRINT_PLATFORM', '').strip().lower()
    for arg in get_default_stealth_args():
        if fingerprint_platform and arg.startswith('--fingerprint-platform='):
            print(f'--fingerprint-platform={fingerprint_platform}')
        else:
            print(arg)
PY
)

if [[ ! -x "${CLOAKBROWSER_BIN}" ]]; then
  echo "CloakBrowser binary not executable: ${CLOAKBROWSER_BIN}" >&2
  ls -la /opt/cloakbrowser-bin >&2 || true
  exit 1
fi

EXTRA_ARGS=()
if [[ -n "${CLOAKBROWSER_EXTRA_ARGS:-}" ]]; then
  while IFS= read -r line; do
    [[ -n "$line" ]] && EXTRA_ARGS+=("$line")
  done < <(python3 - <<'PY'
import os, shlex
for arg in shlex.split(os.environ.get('CLOAKBROWSER_EXTRA_ARGS', '')):
    print(arg)
PY
)
fi

ARGS=(
  "${CLOAK_ARGS[@]}"
  --no-sandbox
  --window-position=0,0
  "--window-size=${CLOAKBROWSER_WINDOW_SIZE}"
  "--display=${DISPLAY}"
  "--user-data-dir=${CLOAKBROWSER_PROFILE_DIR}"
  --no-first-run
  --start-maximized
  --bwsi
  --force-dark-mode
  --disable-file-system
  --disable-dev-shm-usage
  "--remote-debugging-port=${CLOAKBROWSER_CDP_PORT}"
  "--remote-debugging-address=${CLOAKBROWSER_REMOTE_DEBUGGING_ADDRESS}"
)

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  ARGS+=("${EXTRA_ARGS[@]}")
fi

printf 'user=%s home=%s display=%s\n' "$USER" "$HOME" "$DISPLAY"
printf 'cloakbrowser binary: %s\n' "$CLOAKBROWSER_BIN"
printf 'cloakbrowser args (%s):\n' "${#ARGS[@]}"
printf '  %q\n' "${ARGS[@]}"

exec "$CLOAKBROWSER_BIN" \
  "${ARGS[@]}" \
  "$CLOAKBROWSER_START_URL"
