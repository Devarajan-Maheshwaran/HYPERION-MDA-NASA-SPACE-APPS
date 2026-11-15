#!/usr/bin/env bash
# One-command bootstrap + launch for the HYPERION-MDA live crew workstation.
#
#   bash run_workstation.sh              # create venv, install, build SPA, serve :8000
#   bash run_workstation.sh --offline    # reuse an existing venv + web/dist; no network
#   PORT=9000 bash run_workstation.sh    # different port
#
# After the first successful run everything needed is on disk: the second run with
# --offline touches no package index. State is durable in var/hyperion-state.db.
# Not a medical device. Demo thresholds, not clinically validated.
set -euo pipefail
cd "$(dirname "$0")"

OFFLINE=0
for arg in "$@"; do
  case "$arg" in
    --offline) OFFLINE=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv-api}"

if [ "$OFFLINE" -eq 1 ]; then
  if [ ! -x "$VENV/bin/python" ]; then
    echo "OFFLINE: $VENV is missing. Run once without --offline to install dependencies." >&2
    exit 1
  fi
  if [ ! -f web/dist/index.html ]; then
    echo "OFFLINE: web/dist is missing. Run once without --offline to build the SPA." >&2
    exit 1
  fi
  if ! "$VENV/bin/python" -c "import fastapi, uvicorn, pydantic" >/dev/null 2>&1; then
    echo "OFFLINE: API dependencies are not importable in $VENV." >&2
    exit 1
  fi
  echo "OFFLINE: reusing $VENV and web/dist; no network access."
else
  if [ ! -d "$VENV" ]; then
    "$PYTHON" -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  . "$VENV/bin/activate"
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -r requirements-api.txt
  if [ ! -d web/node_modules ]; then
    (cd web && npm ci)
  fi
  (cd web && npm run build)
fi

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
export HYPERION_STATE_DB="${HYPERION_STATE_DB:-$PWD/var/hyperion-state.db}"
mkdir -p "$(dirname "$HYPERION_STATE_DB")"

echo "Crew workstation → http://localhost:${PORT}  (state: $HYPERION_STATE_DB)"
exec "$VENV/bin/python" backend_api.py
