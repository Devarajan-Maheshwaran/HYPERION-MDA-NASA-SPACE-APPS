"""Deterministic scenario generator. SIMULATED / INJECTED only. Never astronaut data.

Scenarios exist to exercise the gate truth table, including the cases where the gates
*should* alert. They are never tuned to make a gate pass (docs/SAFETY_ISSUES.md).
Every waveform is a fixed formula: same scenario id + same t => same values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import ScenarioInfo


@dataclass(frozen=True)
class Scenario:
    info: ScenarioInfo
    base_hr: float
    hr_wave: float
    activity_base: float
    activity_burst: float
    burst_start: float
    burst_end: float
    artifact: bool = False
    arrhythmia: bool = False
    stale_manual: bool = False
    ceiling: bool = False


def _s(info_id: str, label: str, purpose: str, expected: str, **kw) -> Scenario:
    duration = kw.pop("duration_s", 180.0)
    lane = kw.pop("lane", "SIMULATED")
    return Scenario(
        info=ScenarioInfo(scenario_id=info_id, label=label, purpose=purpose, lane=lane,
                          duration_s=duration, expected=expected),
        **kw,
    )


SCENARIOS: tuple[Scenario, ...] = (
    _s("rest-nominal", "Resting, nominal", "Quiet baseline with no movement",
       "NOMINAL when calibrated; UNKNOWN when not",
       base_hr=68, hr_wave=2, activity_base=1.0, activity_burst=0.0,
       burst_start=999, burst_end=999),
    _s("exercise-false-alarm", "Exercise false alarm",
       "HR near 148 bpm while movement is high — the deck's core case",
       "Gate 2 BLOCKs the rate alarm only if calibrated and below the hard ceiling",
       base_hr=70, hr_wave=2, activity_base=1.0, activity_burst=0.9,
       burst_start=30, burst_end=150),
    _s("exercise-with-arrhythmia", "Exercise + irregular rhythm",
       "The same exercise frame carries a non-rate finding",
       "NEVER suppressed — the non-rate finding escalates",
       base_hr=70, hr_wave=2, activity_base=1.0, activity_burst=0.9,
       burst_start=30, burst_end=150, arrhythmia=True, lane="INJECTED"),
    _s("sensor-artifact", "Sensor artifact",
       "Impulsive spikes and high slew corrupt the window",
       "Gate 1 quarantines the window -> Check sensor",
       base_hr=72, hr_wave=2, activity_base=1.0, activity_burst=0.0,
       burst_start=999, burst_end=999, artifact=True, lane="INJECTED"),
    _s("true-rest-tachycardia", "Resting tachycardia",
       "High heart rate with no movement to explain it",
       "SURGEON_ALERT — the filter must not hide this",
       base_hr=132, hr_wave=3, activity_base=1.0, activity_burst=0.0,
       burst_start=999, burst_end=999, lane="INJECTED"),
    _s("hard-ceiling", "Above the hard ceiling",
       "Very high rate during heavy movement",
       "Alerts regardless of activity (hard ceiling)",
       base_hr=186, hr_wave=2, activity_base=1.0, activity_burst=0.9,
       burst_start=0, burst_end=180, ceiling=True, lane="INJECTED"),
    _s("hold-timeout", "Suppression hold timeout",
       "Continuous exercise suppression past the hold limit",
       "Escalates to SURGEON_ALERT after the hold timeout",
       base_hr=70, hr_wave=2, activity_base=1.0, activity_burst=0.9,
       burst_start=0, burst_end=400, duration_s=400),
    _s("stale-manual", "Stale manual exam",
       "Borderline rate while the last manual check is old",
       "Gate 3 HOLDs the ground alarm and asks for a crew check",
       base_hr=124, hr_wave=2, activity_base=1.0, activity_burst=0.0,
       burst_start=999, burst_end=999, stale_manual=True, lane="INJECTED"),
    _s("uncalibrated", "Uncalibrated person",
       "No per-person calibration exists",
       "All gates UNKNOWN; nothing is shown green",
       base_hr=90, hr_wave=4, activity_base=1.0, activity_burst=0.2,
       burst_start=60, burst_end=120),
)

BY_ID = {s.info.scenario_id: s for s in SCENARIOS}


def catalogue() -> list[ScenarioInfo]:
    return [s.info for s in SCENARIOS]


def sample(scenario_id: str, t_s: float) -> dict:
    """Raw synthetic sample at time t. Values are in arbitrary sensor units, not g."""
    sc = BY_ID[scenario_id]
    active = sc.burst_start <= t_s < sc.burst_end
    magnitude = sc.activity_base + (sc.activity_burst if active else 0.0)
    magnitude += 0.01 * math.sin(2 * math.pi * t_s / 7.0)
    hr = sc.base_hr + sc.hr_wave * math.sin(2 * math.pi * t_s / 23.0)
    if active and not sc.ceiling:
        # Rise into the exercise band, then plateau near 148 bpm.
        ramp = min(1.0, (t_s - sc.burst_start) / 20.0)
        hr += 78.0 * ramp
    if sc.artifact and int(t_s) % 7 == 0:
        hr += 55.0
    window = [hr + 1.5 * math.sin(2 * math.pi * (t_s + k * 0.04)) for k in range(25)]
    if sc.artifact:
        window[12] += 400.0
        window[13] -= 380.0
    flags: list[str] = []
    if sc.arrhythmia and active:
        flags.append("irregular rhythm (injected)")
    return {"hr_bpm": hr, "magnitude": magnitude, "window": window, "non_rate_flags": flags,
            "stale_manual": sc.stale_manual, "lane": sc.info.lane}


def rest_calibration_samples(scenario_id: str = "rest-nominal", n: int = 60) -> list[dict]:
    """A labelled resting window used to calibrate a demo subject.

    This is SIMULATED data. Calibrating from it produces a demo calibration, which the
    API labels as such; it is not a clinical calibration.
    """
    return [sample(scenario_id, float(t)) for t in range(n)]
