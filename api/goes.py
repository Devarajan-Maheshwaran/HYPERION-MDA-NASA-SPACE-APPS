"""NOAA GOES primary integral-proton lane. Read-only, honest about absence.

The live endpoint is https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json.
This sandbox cannot reach that host, so the loader reads a cached JSON file if one exists
and otherwise reports NOT_AVAILABLE. It never invents a flux value.

GOES integral protons are particle flux (pfu), NOT absorbed dose (mGy/day). No flux→dose
conversion is performed here; that would require a validated transport model. The UI must
show dose as NOT_AVAILABLE unless a dosimetry source exists. Scenario dose values are
SIMULATED and labelled as such by the workstation layer.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from .lanes import cache_dir

GOES_URL = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json"
RELATIVE = Path("goes") / "primary" / "integral-protons-1-day.json"


def cache_root() -> Path:
    return cache_dir() or Path.home() / ".hyperion_mda"


def cached_path() -> Path | None:
    p = cache_root() / RELATIVE
    return p if p.is_file() else None


def _parse(data: Any) -> dict[str, Any]:
    if not isinstance(data, list):
        raise ValueError("GOES JSON must be a list of samples")
    channels: dict[str, dict[str, Any]] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        energy = str(row.get("energy", row.get("channel", "unknown")))
        flux = row.get("flux")
        try:
            flux_f = float(flux) if flux is not None else None
        except (TypeError, ValueError):
            flux_f = None
        channels[energy] = {
            "time_tag": row.get("time_tag"),
            "flux": flux_f,
            "units": row.get("units", "pfu"),
        }
    return {"sample_count": len(data), "channels": channels}


def load(fetch: bool = False, timeout_s: float = 3.0) -> dict[str, Any]:
    """Return availability + parsed channels. Network is attempted only when fetch=True."""
    path = cached_path()
    if path is not None:
        try:
            parsed = _parse(json.loads(path.read_text(encoding="utf-8")))
            return {"available": True, "source": "cached JSON", "path": str(path),
                    "url": GOES_URL, "dose_mgy_day": None,
                    "dose_note": "GOES flux is pfu, not mGy/day; no validated conversion exists here.",
                    **parsed}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {"available": False, "source": "cached JSON", "detail": f"cache unreadable: {exc}",
                    "url": GOES_URL, "channels": {}, "dose_mgy_day": None}
    if fetch:
        try:
            req = urllib.request.Request(GOES_URL, headers={"User-Agent": "HYPERION-MDA-demo"})
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (fixed URL)
                data = json.loads(resp.read().decode("utf-8"))
            parsed = _parse(data)
            cache_file = cache_root() / RELATIVE
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                tmp = cache_file.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(data), encoding="utf-8")
                tmp.replace(cache_file)
            except OSError:
                pass  # live data is still returned; caching is best-effort
            return {"available": True, "source": "live NOAA SWPC", "url": GOES_URL,
                    "dose_mgy_day": None, "cached_path": str(cache_file), **parsed}
        except Exception as exc:  # network blocked, TLS, timeout — all reported honestly
            return {"available": False, "source": "live NOAA SWPC",
                    "detail": f"fetch failed: {exc}", "url": GOES_URL,
                    "channels": {}, "dose_mgy_day": None}
    return {"available": False, "source": "not cached",
            "detail": "No cached GOES JSON and live fetch not requested. "
                      "Set HYPERION_MDA_DATA_DIR and place the file at goes/primary/integral-protons-1-day.json, "
                      "or POST /api/goes/refresh to attempt the network.",
            "url": GOES_URL, "channels": {}, "dose_mgy_day": None}
