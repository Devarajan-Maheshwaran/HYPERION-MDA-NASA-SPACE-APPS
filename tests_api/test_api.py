"""HTTP contract, role guards, audit chain, organ staleness and data honesty."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from api.actions import ALLOWED_ACTIONS, FORBIDDEN_SUBSTRINGS  # noqa: E402
from api.audit import AuditLog  # noqa: E402
from api.main import create_app  # noqa: E402
from api.models import DISCLAIMER, ManualCheck  # noqa: E402
from api.organs import organ_readings, readiness_streak, tau  # noqa: E402
from api.scenarios import BY_ID, catalogue, sample  # noqa: E402

OPS = {"x-role": "ops"}
CREW = {"x-role": "crew"}
SURGEON = {"x-role": "flight-surgeon"}
RESEARCH = {"x-role": "researcher"}


def client() -> TestClient:
    return TestClient(create_app())


class EnvelopeTests(unittest.TestCase):
    def test_every_endpoint_carries_the_disclaimer_and_lane(self):
        c = client()
        paths = ["/api/health", "/api/session", "/api/lanes", "/api/registry", "/api/subjects",
                 "/api/scenarios", "/api/stream/state", "/api/audit/verify"]
        for path in paths:
            body = c.get(path).json()
            self.assertEqual(body["disclaimer"], DISCLAIMER, path)
            self.assertIn("lane", body, path)
            self.assertIn("generated_at", body, path)

    def test_registry_count_matches_the_existing_module(self):
        body = client().get("/api/registry").json()
        self.assertEqual(body["total"], 49)
        self.assertEqual(body["by_status"]["MEASURED-LAB-SAMPLE"], 19)
        self.assertEqual(len(body["channels"]), 49)

    def test_unavailable_lanes_report_a_reason_not_fabricated_data(self):
        body = client().get("/api/lanes").json()
        for lane in body["lanes"]:
            if not lane["available"]:
                self.assertTrue(lane["detail"], lane["lane"])
        sim = next(l for l in body["lanes"] if l["lane"] == "SIMULATED")
        self.assertTrue(sim["available"])

    def test_lab_endpoint_is_honest_when_uncached(self):
        body = client().get("/api/lab/osd575", headers=RESEARCH).json()
        self.assertIn("available", body)
        if not body["available"]:
            self.assertEqual(body["rows"], [])
            self.assertTrue(body["detail"])


class RoleTests(unittest.TestCase):
    def test_crew_cannot_calibrate(self):
        self.assertEqual(client().post("/api/calibration/demo-crew-1", headers=CREW).status_code, 403)

    def test_ops_can_calibrate(self):
        r = client().post("/api/calibration/demo-crew-1", headers=OPS)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["calibration"]["calibrated"])

    def test_only_surgeon_can_acknowledge(self):
        c = client()
        c.post("/api/calibration/demo-crew-1", headers=OPS)
        c.post("/api/scenarios/true-rest-tachycardia/start", headers=OPS)
        c.post("/api/stream/step?dt_s=5", headers=OPS)
        alerts = c.get("/api/alerts", headers=SURGEON).json()["alerts"]
        self.assertTrue(alerts)
        aid = alerts[0]["alert_id"]
        self.assertEqual(c.post(f"/api/alerts/{aid}/ack", headers=CREW).status_code, 403)
        self.assertEqual(c.post(f"/api/alerts/{aid}/ack", headers=OPS).status_code, 403)
        ok = c.post(f"/api/alerts/{aid}/ack", json={"note": "reviewed"}, headers=SURGEON)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["alert"]["acknowledged_by"], "flight-surgeon")

    def test_crew_cannot_read_research_or_audit(self):
        c = client()
        self.assertEqual(c.get("/api/research/m6", headers=CREW).status_code, 403)
        self.assertEqual(c.get("/api/audit", headers=CREW).status_code, 403)
        self.assertEqual(c.get("/api/research/m6", headers=RESEARCH).status_code, 200)

    def test_unknown_role_falls_back_to_crew(self):
        c = client()
        self.assertEqual(c.get("/api/session", headers={"x-role": "root"}).json()["role"], "crew")


class ActionTextTests(unittest.TestCase):
    def test_allow_list_is_exactly_four(self):
        self.assertEqual(ALLOWED_ACTIONS, ("Repeat measurement", "Rest and recheck",
                                           "Check sensor", "Contact flight surgeon"))

    def test_no_treatment_advice_in_any_scenario_frame_or_organ(self):
        c = client()
        c.post("/api/calibration/demo-crew-1", headers=OPS)
        c.post("/api/manual", json={"subject_id": "demo-crew-1", "kind": "bp",
                                    "systolic": 150, "diastolic": 95, "unit": "mmHg"}, headers=CREW)
        texts: list[str] = []
        for sid in BY_ID:
            c.post(f"/api/scenarios/{sid}/start", headers=OPS)
            for _ in range(3):
                frame = c.post("/api/stream/step?dt_s=2", headers=OPS).json()["frame"]
                texts += frame["actions"]
        for organ in c.get("/api/organs", headers=CREW).json()["organs"]:
            texts.append(organ["action"])
        for text in texts:
            self.assertIn(text, ALLOWED_ACTIONS)
            lowered = text.lower()
            for bad in FORBIDDEN_SUBSTRINGS:
                self.assertNotIn(bad, lowered, f"treatment advice leaked: {text!r}")

    def test_organ_thresholds_are_labelled_demo(self):
        c = client()
        for organ in c.get("/api/organs", headers=CREW).json()["organs"]:
            self.assertIn("DEMO THRESHOLD", organ["threshold_label"])


class AuditTests(unittest.TestCase):
    def test_chain_verifies(self):
        log = AuditLog()
        log.append("a", "ops", "s1", "SIMULATED", {"x": 1})
        log.append("b", "crew", "s1", "INJECTED", {})
        self.assertTrue(log.verify()["ok"])
        self.assertEqual(log.verify()["entries"], 2)

    def test_tampering_is_detected(self):
        log = AuditLog()
        log.append("a", "ops", "s1", "SIMULATED", {"x": 1})
        log.append("b", "crew", "s1", "INJECTED", {})
        log._entries[0].detail["x"] = 999  # simulate an edit
        result = log.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad_index"], 0)

    def test_deleting_an_entry_is_detected(self):
        log = AuditLog()
        for i in range(3):
            log.append(f"e{i}", "ops", "s1", "SIMULATED", {})
        del log._entries[1]
        self.assertFalse(log.verify()["ok"])

    def test_api_actions_are_audited(self):
        c = client()
        c.post("/api/calibration/demo-crew-1", headers=OPS)
        c.post("/api/scenarios/rest-nominal/start", headers=OPS)
        c.post("/api/stream/step?dt_s=1", headers=OPS)
        entries = c.get("/api/audit", headers=OPS).json()["entries"]
        events = {e["event"] for e in entries}
        self.assertIn("calibration.create", events)
        self.assertIn("scenario.start", events)
        self.assertTrue(c.get("/api/audit/verify").json()["ok"])

    def test_audit_stores_no_raw_measurements(self):
        c = client()
        c.post("/api/manual", json={"subject_id": "demo-crew-1", "kind": "glucose",
                                    "value": 131, "unit": "mg/dL"}, headers=CREW)
        for entry in c.get("/api/audit", headers=OPS).json()["entries"]:
            self.assertNotIn("131", str(entry["detail"]))


class StalenessTests(unittest.TestCase):
    def _check(self, kind: str, hours_ago: float, value: float = 100.0) -> ManualCheck:
        ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
        return ManualCheck(subject_id="s1", kind=kind, value=value, recorded_at=ts)

    def test_tau_decays(self):
        self.assertAlmostEqual(tau(0.0), 1.0)
        self.assertLess(tau(10.0), tau(1.0))

    def test_missing_is_not_available_never_nominal(self):
        readings = organ_readings([])
        self.assertEqual(len(readings), 6)
        for r in readings:
            self.assertEqual(r.status, "NOT_AVAILABLE")

    def test_stale_is_unknown_never_nominal(self):
        readings = organ_readings([self._check("glucose", 48.0, 90.0)])
        metabolic = next(r for r in readings if r.system == "metabolic")
        self.assertEqual(metabolic.status, "UNKNOWN")
        self.assertIn("stale", metabolic.indicator)

    def test_fresh_normal_is_nominal(self):
        readings = organ_readings([self._check("glucose", 0.5, 85.0)])
        self.assertEqual(next(r for r in readings if r.system == "metabolic").status, "NOMINAL")

    def test_fresh_breach_is_alert_with_allowed_action(self):
        readings = organ_readings([self._check("glucose", 0.5, 140.0)])
        metabolic = next(r for r in readings if r.system == "metabolic")
        self.assertEqual(metabolic.status, "ALERT")
        self.assertIn(metabolic.action, ALLOWED_ACTIONS)

    def test_readiness_streak_counts_days(self):
        checks = [self._check("mood", 1.0), self._check("mood", 25.0)]
        self.assertGreaterEqual(readiness_streak(checks)["streak_days"], 1)


class ScenarioTests(unittest.TestCase):
    def test_scenarios_are_deterministic(self):
        for sid in BY_ID:
            self.assertEqual(sample(sid, 12.0), sample(sid, 12.0))

    def test_catalogue_covers_the_safety_cases(self):
        ids = {s.scenario_id for s in catalogue()}
        for required in ("exercise-false-alarm", "exercise-with-arrhythmia", "hard-ceiling",
                         "hold-timeout", "sensor-artifact", "uncalibrated", "stale-manual"):
            self.assertIn(required, ids)

    def test_every_scenario_is_labelled_simulated_or_injected(self):
        for info in catalogue():
            self.assertIn(info.lane, ("SIMULATED", "INJECTED"))

    def test_frames_never_claim_lab_provenance(self):
        c = client()
        c.post("/api/calibration/demo-crew-1", headers=OPS)
        for sid in BY_ID:
            c.post(f"/api/scenarios/{sid}/start", headers=OPS)
            frame = c.post("/api/stream/step?dt_s=1", headers=OPS).json()["frame"]
            self.assertIn(frame["lane"], ("SIMULATED", "INJECTED"))

    def test_step_requires_a_started_scenario(self):
        self.assertEqual(client().post("/api/stream/step", headers=OPS).status_code, 409)

    def test_unknown_scenario_is_404(self):
        self.assertEqual(client().post("/api/scenarios/nope/start", headers=OPS).status_code, 404)


class PvtTests(unittest.TestCase):
    def test_valid_submission(self):
        r = client().post("/api/pvt", json={"subject_id": "demo-crew-1",
                                            "reaction_ms": [280, 310, 420, 355]}, headers=CREW)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["lapses_over_350ms"], 2)

    def test_rejects_empty_and_implausible(self):
        c = client()
        self.assertEqual(c.post("/api/pvt", json={"reaction_ms": []}, headers=CREW).status_code, 400)
        self.assertEqual(c.post("/api/pvt", json={"reaction_ms": [-5]}, headers=CREW).status_code, 400)
        self.assertEqual(c.post("/api/pvt", json={"reaction_ms": [99999]}, headers=CREW).status_code, 400)


class ManualValidationTests(unittest.TestCase):
    def test_bp_requires_both_numbers(self):
        c = client()
        self.assertEqual(c.post("/api/manual", json={"subject_id": "demo-crew-1", "kind": "bp",
                                                     "systolic": 120}, headers=CREW).status_code, 400)

    def test_scalar_requires_value(self):
        c = client()
        self.assertEqual(c.post("/api/manual", json={"subject_id": "demo-crew-1",
                                                     "kind": "glucose"}, headers=CREW).status_code, 400)

    def test_unknown_subject_rejected(self):
        c = client()
        self.assertEqual(c.post("/api/manual", json={"subject_id": "nobody", "kind": "glucose",
                                                     "value": 100}, headers=CREW).status_code, 400)


if __name__ == "__main__":
    unittest.main()
