"""Real wearable-feature availability. Never fabricates a waveform feature.

WESAD is gate NO-GO in the existing registry. PhysioNet recordings are non-astronaut and
only usable when the verified cache exists AND numpy/scipy are installed. If either is
missing, every feature is NOT_AVAILABLE with the real reason.
"""
from __future__ import annotations

from typing import Any

from . import lanes

FEATURES = ("hr", "rmssd", "enmo", "ecg_kurtosis", "temp", "resp")


def status() -> dict[str, Any]:
    recorded = lanes.recorded_lane()
    if not recorded.available:
        return {"available": False, "lane": recorded.lane, "detail": recorded.detail,
                "provenance": recorded.provenance,
                "features": {f: None for f in FEATURES},
                "wesad": "NO-GO: terms/labels/checksums unverified in signal_registry"}
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401
    except ImportError:
        return {"available": False, "lane": recorded.lane,
                "detail": "Verified cache present but numpy/scipy are not installed in the API environment.",
                "provenance": recorded.provenance,
                "features": {f: None for f in FEATURES},
                "wesad": "NO-GO"}
    # Cache + deps present. Computing full DSP on every /api/state call would be slow and
    # is not wired into the live decision path; report the verified source and leave the
    # live feature values to the existing offline M6 pipeline rather than inventing them.
    return {"available": True, "lane": recorded.lane,
            "detail": "Verified non-astronaut cache present. Live feature extraction is not "
                      "wired into the decision path; see read-only M6 outputs for measured results.",
            "provenance": recorded.provenance,
            "features": {f: None for f in FEATURES},
            "wesad": "NO-GO"}
