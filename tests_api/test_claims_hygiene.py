"""P0-8: automated guard against the overclaims the concept deck invites.

Each test encodes one claim the prototype must NOT make, and checks the shipped strings and
API payloads rather than the docs alone. A negated mention ("not NASA-STD-3001 compliance")
is fine; a bare assertion is not. If a future edit drops a disclaimer, this fails.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from api import goes, lanes  # noqa: E402
from api.actions import ALLOWED_ACTIONS  # noqa: E402
from api.main import create_app  # noqa: E402
from api.models import DISCLAIMER  # noqa: E402

CREW = {"x-role": "crew"}
SURGEON = {"x-role": "flight-surgeon"}

UI_SOURCES = sorted((ROOT / "web" / "src").rglob("*.ts")) + sorted((ROOT / "web" / "src").rglob("*.tsx"))
UI_SOURCES = [p for p in UI_SOURCES if ".test." not in p.name and "/test/" not in str(p)]
API_SOURCES = sorted((ROOT / "api").glob("*.py"))


def text_of(paths: list[Path]) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in paths)


class DisclaimerTests(unittest.TestCase):
    def test_every_state_payload_carries_the_disclaimer(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            client.get("/api/state")
            for scenario in ("nominal-orbital", "eva-ared-exercise", "sans-stale-eye",
                             "spe-radiation", "glycemic-circadian"):
                with self.subTest(scenario=scenario):
                    state = client.post("/api/scenario", json={"scenario_id": scenario},
                                        headers=CREW).json()
                    self.assertEqual(state["disclaimer"], DISCLAIMER)
                    self.assertIn("not clinically validated", state["disclaimer"])
                    self.assertIn("Not a medical device", state["disclaimer"])

    def test_ui_ships_the_same_disclaimer(self):
        self.assertIn(DISCLAIMER, text_of(UI_SOURCES))


class StandardsClaimTests(unittest.TestCase):
    def test_no_unqualified_nasa_std_3001_compliance_claim(self):
        """Every NASA-STD-3001 mention must be a reference or an explicit negation."""
        for path in UI_SOURCES + API_SOURCES:
            body = path.read_text(encoding="utf-8")
            for match in re.finditer(r"NASA-STD-3001", body):
                window = body[max(0, match.start() - 400): match.end() + 400].lower()
                with self.subTest(file=str(path.relative_to(ROOT))):
                    self.assertTrue(
                        any(cue in window for cue in ("not ", "no compliance", "reference",
                                                      "framework", "does not claim", "≠")),
                        f"unqualified NASA-STD-3001 mention in {path.name}")

    def test_demo_thresholds_are_labelled_on_every_organ(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            state = client.get("/api/state").json()
            for organ in state["organs"]:
                with self.subTest(organ=organ["system"]):
                    self.assertIn("DEMO", organ["threshold_label"])
                    self.assertIn("not a validated clinical limit", organ["threshold_label"])
                    self.assertIn("deck claim", organ["demo_threshold"])

    def test_lifecycle_routing_is_labelled_a_demo_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            state = client.get("/api/state").json()
            routing = state["lifecycle"]["routing_label"].lower()
            self.assertIn("demo", routing)
            self.assertIn("DEMO triage", state["triage"]["label"])


class DatasetProvenanceTests(unittest.TestCase):
    def test_osd_575_is_never_described_as_environmental(self):
        """OSD-575 is a rodent hindlimb-unloading lab dataset, not cabin environment data."""
        lane = lanes.lab_lane()
        blob = f"{lane.model_dump()} {text_of(API_SOURCES)} {text_of(UI_SOURCES)}".lower()
        self.assertIn("osd-575", blob)
        for phrase in ("osd-575 environmental", "osd-575 cabin", "environmental osd-575",
                       "osd-575 co2", "osd-575 radiation"):
            self.assertNotIn(phrase, blob)

    def test_lab_lane_declares_its_true_provenance(self):
        lane = lanes.lab_lane()
        text = str(lane.model_dump()).lower()
        self.assertTrue(any(word in text for word in ("rodent", "mouse", "mice", "hindlimb",
                                                      "muscle", "lab")))
        self.assertNotIn("astronaut", text.replace("non-astronaut", "").replace("not astronaut", ""))

    def test_recorded_replay_is_badged_non_astronaut(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            state = client.post("/api/scenario", json={"replay_participant": "s1"},
                                headers=CREW).json()
            self.assertIn("NON-ASTRONAUT", state["provenance_banner"])
            self.assertIn("NON-ASTRONAUT", state["replay"]["lane"])
            self.assertEqual(state["frame"]["lane"], "RECORDED-NON-ASTRONAUT")

    def test_the_three_lanes_are_never_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            body = client.get("/api/lanes").json()
            names = {lane["lane"] for lane in body["lanes"]}
            self.assertIn("LAB DATA", names)
            self.assertIn("RECORDED-NON-ASTRONAUT", names)
            self.assertIn("SIMULATED", names)
            self.assertIn("INJECTED", names)
            self.assertEqual(len(names), 4)  # four distinct lanes, never one merged stream
            registry = client.get("/api/registry").json()
            self.assertEqual(registry["by_status"]["MEASURED-LAB-SAMPLE"], 19)


class RadiationUnitTests(unittest.TestCase):
    def test_goes_quantity_is_flux_in_pfu_not_dose(self):
        summary = goes.summary()
        self.assertEqual(summary["unit"], "pfu")
        self.assertIn("cm^2", summary["unit_long"])
        self.assertIn("not absorbed tissue dose", summary["dose_note"].lower())
        self.assertIn("mgy/day", summary["dose_note"].lower())
        self.assertIn("not tissue dose", summary["quantity"])

    def test_goes_is_unavailable_offline_instead_of_fabricated(self):
        summary = goes.summary()
        if not summary["available"]:
            self.assertIsNone(summary["latest_sample"])
            self.assertIsNone(summary["cache_age_s"])

    def test_simulated_dose_is_never_attributed_to_goes(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            state = client.post("/api/scenario", json={"scenario_id": "spe-radiation"},
                                headers=CREW).json()
            label = state["overlays"]["label"]
            self.assertIn("SIMULATED dose placeholder", label)
            self.assertIn("never derived", label)
            self.assertIn("pfu", label)
            chest = next(o for o in state["organs"] if o["system"] == "chest-immune")
            self.assertIn("SIMULATED", chest["indicator"])


class BlockchainClaimTests(unittest.TestCase):
    def test_hash_chain_is_never_claimed_as_a_mainnet_or_evm_deployment(self):
        blob = text_of(UI_SOURCES + API_SOURCES)
        self.assertNotIn("deployed to mainnet", blob.lower())
        self.assertNotIn("live on mainnet", blob.lower())
        self.assertIn("NOT deployed, NOT on-chain", blob)
        self.assertIn("no EVM tx", blob)

    def test_audit_payload_denies_the_chain_and_hides_raw_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            client.get("/api/state")
            client.post("/api/exams/vitals", json={"glucose_mgdl": 220, "bp_sys": 150,
                                                   "bp_dia": 95}, headers=CREW)
            state = client.get("/api/state").json()
            self.assertIn("no chain exists", state["audit"]["badge"])
            self.assertIn("NOT deployed", state["audit"]["contract"])
            for entry in state["audit"]["entries"]:
                detail = str(entry["detail"])
                for raw in ("220", "150", "95"):
                    self.assertNotIn(raw, detail,
                                     f"raw measurement leaked into audit detail: {detail}")
            self.assertTrue(state["audit"]["verification"]["ok"])

    def test_fl_simulation_is_labelled_a_toy_not_a_real_federation(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            state = client.post("/api/scenario", json={"scenario_id": "spe-radiation"},
                                headers=CREW).json()
            bench = state["ml_benchmark"]
            label = bench["fl_simulation"]["label"].lower()
            self.assertIn("simulation", label)
            self.assertIn("no privacy guarantee", label)
            self.assertIn("no accuracy claim", label)
            self.assertTrue(bench["not_implemented"])
            statuses = {row["status"] for row in bench["requested_benchmarks"]}
            self.assertIn("SIMULATED_TOY_FEDAVG", statuses)


class ActionAllowListTests(unittest.TestCase):
    def test_no_treatment_instructions_are_emitted(self):
        self.assertEqual(len(ALLOWED_ACTIONS), 4)
        blob = " ".join(ALLOWED_ACTIONS).lower()
        for forbidden in ("500 ml", "600 ml", "salt", "potassium citrate", "lbnP".lower(),
                          "insulin", "mg ", "administer", "prescribe"):
            self.assertNotIn(forbidden, blob)

    def test_every_sbar_recommendation_stays_inside_the_allow_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            client.get("/api/state")
            state = client.post("/api/scenario", json={"scenario_id": "spe-radiation"},
                                headers=CREW).json()
            for packet in state["comms"]["packets"]:
                recommendation = packet["sbar"]["recommendation"]
                self.assertTrue(any(action in recommendation for action in ALLOWED_ACTIONS),
                                recommendation)


class CommsHonestyTests(unittest.TestCase):
    def test_mars_delay_is_labelled_a_demo_compression(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(db_path=Path(tmp) / "s.db", clock_enabled=False))
            state = client.post("/api/scenario", json={"habitat": "transit"}, headers=CREW).json()
            profile = state["comms"]["profile"]
            self.assertEqual(profile["delay_s"], 12.0)
            note = profile["real_world_note"].lower()
            self.assertIn("20", note)
            self.assertTrue("demo" in note or "scale" in note or "compress" in note)

    def test_no_hipaa_or_regulatory_compliance_claim(self):
        blob = text_of(UI_SOURCES + API_SOURCES).lower()
        for phrase in ("hipaa compliant", "hipaa-compliant", "gdpr compliant", "gdpr-compliant",
                       "fda approved", "fda-approved", "clinically validated system",
                       "flight-ready", "flight ready"):
            self.assertNotIn(phrase, blob, f"unqualified claim: {phrase}")
        # Any "astronaut data" mention must be a denial, never a claim to hold such data.
        for match in re.finditer(r"astronaut data", blob):
            window = blob[max(0, match.start() - 60): match.end()]
            self.assertTrue(any(cue in window for cue in ("never ", "not ", "no ", "non-")),
                            f"unqualified astronaut-data claim near: {window!r}")


if __name__ == "__main__":
    unittest.main()
