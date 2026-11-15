"""Single-command entrypoint for the live HYPERION-MDA workstation.

    python backend_api.py
    # then open http://localhost:8000

If web/dist is missing, this builds the React SPA first (npm ci + npm run build). For a
fresh clone including Python dependency setup, use:  bash run_workstation.sh

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
    audit = os.environ.get("HYPERION_AUDIT_LOG")
    app = create_app(Path(audit) if audit else None)
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"),
                port=int(os.environ.get("PORT", "8000")), log_level="info")


# Keep a module-level app for `uvicorn backend_api:app` as well.
try:
    from api.main import create_app as _create_app
    app = _create_app(Path(os.environ["HYPERION_AUDIT_LOG"]) if os.environ.get("HYPERION_AUDIT_LOG") else None)
except ImportError:  # pragma: no cover - helpful CLI path above
    app = None

if __name__ == "__main__":
    main()
