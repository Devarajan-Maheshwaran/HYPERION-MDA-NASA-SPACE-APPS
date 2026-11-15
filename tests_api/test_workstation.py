"""Unified workstation endpoints, dual-mode honesty, exams and demo math."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from api.actions import ALLOWED_ACTIONS  # noqa: E402
from api.conformal import split_conformal_quantile, upper_bound  # noqa: E402
from api.main import create_app  # noqa: E402
from api.models import DISCLAIMER  # noqa: E402
from api.robust import bitflip_demo, cosine_median  # noqa: E402
from api.workstation import onsd_from_pixels  # noqa: E402

OPS = {"x-role": "ops"}
CREW = {"x-role": "crew"}


def client() -> TestClient:
    return TestClient(create_app())


class MathTests(unittest.TestCase):
    def test_conformal_quantile_finite_sample(self):
        self.assertAlmostEqual(split_conformal_quantile([1, 2, 3, 4, 5], 0.2), 5)
        self.assertIsNone(split_conformal_quantile([], 0.1))
        self.assertIsNone(split_conformal_quantile([1], 0.0))
        ub = upper_bound(70.0, [1, 2, 3, 4], 0.1)
        self.assertEqual(ub["upper"], 74.0)
        self.assertIsNone(ub["sigma_epistemic"])
        self.assertIn("no coverage guarantee", ub["label"])

    def test_cosine_median_rejects_bitflip(self):
        vectors = [(1.0, 0.9), (1.1, 1.0), (0.9, 1.1), (1.0, 1.05)]
        result = bitflip_demo(vectors, silo_index=1)
        self.assertTrue(result["caught"])
        self.assertEqual(result["rejected"][0]["silo_index"], 1)
        clean = cosine_median(vectors, trim=0)
        self.assertEqual(len(clean["kept"]), 4)

    def test_onsd_caliper_math(self):
        self.assertAlmostEqual(onsd_from_pixels(0, 0, 92, 0, 20.0), 4.6)
        with self.assertRaises(ValueError):
            onsd_from_pixels(0, 0, 1, 1, 0.0)


class StateTests(unittest.TestCase):
    def test_state_envelope_and_honesty(self):
        body = client().get("/api/state").json()
        self.assertEqual(body["disclaimer"], DISCLAIMER)
        self.assertIn(body["data_source_mode"], {"REAL_EMPIRICAL", "SIMULATED_FALLBACK"})
        self.assertEqual(body["telemetry_mode"], "SIMULATED_FALLBACK")
        self.assertIn("SIMULATED", body["provenance_banner"])
        self.assertEqual(len(body["organs"]), 6)
        self.assertIsNone(body["conformal"]["sigma_epistemic"])
        self.assertIn("NOT deployed", body["audit"]["contract"])
        self.assertTrue(body["ml_benchmark"]["not_implemented"])
        self.assertFalse(body["sources"]["goes"]["available"])

    def test_nominal_scenario_is_all_green(self):
        body = client().post("/api/scenario", json={"scenario_id": "nominal-orbital"}, headers=CREW).json()
        self.assertEqual(body["frame"]["state"], "NOMINAL")
        self.assertTrue(all(g["outcome"] == "PASS" for g in body["gates"]))
        self.assertTrue(all(o["status"] == "NOMINAL" for o in body["organs"]))
        self.assertEqual(body["triage"]["tier"], "NOMINAL")

    def test_exercise_scenario_blocks_false_alarm(self):
        c = client()
        body = c.post("/api/scenario", json={"scenario_id": "eva-ared-exercise"}, headers=CREW).json()
        self.assertEqual(body["data_source_mode"], "SIMULATED_FALLBACK")
        self.assertEqual(body["habitat"], "rover")
        self.assertAlmostEqual(body["overlays"]["enmo_g"], 0.31)
        frame = body["frame"]
        self.assertGreater(frame["hr_bpm"], 140)
        g2 = next(g for g in frame["gates"] if g["gate"] == 2)
        self.assertEqual(g2["outcome"], "BLOCK")
        self.assertTrue(frame["suppressed"])
        self.assertEqual(body["triage"]["tier"], "WATCH")
        events = {e["event"] for e in body["audit"]["entries"]}
        self.assertIn("GATE_2_FALSE_ALARM_BLOCKED", events)
        heart = next(o for o in body["organs"] if o["system"] == "heart")
        self.assertEqual(heart["status"], "WATCH")
        self.assertIsNotNone(heart["z_score"])

    def test_sans_scenario_holds_for_eye_scan(self):
        body = client().post("/api/scenario", json={"scenario_id": "sans-stale-eye"}, headers=CREW).json()
        self.assertAlmostEqual(body["overlays"]["co2_mmhg"], 4.2)
        self.assertEqual(body["frame"]["state"], "CREW_CHECK")
        g3 = next(g for g in body["gates"] if g["gate"] == 3)
        self.assertEqual(g3["outcome"], "HOLD")
        self.assertEqual(g3["evidence"]["requested_exam"], "ultrasound")
        self.assertEqual(body["active_sensing"]["top"]["exam"], "onsd")
        self.assertEqual(body["triage"]["tier"], "CREW")

    def test_radiation_and_glycemic_scenarios_raise_organs(self):
        c = client()
        spe = c.post("/api/scenario", json={"scenario_id": "spe-radiation"}, headers=CREW).json()
        chest = next(o for o in spe["organs"] if o["system"] == "chest-immune")
        self.assertEqual(chest["status"], "ALERT")
        self.assertEqual(spe["frame"]["state"], "SURGEON_ALERT")
        self.assertEqual(spe["triage"]["tier"], "SURGEON")
        self.assertTrue(spe["ml_benchmark"]["cosine_median_demo"]["caught"])
        events = {e["event"] for e in spe["audit"]["entries"]}
        self.assertIn("SURGEON_ESCALATION", events)
        self.assertIn("FEDERATED_ROUND_ANCHORED", events)
        drift = c.post("/api/scenario", json={"scenario_id": "glycemic-circadian"}, headers=CREW).json()
        statuses = {o["system"]: o["status"] for o in drift["organs"]}
        self.assertEqual(statuses["metabolic"], "WATCH")
        self.assertEqual(statuses["brain"], "ALERT")
        self.assertEqual(statuses["bones"], "NOMINAL")

    def test_real_mode_does_not_invent_telemetry(self):
        c = client()
        c.post("/api/scenario", json={"scenario_id": "nominal-orbital"}, headers=CREW)
        body = c.post("/api/scenario", json={"mode": "REAL_EMPIRICAL"}, headers=OPS).json()
        self.assertEqual(body["data_source_mode"], "REAL_EMPIRICAL")
        self.assertEqual(body["telemetry_mode"], "NOT_AVAILABLE")
        self.assertIn("NOT AVAILABLE", body["provenance_banner"])
        self.assertIsNone(body["frame"])
        self.assertEqual(body["history"], [])
        self.assertIsNone(body["overlays"]["enmo_g"])
        self.assertFalse(body["running"])


class ExamTests(unittest.TestCase):
    def test_pvt_resets_tau_and_audits_without_raw_value(self):
        c = client()
        body = c.post("/api/exams/pvt", json={"reaction_ms": [288, 305, 340]}, headers=CREW).json()
        brain = next(o for o in body["organs"] if o["system"] == "brain")
        self.assertAlmostEqual(brain["staleness_tau"], 1.0, places=2)
        entries = c.get("/api/audit", headers=OPS).json()["entries"]
        self.assertTrue(any(e["event"] == "pvt.result" for e in entries))
        self.assertNotIn("305", str(entries))

    def test_ultrasound_samples_and_custom_caliper(self):
        c = client()
        nominal = c.post("/api/exams/ultrasound", json={"sample": "nominal"}, headers=CREW).json()
        self.assertAlmostEqual(nominal["caliper"]["onsd_mm"], 4.6)
        sans = c.post("/api/exams/ultrasound", json={"sample": "sans"}, headers=CREW).json()
        self.assertAlmostEqual(sans["caliper"]["onsd_mm"], 6.1)
        custom = c.post("/api/exams/ultrasound",
                        json={"px_per_mm": 20, "x1": 0, "y1": 0, "x2": 100, "y2": 0}, headers=CREW).json()
        self.assertAlmostEqual(custom["caliper"]["onsd_mm"], 5.0)
        bad = c.post("/api/exams/ultrasound", json={"x1": 0, "y1": 0, "x2": 10, "y2": 0}, headers=CREW)
        self.assertEqual(bad.status_code, 400)

    def test_vitals_update_organs_and_actions_stay_allowed(self):
        c = client()
        body = c.post("/api/exams/vitals", json={"bp_sys": 122, "bp_dia": 78, "glucose_mgdl": 92,
                                                 "temp_c": 36.8, "sleep_hrs": 7.2, "water_ml": 1800,
                                                 "ared_min": 30, "mood_score": 7}, headers=CREW).json()
        self.assertFalse(body["countermeasure_flags"]["water_low"])
        self.assertFalse(body["countermeasure_flags"]["ared_low"])
        for organ in body["organs"]:
            self.assertIn(organ["action"], ALLOWED_ACTIONS)
        for action in body["triage"]["actions"]:
            self.assertIn(action, ALLOWED_ACTIONS)

    def test_unknown_scenario_rejected(self):
        self.assertEqual(client().post("/api/scenario", json={"scenario_id": "nope"}, headers=CREW).status_code, 400)


if __name__ == "__main__":
    unittest.main()
