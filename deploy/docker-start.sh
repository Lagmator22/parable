#!/usr/bin/env bash
set -euo pipefail

# Match the World ID OAuth callback to whichever free PaaS URL is hosting this container.
if [ -z "${WORLD_REDIRECT_URI:-}" ]; then
  if [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
    export WORLD_REDIRECT_URI="${RENDER_EXTERNAL_URL%/}/world/callback"
  elif [ -n "${RAILWAY_PUBLIC_DOMAIN:-}" ]; then
    export WORLD_REDIRECT_URI="https://${RAILWAY_PUBLIC_DOMAIN}/world/callback"
  elif [ -n "${KOYEB_PUBLIC_DOMAIN:-}" ]; then
    export WORLD_REDIRECT_URI="https://${KOYEB_PUBLIC_DOMAIN}/world/callback"
  fi
fi

# Keep Python + Node bridge aligned even if ARKIV_BRIDGE_TOKEN wasn't explicitly set.
if [ -z "${ARKIV_BRIDGE_TOKEN:-}" ]; then
  export ARKIV_BRIDGE_TOKEN
  ARKIV_BRIDGE_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
fi

export NODE_OPTIONS="${NODE_OPTIONS:-} --max-old-space-size=128"
export ARKIV_BRIDGE_PORT="${ARKIV_BRIDGE_PORT:-8787}"
export ARKIV_BRIDGE_URL="http://127.0.0.1:${ARKIV_BRIDGE_PORT}"

BRIDGE_PID=""
ENGINE_PID=""

cleanup() {
  trap - TERM INT EXIT
  [ -n "$ENGINE_PID" ] && kill "$ENGINE_PID" 2>/dev/null || true
  [ -n "$BRIDGE_PID" ] && kill "$BRIDGE_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup TERM INT EXIT

if [ -n "${ARKIV_PRIVATE_KEY:-}" ]; then
  (cd /app/arkiv-bridge && exec node index.mjs) &
  BRIDGE_PID=$!

  # Wait briefly for the local bridge to bind before FastAPI's startup repair runs.
  for _ in $(seq 1 30); do
    if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then
      echo "arkiv-bridge exited unexpectedly" >&2
      exit 1
    fi
    if python3 -c "import socket; s=socket.create_connection(('127.0.0.1', ${ARKIV_BRIDGE_PORT}), 0.5); s.close()" 2>/dev/null; then
      break
    fi
    sleep 0.2
  done
else
  echo "ARKIV_PRIVATE_KEY not set; starting engine without arkiv-bridge" >&2
fi

cd /app/engine
/app/engine/.venv/bin/uvicorn parable.api:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 &
ENGINE_PID=$!

wait -n "$ENGINE_PID" ${BRIDGE_PID:+"$BRIDGE_PID"}
