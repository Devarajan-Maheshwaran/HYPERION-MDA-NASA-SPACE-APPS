"""Recorded human replay lane (P0-4): RECORDED-NON-ASTRONAUT.

Source
------
`experiments/m6/outputs/windows.csv` — committed, openly licensed (ODC-By 1.0) derived
output of the audited M5/M6 PhysioNet pipeline. Each row is one real 8-second window from
the PhysioNet *Wrist PPG During Exercise* v1.0.0 dataset (8 adults, terrestrial lab exercise):

* `ref_hr_bpm`  — heart rate from the hand-marked chest-ECG R peaks in that window
                  (60 / median RR). This is a MEASURED reference, not a PPG estimate.
* `accel_mag_median_uncalibrated` — median wrist accelerometer magnitude, header units.
                  Uncalibrated: it is NOT ENMO in g and is never presented as such.
* `ref_beats`, `rr_screen_ok` — real window-quality metadata from the annotation file.

Honesty rules
-------------
* Nothing is synthesised. A window with no reference HR replays as `hr_bpm=None`.
* One window is replayed per mission second, so the stream is explicitly TIME-COMPRESSED
  (8 s of recording per 1 s of mission clock). The banner and every payload say so.
* These are terrestrial non-astronaut adults. No astronaut, NASA or CSA data is involved.
* The lane never merges with the NASA lab lane or the simulated scenario lane.
* Gate 1 uses the recorded RR-screen quality basis, not an invented PPG kurtosis: the
  raw waveform is not in this repository, so no waveform SQI statistic is fabricated.
"""
from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_CSV = REPO_ROOT / "experiments" / "m6" / "outputs" / "windows.csv"

PROVENANCE = ("PhysioNet Wrist PPG During Exercise v1.0.0 · RECORDED-NON-ASTRONAUT · ODC-By 1.0 · "
              "ECG-derived reference HR per 8 s window, time-compressed to 1 Hz")
DETAIL = ("Real recorded windows from 8 terrestrial adults. Not astronaut telemetry. "
          "Heart rate is the chest-ECG annotation reference, not a wearable estimate.")


@dataclass(frozen=True)
class ReplayWindow:
    participant: str
    record: str
    activity: str
    start_sample: int
    hr_bpm: float | None
    ref_beats: int
    rr_screen_ok: bool
    accel_magnitude: float | None


def _float(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None  # NaN -> None


def available() -> bool:
    return WINDOWS_CSV.is_file()


def participants() -> list[str]:
    if not available():
        return []
    with WINDOWS_CSV.open(newline="", encoding="utf-8") as fh:
        return sorted({row["participant"] for row in csv.DictReader(fh)})


def load(participant: str) -> list[ReplayWindow]:
    """All windows for one participant, ordered by record then sample offset."""
    if not available():
        return []
    out: list[ReplayWindow] = []
    with WINDOWS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["participant"] != participant:
                continue
            beats = int(row["ref_beats"] or 0)
            out.append(ReplayWindow(
                participant=row["participant"], record=row["record"], activity=row["activity"],
                start_sample=int(row["start_sample"]), hr_bpm=_float(row["ref_hr_bpm"]),
                ref_beats=beats, rr_screen_ok=row["rr_screen_ok"] == "1",
                accel_magnitude=_float(row["accel_mag_median_uncalibrated"]),
            ))
    out.sort(key=lambda w: (w.record, w.start_sample))
    return out


def status() -> dict[str, Any]:
    if not available():
        return {"available": False, "lane": "RECORDED-NON-ASTRONAUT",
                "detail": f"{WINDOWS_CSV.name} is not present; recorded replay cannot start.",
                "provenance": PROVENANCE, "participants": [], "n_windows": 0}
    people = participants()
    total = sum(len(load(p)) for p in people)
    return {"available": True, "lane": "RECORDED-NON-ASTRONAUT", "detail": DETAIL,
            "provenance": PROVENANCE, "participants": people, "n_participants": len(people),
            "n_windows": total, "source_file": str(WINDOWS_CSV.relative_to(REPO_ROOT)),
            "window_s": 8.0, "replay_rate_hz": 1.0, "time_compressed": True}


def calibration_values(windows: list[ReplayWindow]) -> dict[str, float | None]:
    """Descriptive per-participant centre/scale from that participant's own windows.

    Labelled a recorded-derived DEMO calibration: it exists so the deterministic gate can
    run on this lane, and it is never presented as a clinical calibration.
    """
    hrs = [w.hr_bpm for w in windows if w.hr_bpm is not None]
    mags = [w.accel_magnitude for w in windows if w.accel_magnitude is not None]
    if not hrs or not mags:
        return {"rest_hr_median": None, "rest_hr_scale": None,
                "rest_activity_median": None, "rest_activity_scale": None, "residual_q95": None}
    hr_median = statistics.median(hrs)
    hr_scale = statistics.pstdev(hrs) or 1.0
    residuals = sorted(abs(h - hr_median) for h in hrs)
    q95 = residuals[max(0, int(0.95 * len(residuals)) - 1)]
    return {"rest_hr_median": hr_median, "rest_hr_scale": hr_scale,
            "rest_activity_median": statistics.median(mags),
            "rest_activity_scale": statistics.pstdev(mags) or 0.01,
            "residual_q95": q95}


def sample(windows: list[ReplayWindow], t_s: float) -> dict[str, Any]:
    """Frame inputs at mission second `t_s`. Deterministic and index-based, never random."""
    if not windows:
        return {"hr_bpm": None, "magnitude": None, "window": [], "non_rate_flags": [],
                "stale_manual": False, "lane": "RECORDED-NON-ASTRONAUT",
                "recorded_quality": {"available": False}, "record": None, "activity": None,
                "window_index": 0}
    index = int(max(0.0, t_s)) % len(windows)
    w = windows[index]
    return {
        "hr_bpm": w.hr_bpm, "magnitude": w.accel_magnitude, "window": [],
        "non_rate_flags": [], "stale_manual": False, "lane": "RECORDED-NON-ASTRONAUT",
        "recorded_quality": {"available": True, "rr_screen_ok": w.rr_screen_ok,
                             "ref_beats": w.ref_beats, "basis": "RECORDED_RR_SCREEN",
                             "source": "hand-marked chest-ECG annotations (.atr), M5 reader"},
        "record": w.record, "activity": w.activity, "participant": w.participant,
        "window_index": index, "start_sample": w.start_sample,
    }
