"""Read-only loader for the committed FL/DP benchmark artifact.

The API never recomputes the benchmark: it reports exactly what
`scripts/run_fl_dp_benchmark.py` wrote to `artifacts/fl_dp_benchmark_results.json`, including
the artifact digest, so every number in the UI is traceable to a committed file.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = REPO_ROOT / "artifacts" / "fl_dp_benchmark_results.json"

MISSING_DETAIL = ("artifacts/fl_dp_benchmark_results.json is not present. Run "
                  "`python3 scripts/run_fl_dp_benchmark.py` to generate the measured, "
                  "reproducible benchmark. No values are invented in the meantime.")


def load() -> dict[str, Any]:
    if not ARTIFACT.is_file():
        return {"available": False, "detail": MISSING_DETAIL, "results": None, "sha256": None}
    try:
        raw = ARTIFACT.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        return {"available": False, "detail": f"benchmark artifact unreadable: {exc}",
                "results": None, "sha256": None}
    return {"available": True, "detail": "Measured, committed benchmark artifact",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "path": str(ARTIFACT.relative_to(REPO_ROOT)), "results": data}
