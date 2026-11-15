"""Read-only composition of the existing lanes. Imports them; never modifies them.

Every function reports honestly when its data is absent: `available=False` with the real
reason. Nothing is fabricated to fill a gap, and no lane's data is passed to another lane.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hyperion_mda import signal_registry as reg  # noqa: E402
from hyperion_mda.osdr_source import (OsdrSourceError, load_manifest,  # noqa: E402
                                      verified_cmp_file)

from .models import LaneInfo


def cache_dir() -> Path | None:
    env = os.environ.get("HYPERION_MDA_DATA_DIR")
    return Path(env) if env else None


def registry_channels() -> list[dict[str, Any]]:
    return [
        {"channel_id": c.channel_id, "label": c.label, "region": c.region, "status": c.status,
         "lane": c.lane, "source": c.source, "sampling": c.sampling, "unit": c.unit, "note": c.note}
        for c in reg.CHANNELS
    ]


def registry_summary() -> dict[str, Any]:
    counts = reg.status_counts()
    return {"total": len(reg.CHANNELS), "by_status": dict(counts),
            "source": "signal_registry.CHANNELS (value-free registry)"}


def lab_lane() -> LaneInfo:
    try:
        verified = verified_cmp_file(cache_dir())
    except OsdrSourceError as exc:
        return LaneInfo(lane="LAB DATA", available=False, detail=str(exc),
                        provenance="NASA OSDR OSD-575 (not cached)")
    except OSError as exc:
        return LaneInfo(lane="LAB DATA", available=False, detail=str(exc),
                        provenance="NASA OSDR OSD-575 (unreadable cache)")
    return LaneInfo(lane="LAB DATA", available=True,
                    detail=f"SHA-256 verified, {verified.size} bytes",
                    provenance=f"NASA OSDR OSD-575 · {verified.path.name}")


def lab_rows() -> dict[str, Any]:
    """Verified NASA lab rows through the existing adapter, or an honest unavailable."""
    from hyperion_mda.osdr_cmp import load_osd575_cmp

    try:
        verified = verified_cmp_file(cache_dir())
        records, report = load_osd575_cmp(verified)
    except (OsdrSourceError, OSError) as exc:
        return {"available": False, "detail": str(exc), "rows": [], "lane": "LAB DATA",
                "provenance": "NASA OSDR OSD-575 (not cached)"}
    rows = [
        {"row_number": r.row_number, "subject_id": r.subject_id, "signal": r.signal,
         "value": None if not r.has_value else r.value, "unit": r.unit,
         "timepoint": r.timestamp, "record_type": r.record_type,
         "z_score": r.z_score, "score_note": r.score_note, "flags": list(r.flags),
         "rejection_reason": r.rejection_reason}
        for r in records
    ]
    return {"available": True, "detail": f"{len(rows)} rows, SHA-256 verified", "rows": rows,
            "lane": "LAB DATA", "provenance": f"NASA OSDR OSD-575 · {verified.path.name}",
            "sha256": verified.sha256, "data_rows": report.data_rows}


def recorded_lane() -> LaneInfo:
    from hyperion_mda.physionet_source import PhysioNetSourceError, load_manifest as pn_manifest

    try:
        manifest = pn_manifest()
        names = manifest.get("records") or []
        first = names[0] if isinstance(names, list) and names else None
        if first is None:
            files = manifest.get("files") or []
            first = None
            for entry in files:
                name = entry.get("name", "") if isinstance(entry, dict) else str(entry)
                if name.endswith(".hea"):
                    first = name[:-4]
                    break
        if first is None:
            raise PhysioNetSourceError("no record names in the manifest")
        from hyperion_mda.physionet_source import verified_record
        verified_record(first, cache_dir())
    except Exception as exc:  # missing cache, checksum, or format — all reported honestly
        return LaneInfo(lane="RECORDED-NON-ASTRONAUT", available=False, detail=str(exc),
                        provenance="PhysioNet Wrist PPG During Exercise v1.0.0 (not cached)")
    return LaneInfo(lane="RECORDED-NON-ASTRONAUT", available=True,
                    detail="Verified against the pinned SHA256SUMS manifest",
                    provenance="PhysioNet Wrist PPG During Exercise v1.0.0 · ODC-By 1.0")


def lanes() -> list[LaneInfo]:
    return [
        lab_lane(),
        recorded_lane(),
        LaneInfo(lane="SIMULATED", available=True,
                 detail="Deterministic fixed-formula signals; no device, no measurement",
                 provenance="api/scenarios.py (SIMULATED)"),
        LaneInfo(lane="INJECTED", available=True,
                 detail="Operator-injected test conditions for the gate truth table",
                 provenance="api/scenarios.py (INJECTED)"),
    ]


def m6_results() -> dict[str, Any]:
    """Read-only committed M6 outputs. Never recomputed or altered here."""
    import json

    path = REPO_ROOT / "experiments" / "m6" / "outputs" / "results.json"
    if not path.exists():
        return {"available": False, "detail": "M6 outputs not present", "results": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    keep = {k: v for k, v in data.items()
            if k in {"dataset", "config", "windows", "hr", "activity", "provenance", "schema"}}
    return {"available": True, "detail": "Committed, independently verified M6 outputs",
            "results": keep or data, "lane": "RECORDED-NON-ASTRONAUT",
            "provenance": "experiments/m6/outputs/results.json · PhysioNet · ODC-By 1.0"}


def osdr_manifest() -> dict[str, Any]:
    return load_manifest()
