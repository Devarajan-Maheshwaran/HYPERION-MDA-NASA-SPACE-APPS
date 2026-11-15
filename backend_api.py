"""Single-command entrypoint for the live HYPERION-MDA workstation.

    python backend_api.py
    # then open http://localhost:8000

If web/dist is missing, this builds the React SPA first (npm ci + npm run build). For a
fresh clone including Python dependency setup, use:  bash run_workstation.sh

State is durable by default: cases, telemetry history, exams, calibrations, workflow stage,
the surgeon outbox and the audit chain live in SQLite at `var/hyperion-state.db` (override
with HYPERION_STATE_DB). Restarting the process resumes the same mission clock and stage.

This is a thin wrapper over the tested FastAPI composition layer in api/. It serves the
built React SPA and the unified /api/state + /api/exams/* endpoints on the same origin,
so there is no CORS and no separate frontend server in production.

Not a medical device. Demo thresholds, not clinically validated.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_DB = REPO_ROOT / "var" / "hyperion-state.db"


def state_db_path() -> Path:
    """Durable case store. HYPERION_STATE_DB=':memory:' opts out deliberately."""
    raw = os.environ.get("HYPERION_STATE_DB")
    if raw == ":memory:":
        return Path(":memory:")
    path = Path(raw) if raw else DEFAULT_STATE_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def audit_log_path() -> Path | None:
    raw = os.environ.get("HYPERION_AUDIT_LOG")
    return Path(raw) if raw else None


def ensure_spa() -> None:
    dist = REPO_ROOT / "web" / "dist"
    if (dist / "index.html").exists():
        return
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("web/dist is missing and npm was not found. Install Node 20+, then: "
                         "cd web && npm ci && npm run build")
    web = REPO_ROOT / "web"
    if not (web / "node_modules").exists():
        subprocess.run([npm, "ci"], cwd=web, check=True)
    subprocess.run([npm, "run", "build"], cwd=web, check=True)


def main() -> None:
    try:
        import uvicorn
        from api.main import create_app
    except ImportError as exc:
        raise SystemExit(f"Missing API dependency: {exc}. Install with: "
                         f"{sys.executable} -m pip install -r requirements-api.txt") from exc
    ensure_spa()
    db = state_db_path()
    app = create_app(audit_log_path(), None if str(db) == ":memory:" else db)
    print(f"HYPERION-MDA state store: {db}", flush=True)
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"),
                port=int(os.environ.get("PORT", "8000")), log_level="info")


# Keep a module-level app for `uvicorn backend_api:app` as well.
try:
    from api.main import create_app as _create_app
    _db = state_db_path()
    app = _create_app(audit_log_path(), None if str(_db) == ":memory:" else _db)
except ImportError:  # pragma: no cover - helpful CLI path above
    app = None

if __name__ == "__main__":
    main()
