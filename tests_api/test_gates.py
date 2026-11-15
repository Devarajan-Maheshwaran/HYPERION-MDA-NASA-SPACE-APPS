"""Gate truth table and safety invariants.

These tests assert the behaviour documented in docs/SAFETY_ISSUES.md. If a gate constant
changes, these fail — they are the guard against tuning gates to make a demo look good.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.gates import (ACTIVITY_ELEVATED_NORM, HARD_HR_CEILING_BPM,  # noqa: E402
                       MAX_SUPPRESSION_HOLD_S, GateInput, HoldClock, evaluate,
                       gate1_sensor, gate2_exercise, kurtosis, normalise_activity,
                       personal_residual, slew_rate)
from api.models import Calibration, SqReading  # noqa: E402


def calibrated(subject: str = "s1") -> Calibration:
    return Calibration(
        subject_id=subject, calibrated=True, n_windows=60, lane="SIMULATED",
        source="test fixture", rest_hr_median=68.0, rest_hr_scale=2.0,
        rest_activity_median=1.0, rest_activity_scale=0.01, residual_q95=4.0,
        kurtosis_low=1.5, kurtosis_high=6.0, slew_high=500.0,
    )


def inp(**kw) -> GateInput:
    base = dict(t_s=1.0, hr_bpm=70.0, activity_norm=0.0,
                sqi=SqReading(kurtosis=3.0, slew=10.0, calibrated=True), hr_status="OK")
    base.update(kw)
    return GateInput(**base)


class HelperTests(unittest.TestCase):
    def test_kurtosis_needs_four_samples(self):
        self.assertIsNone(kurtosis([1.0, 2.0, 3.0]))
        self.assertIsNone(kurtosis([5.0] * 10))  # zero variance
        self.assertIsNotNone(kurtosis([1.0, 2.0, 3.0, 9.0]))

    def test_slew_rate(self):
        self.assertEqual(slew_rate([0.0, 1.0, 0.0], 2.0), 2.0)
        self.assertIsNone(slew_rate([1.0], 2.0))

    def test_activity_is_dimensionless_and_uncalibrated_is_none(self):
        self.assertIsNone(normalise_activity(1.5, Calibration(subject_id="s1")))
        self.assertAlmostEqual(normalise_activity(1.02, calibrated()), 2.0)


class Gate1Tests(unittest.TestCase):
    def test_uncalibrated_is_unknown_never_pass(self):
        v = gate1_sensor(inp(), Calibration(subject_id="s1"))
        self.assertEqual(v.outcome, "UNKNOWN")
        self.assertIn("not calibrated", v.reason)

    def test_inside_envelope_passes(self):
        self.assertEqual(gate1_sensor(inp(), calibrated()).outcome, "PASS")

    def test_outside_envelope_blocks(self):
        v = gate1_sensor(inp(sqi=SqReading(kurtosis=20.0, slew=10.0)), calibrated())
        self.assertEqual(v.outcome, "BLOCK")

    def test_high_slew_blocks(self):
        v = gate1_sensor(inp(sqi=SqReading(kurtosis=3.0, slew=9999.0)), calibrated())
        self.assertEqual(v.outcome, "BLOCK")

    def test_missing_window_is_unknown(self):
        v = gate1_sensor(inp(sqi=SqReading(kurtosis=None, slew=None)), calibrated())
        self.assertEqual(v.outcome, "UNKNOWN")

    def test_no_default_kurtosis_threshold_ships(self):
        """S1: an empty calibration must carry no usable threshold, so Gate 1 cannot pass."""
        empty = Calibration(subject_id="s1")
        self.assertIsNone(empty.kurtosis_low)
        self.assertIsNone(empty.kurtosis_high)
        self.assertIsNone(empty.slew_high)
        self.assertFalse(empty.calibrated)
        self.assertEqual(gate1_sensor(inp(), empty).outcome, "UNKNOWN")


class Gate2Tests(unittest.TestCase):
    def test_non_rate_flags_are_never_suppressed(self):
        """S3: the single most important invariant."""
        cal = calibrated()
        i = inp(hr_bpm=148.0, activity_norm=100.0, non_rate_flags=["irregular rhythm"])
        residual = personal_residual(i.hr_bpm, i.activity_norm, cal)
        v = gate2_exercise(i, cal, residual, 0.0)
        self.assertEqual(v.outcome, "PASS")
        frame = evaluate(i, cal, HoldClock())
        self.assertFalse(frame.suppressed)
        self.assertEqual(frame.state, "SURGEON_ALERT")

    def test_hard_ceiling_overrides_exercise(self):
        cal = calibrated()
        i = inp(hr_bpm=HARD_HR_CEILING_BPM + 5, activity_norm=100.0)
        residual = personal_residual(i.hr_bpm, i.activity_norm, cal)
        v = gate2_exercise(i, cal, residual, 0.0)
        self.assertEqual(v.outcome, "PASS")
        self.assertIn("hard ceiling", v.reason)
        self.assertEqual(evaluate(i, cal, HoldClock()).state, "SURGEON_ALERT")

    def test_explained_exercise_is_blocked(self):
        cal = calibrated()
        i = inp(hr_bpm=147.0, activity_norm=100.0)
        residual = personal_residual(i.hr_bpm, i.activity_norm, cal)
        self.assertEqual(gate2_exercise(i, cal, residual, 0.0).outcome, "BLOCK")
        self.assertEqual(evaluate(i, cal, HoldClock()).state, "CONTEXT_COMPENSATED")

    def test_unexplained_rate_is_not_blocked(self):
        cal = calibrated()
        i = inp(hr_bpm=190.0 - 60, activity_norm=ACTIVITY_ELEVATED_NORM)
        residual = personal_residual(i.hr_bpm, i.activity_norm, cal)
        self.assertEqual(gate2_exercise(i, cal, residual, 0.0).outcome, "PASS")

    def test_rest_tachycardia_alerts(self):
        frame = evaluate(inp(hr_bpm=130.0, activity_norm=0.0), calibrated(), HoldClock())
        self.assertEqual(frame.state, "SURGEON_ALERT")

    def test_uncalibrated_cannot_suppress(self):
        cal = Calibration(subject_id="s1")
        i = inp(hr_bpm=148.0, activity_norm=None)
        self.assertEqual(gate2_exercise(i, cal, None, 0.0).outcome, "UNKNOWN")
        self.assertFalse(evaluate(i, cal, HoldClock()).suppressed)

    def test_hold_timeout_latches(self):
        """S4: after the hold limit, suppression stays off until reset."""
        cal, hold = calibrated(), HoldClock()
        i = inp(hr_bpm=147.0, activity_norm=100.0)
        first = evaluate(i, cal, hold)
        self.assertTrue(first.suppressed)
        late = evaluate(inp(t_s=MAX_SUPPRESSION_HOLD_S + 1, hr_bpm=147.0, activity_norm=100.0),
                        cal, hold)
        self.assertFalse(late.suppressed)
        self.assertEqual(late.state, "SURGEON_ALERT")
        # A later frame must not silently resume suppression.
        again = evaluate(inp(t_s=MAX_SUPPRESSION_HOLD_S + 50, hr_bpm=147.0, activity_norm=100.0),
                         cal, hold)
        self.assertFalse(again.suppressed)
        self.assertTrue(hold.latched)
        hold.reset()
        self.assertFalse(hold.latched)

    def test_residual_model_is_bounded(self):
        """S12: expectation saturates; it must not run away with activity."""
        cal = calibrated()
        r_low = personal_residual(150.0, 10.0, cal)
        r_high = personal_residual(150.0, 100000.0, cal)
        self.assertIsNotNone(r_low)
        self.assertIsNotNone(r_high)
        self.assertGreater(r_high, -1000.0)
        self.assertLess(abs(r_high - r_low), 100.0)


class Gate3Tests(unittest.TestCase):
    def test_stale_manual_holds_ground_alarm(self):
        frame = evaluate(inp(hr_bpm=125.0, stale_manual=True, min_tau=0.1),
                         calibrated(), HoldClock())
        self.assertEqual(frame.gates[2].outcome, "HOLD")
        self.assertEqual(frame.state, "CREW_CHECK")

    def test_non_rate_finding_is_never_held(self):
        frame = evaluate(inp(hr_bpm=125.0, stale_manual=True, min_tau=0.1,
                             non_rate_flags=["irregular rhythm"]), calibrated(), HoldClock())
        self.assertNotEqual(frame.gates[2].outcome, "HOLD")
        self.assertEqual(frame.state, "SURGEON_ALERT")

    def test_current_manual_does_not_hold(self):
        frame = evaluate(inp(hr_bpm=130.0, stale_manual=False, min_tau=0.9),
                         calibrated(), HoldClock())
        self.assertEqual(frame.state, "SURGEON_ALERT")


class StateMappingTests(unittest.TestCase):
    def test_uncalibrated_is_never_nominal(self):
        frame = evaluate(inp(), Calibration(subject_id="s1"), HoldClock())
        self.assertEqual(frame.state, "UNKNOWN")

    def test_missing_hr_is_never_nominal(self):
        frame = evaluate(inp(hr_bpm=None, hr_status="NOT_AVAILABLE"), calibrated(), HoldClock())
        self.assertEqual(frame.state, "UNKNOWN")

    def test_sensor_issue_wins_over_rate(self):
        frame = evaluate(inp(hr_bpm=150.0, sqi=SqReading(kurtosis=99.0, slew=1.0)),
                         calibrated(), HoldClock())
        self.assertEqual(frame.state, "SENSOR_ISSUE")
        self.assertIn("Check sensor", frame.actions)


if __name__ == "__main__":
    unittest.main()
