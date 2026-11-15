#!/usr/bin/env bash
# One-command bootstrap + launch for the HYPERION-MDA live workstation.
#   bash run_workstation.sh
#   open http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if [ ! -d .venv-api ]; then
  "$PYTHON" -m venv .venv-api
fi
# shellcheck disable=SC1091
. .venv-api/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements-api.txt

if [ ! -d web/node_modules ]; then
  (cd web && npm ci)
fi
(cd web && npm run build)

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
exec python backend_api.py
