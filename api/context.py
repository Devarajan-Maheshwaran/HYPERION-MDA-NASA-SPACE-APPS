"""Declared DEMO context constants for the unified workstation.

These are scenario-engine constants, not fitted physiology and not clinical thresholds.
They exist so the cockpit can show the deck's CO2 / radiation / countermeasure channels
without pretending they are measured astronaut telemetry. The deterministic gate still
uses per-person scale-normalised activity (S2), never ENMO in g.
"""
from __future__ import annotations

# Demo CO2 contribution to expected heart rate above a nominal cabin baseline.
CO2_BASELINE_MMHG = 3.0
CO2_HR_DRIVE_BPM_PER_MMHG = 4.0
CO2_EYE_HOLD_MMHG = 4.0
PROTON_CHEST_ALERT_MGY_DAY = 2.0
WATER_LOW_ML = 1400.0
ARED_LOW_MIN = 20.0


def co2_hr_drive(co2_mmhg: float | None) -> float:
    if co2_mmhg is None:
        return 0.0
    return CO2_HR_DRIVE_BPM_PER_MMHG * max(0.0, co2_mmhg - CO2_BASELINE_MMHG)
