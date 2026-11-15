"""The three-stage deterministic trust gate.

No neural network and no LLM participates. Every verdict is a pure function of the
frame, the subject's calibration and the suppression hold clock, so the truth table is
testable and reproducible.

Deliberate deviations from the concept deck (docs/SAFETY_ISSUES.md):
  S1  Gate 1 has NO default kurtosis cutoff. Uncalibrated -> UNKNOWN, never PASS.
  S2  Activity is per-person scale-normalised (dimensionless), never ENMO in g.
  S3  Non-rate flags are never suppressed by the exercise filter.
  S4  A hard HR ceiling and a suppression hold timeout bound the filter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .actions import (CHECK_SENSOR, CONTACT_FLIGHT_SURGEON, REPEAT_MEASUREMENT,
                      REST_AND_RECHECK, actions_for)
from .context import CO2_EYE_HOLD_MMHG, co2_hr_drive
from .models import Calibration, Frame, GateVerdict, SqReading

# --- Declared demo limits. Not clinical thresholds. See docs/SAFETY_ISSUES.md S4. ---
HARD_HR_CEILING_BPM = 180.0
MAX_SUPPRESSION_HOLD_S = 120.0
REST_TACHYCARDIA_BPM = 115.0          # the deck's claim, used as a DEMO rule only
RESIDUAL_SIGMA_BLOCK = 2.0            # residual below this many personal scales -> explained
ACTIVITY_ELEVATED_NORM = 2.0          # per-person rest scales, dimensionless
STALE_TAU_HOLD = 0.5                  # tau below this -> ask for a crew check first

# Declared DEMO context-model constants (docs/SAFETY_ISSUES.md S12). A heart-rate response
# to workload saturates; a straight line does not. These are not clinical values and are
# not fitted to any scenario outcome.
HR_RESERVE_BPM = 80.0                 # demo per-person reserve above resting median
ACTIVITY_SATURATION_SCALE = 6.0       # personal rest scales at which the response saturates

NOT_CALIBRATED = "not calibrated for this person"


def kurtosis(values: list[float]) -> float | None:
    """Fourth-moment kurtosis (not excess). None when it cannot be computed."""
    n = len(values)
    if n < 4:
        return None
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    if var <= 0:
        return None
    return (sum((v - mean) ** 4 for v in values) / n) / (var ** 2)


def slew_rate(values: list[float], fs_hz: float) -> float | None:
    """Maximum absolute first difference per second."""
    if len(values) < 2 or fs_hz <= 0:
        return None
    return max(abs(b - a) for a, b in zip(values, values[1:])) * fs_hz


@dataclass
class HoldClock:
    """Tracks continuous suppression so it cannot hide a problem indefinitely (S4).

    `peek` is side-effect free: it reports how long suppression would have been running if
    it continues this frame. `commit` then records the actual decision. Splitting the two
    matters — an earlier version reset the clock while measuring it, so the timeout could
    never fire.
    """

    held_since: float | None = None
    last_t: float | None = None
    latched: bool = False

    def peek(self, t_s: float) -> float:
        return 0.0 if self.held_since is None else max(0.0, t_s - self.held_since)

    def commit(self, t_s: float, suppressing: bool) -> float:
        if not suppressing:
            self.held_since = None
            self.last_t = t_s
            return 0.0
        if self.held_since is None:
            self.held_since = t_s
        self.last_t = t_s
        return t_s - self.held_since

    def latch(self) -> None:
        """Once the hold limit is reached, suppression stays off until an explicit reset.

        Without this the clock would restart and re-suppress the very next frame, turning a
        sustained problem back into a green 'context compensated' display.
        """
        self.latched = True
        self.held_since = None

    def reset(self) -> None:
        self.held_since = None
        self.last_t = None
        self.latched = False


@dataclass
class GateInput:
    t_s: float
    hr_bpm: float | None
    activity_norm: float | None
    sqi: SqReading
    non_rate_flags: list[str] = field(default_factory=list)
    stale_manual: bool = False
    min_tau: float | None = None
    hr_status: str = "UNKNOWN"
    co2_mmhg: float | None = None
    onsd_tau: float | None = None


def gate1_sensor(inp: GateInput, cal: Calibration) -> GateVerdict:
    """Sensor quality. Uncalibrated is UNKNOWN, never a silent pass (S1)."""
    evidence = {
        "kurtosis": inp.sqi.kurtosis,
        "slew": inp.sqi.slew,
        "calibrated": cal.calibrated,
        "kurtosis_low": cal.kurtosis_low,
        "kurtosis_high": cal.kurtosis_high,
        "slew_high": cal.slew_high,
    }
    if not cal.calibrated:
        return GateVerdict(gate=1, outcome="UNKNOWN", reason=NOT_CALIBRATED, evidence=evidence)
    if inp.sqi.kurtosis is None or inp.sqi.slew is None:
        return GateVerdict(gate=1, outcome="UNKNOWN", reason="sensor window unavailable",
                           evidence=evidence)
    low, high, slew_high = cal.kurtosis_low, cal.kurtosis_high, cal.slew_high
    if low is None or high is None or slew_high is None:
        return GateVerdict(gate=1, outcome="UNKNOWN", reason="calibration incomplete",
                           evidence=evidence)
    if inp.sqi.kurtosis < low or inp.sqi.kurtosis > high or inp.sqi.slew > slew_high:
        return GateVerdict(gate=1, outcome="BLOCK",
                           reason="window outside this person's calibrated sensor envelope",
                           evidence=evidence)
    return GateVerdict(gate=1, outcome="PASS", reason="within calibrated sensor envelope",
                       evidence=evidence)


def gate2_exercise(inp: GateInput, cal: Calibration, residual: float | None,
                   hold_s: float, latched: bool = False) -> GateVerdict:
    """Exercise filter with a hard ceiling, a hold timeout and a non-rate bypass."""
    evidence = {
        "hr_bpm": inp.hr_bpm,
        "activity_norm": inp.activity_norm,
        "activity_unit": "per-person rest scale (dimensionless)",
        "residual_bpm": residual,
        "hard_ceiling_bpm": HARD_HR_CEILING_BPM,
        "hold_s": round(hold_s, 3),
        "max_hold_s": MAX_SUPPRESSION_HOLD_S,
        "non_rate_flags": list(inp.non_rate_flags),
        "calibrated": cal.calibrated,
        "hold_latched": latched,
        "co2_mmhg": inp.co2_mmhg,
        "co2_hr_drive_bpm": round(co2_hr_drive(inp.co2_mmhg), 3),
    }
    # S3: a non-rate finding is never explained away by movement.
    if inp.non_rate_flags:
        return GateVerdict(gate=2, outcome="PASS",
                           reason="non-rate finding present; exercise filter does not apply",
                           evidence=evidence)
    if inp.hr_bpm is None:
        return GateVerdict(gate=2, outcome="UNKNOWN", reason="heart rate unavailable",
                           evidence=evidence)
    # S4: above the hard ceiling, movement never explains the rate.
    if inp.hr_bpm >= HARD_HR_CEILING_BPM:
        return GateVerdict(gate=2, outcome="PASS",
                           reason=f"at or above hard ceiling {HARD_HR_CEILING_BPM:g} bpm",
                           evidence=evidence)
    if not cal.calibrated or inp.activity_norm is None or residual is None:
        return GateVerdict(gate=2, outcome="UNKNOWN", reason=NOT_CALIBRATED, evidence=evidence)
    if cal.rest_hr_scale is None or cal.rest_hr_scale <= 0:
        return GateVerdict(gate=2, outcome="UNKNOWN", reason="calibration incomplete",
                           evidence=evidence)
    # S4: suppression may not persist beyond the hold limit, and once it has been reached
    # it stays off until an explicit reset (scenario restart or recalibration).
    if latched or hold_s >= MAX_SUPPRESSION_HOLD_S:
        return GateVerdict(gate=2, outcome="PASS", reason="suppression hold timeout",
                           evidence=evidence)
    # BLOCK means "an alarm that would otherwise fire is being suppressed". If the rate is
    # not in the alert band there is nothing to block, and claiming a block would be
    # misleading in the UI.
    if inp.hr_bpm <= REST_TACHYCARDIA_BPM:
        return GateVerdict(gate=2, outcome="PASS",
                           reason="rate below the demo alert band; nothing to block",
                           evidence=evidence)
    elevated = inp.activity_norm >= ACTIVITY_ELEVATED_NORM
    # One-sided: a rate at or below what the workload predicts is explained by it. A rate
    # ABOVE the prediction by more than the personal band is not, however hard the exercise.
    explained = residual < RESIDUAL_SIGMA_BLOCK * cal.rest_hr_scale
    if elevated and explained:
        return GateVerdict(gate=2, outcome="BLOCK",
                           reason="rate explained by this person's activity scale",
                           evidence=evidence)
    return GateVerdict(gate=2, outcome="PASS", reason="rate not explained by activity",
                       evidence=evidence)


def gate3_uncertainty(inp: GateInput, cal: Calibration, would_alert: bool) -> GateVerdict:
    """Active sensing: hold a ground alarm when staleness, not the signal, drives risk."""
    evidence = {
        "min_tau": inp.min_tau,
        "stale_manual": inp.stale_manual,
        "hold_tau_threshold": STALE_TAU_HOLD,
        "would_alert": would_alert,
        "band": "empirical residual quantile (demo, no coverage guarantee)",
        "co2_mmhg": inp.co2_mmhg,
        "onsd_tau": inp.onsd_tau,
        "requested_exam": None,
    }
    if not would_alert:
        return GateVerdict(gate=3, outcome="PASS", reason="no rate alarm to hold",
                           evidence=evidence)
    # A non-rate finding is never held for a manual check (S3).
    if inp.non_rate_flags:
        return GateVerdict(gate=3, outcome="PASS", reason="non-rate finding is not held",
                           evidence=evidence)
    if (inp.co2_mmhg is not None and inp.co2_mmhg >= CO2_EYE_HOLD_MMHG
            and inp.onsd_tau is not None and inp.onsd_tau < STALE_TAU_HOLD):
        evidence["requested_exam"] = "ultrasound"
        return GateVerdict(gate=3, outcome="HOLD",
                           reason="cabin CO2 elevated and eye scan stale; request guided ONSD ultrasound",
                           evidence=evidence)
    if inp.stale_manual and inp.min_tau is not None and inp.min_tau < STALE_TAU_HOLD:
        return GateVerdict(gate=3, outcome="HOLD",
                           reason="manual exam stale; request the fastest crew check first",
                           evidence=evidence)
    return GateVerdict(gate=3, outcome="PASS", reason="manual context current or absent",
                       evidence=evidence)


def personal_residual(hr_bpm: float | None, activity_norm: float | None,
                      cal: Calibration, co2_mmhg: float | None = None) -> float | None:
    """Expected-rate removal using this person's own resting scale.

    A transparent saturating context model:
        expected = rest_median + HR_RESERVE * (1 - exp(-activity_norm / SATURATION))
    It is a DEMO context model, not a fitted physiological model, and it is bounded: as
    activity grows the expectation approaches rest_median + reserve rather than running
    away linearly. Residual = observed - expected. See docs/SAFETY_ISSUES.md S12.
    """
    if hr_bpm is None or activity_norm is None or not cal.calibrated:
        return None
    if cal.rest_hr_median is None or cal.rest_hr_scale is None or cal.rest_hr_scale <= 0:
        return None
    drive = 1.0 - math.exp(-max(0.0, activity_norm) / ACTIVITY_SATURATION_SCALE)
    expected = cal.rest_hr_median + HR_RESERVE_BPM * drive + co2_hr_drive(co2_mmhg)
    return hr_bpm - expected


def evaluate(inp: GateInput, cal: Calibration, hold: HoldClock) -> Frame:
    """Run all three gates and map to a workflow state. Pure except for the hold clock."""
    residual = personal_residual(inp.hr_bpm, inp.activity_norm, cal, inp.co2_mmhg)

    # Measure how long suppression has already run, decide, then commit the decision.
    hold_s = hold.peek(inp.t_s)
    g1 = gate1_sensor(inp, cal)
    g2 = gate2_exercise(inp, cal, residual, hold_s, latched=hold.latched)
    suppressed = g2.outcome == "BLOCK"
    hold_s = hold.commit(inp.t_s, suppressed)
    hold_expired = (not suppressed) and g2.reason == "suppression hold timeout"
    if hold_expired:
        hold.latch()

    rate_alarm = (
        inp.hr_bpm is not None
        and cal.calibrated
        and (inp.hr_bpm >= HARD_HR_CEILING_BPM
             or hold_expired
             or (not suppressed and residual is not None and cal.rest_hr_scale
                 and residual >= RESIDUAL_SIGMA_BLOCK * cal.rest_hr_scale
                 and inp.hr_bpm > REST_TACHYCARDIA_BPM))
    )
    non_rate = bool(inp.non_rate_flags)
    g3 = gate3_uncertainty(inp, cal, bool(rate_alarm))

    frame = Frame(
        t_s=inp.t_s, lane="NONE", subject_id=cal.subject_id, habitat="Space Station (0g)",
        hr_bpm=inp.hr_bpm, hr_status=inp.hr_status, activity_norm=inp.activity_norm,
        sqi=inp.sqi, gates=[g1, g2, g3], residual_bpm=residual,
        suppressed=suppressed,
        suppression_reason=g2.reason if suppressed else None,
        non_rate_flags=list(inp.non_rate_flags), scenario_id=None,
    )
    if cal.calibrated and cal.residual_q95 is not None and residual is not None:
        frame.band_upper = residual + cal.residual_q95
        frame.band_lower = residual - cal.residual_q95

    # --- State mapping. UNKNOWN and sensor issues can never be NOMINAL. ---
    if g1.outcome == "BLOCK":
        frame.state = "SENSOR_ISSUE"
        frame.actions = actions_for(CHECK_SENSOR, REPEAT_MEASUREMENT)
    elif non_rate:
        frame.state = "SURGEON_ALERT"
        frame.actions = actions_for(CONTACT_FLIGHT_SURGEON, REPEAT_MEASUREMENT)
    elif not cal.calibrated or inp.hr_bpm is None or g1.outcome == "UNKNOWN":
        frame.state = "UNKNOWN"
        frame.actions = actions_for(CHECK_SENSOR, REPEAT_MEASUREMENT)
    elif g3.outcome == "HOLD":
        frame.state = "CREW_CHECK"
        frame.actions = actions_for(REPEAT_MEASUREMENT, REST_AND_RECHECK)
    elif rate_alarm:
        frame.state = "SURGEON_ALERT"
        frame.actions = actions_for(REST_AND_RECHECK, CONTACT_FLIGHT_SURGEON)
    elif suppressed:
        frame.state = "CONTEXT_COMPENSATED"
        frame.actions = actions_for(REST_AND_RECHECK)
    else:
        frame.state = "NOMINAL"
        frame.actions = actions_for(REPEAT_MEASUREMENT)
    return frame


def normalise_activity(magnitude: float | None, cal: Calibration) -> float | None:
    """Per-person, scale-normalised activity. Dimensionless. Never ENMO in g (S2)."""
    if magnitude is None or not cal.calibrated:
        return None
    if cal.rest_activity_median is None or cal.rest_activity_scale is None:
        return None
    if cal.rest_activity_scale <= 0 or not math.isfinite(cal.rest_activity_scale):
        return None
    return (magnitude - cal.rest_activity_median) / cal.rest_activity_scale
