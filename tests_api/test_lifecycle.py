"""P0-1/P0-2/P0-3/P0-5/P0-6: clock, restart persistence, closed-loop lifecycle, reset.

Deterministic by construction: `clock_enabled=False` everywhere except the one test that
exercises the real 1 Hz task, and wall-clock transport delays are driven by patching
`api.outbox.time.time` instead of sleeping.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from api import workflow  # noqa: E402
from api.main import create_app  # noqa: E402
from api.persistence import StateDatabase  # noqa: E402

CREW = {"x-role": "crew"}
OPS = {"x-role": "ops"}
SURGEON = {"x-role": "flight-surgeon"}
RESEARCH = {"x-role": "researcher"}
FUTURE = 9.0e12  # a wall clock far beyond any comms delay


class WorkstationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "state.db"
        self.addCleanup(self.tmp.cleanup)
        self.client = self.boot()

    def boot(self, **kwargs) -> TestClient:
        """Fresh app over the same database file = a process restart."""
        app = create_app(db_path=self.db_path, clock_enabled=False, **kwargs)
        client = TestClient(app)
        client.get("/api/state")  # lazy boot seed
        return client

    def scenario(self, scenario_id: str, **extra) -> dict:
        response = self.client.post("/api/scenario",
                                    json={"scenario_id": scenario_id, **extra}, headers=CREW)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def step(self, dt_s: float = 1.0) -> dict:
        response = self.client.post("/api/transport", json={"action": "step", "dt_s": dt_s},
                                    headers=CREW)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def deliver(self) -> None:
        """Move the store-and-forward clock past every profile's delay."""
        with patch("api.outbox.time.time", return_value=FUTURE):
            self.step(1.0)

    def acknowledge(self, packet_id: str, directive: str = "Recheck ONSD in 30 minutes."):
        return self.client.post("/api/surgeon/acknowledge",
                                json={"packet_id": packet_id, "directive": directive},
                                headers=SURGEON)


class BootAndClockTests(WorkstationTestCase):
    def test_boot_opens_on_a_live_labelled_case(self):
        state = self.client.get("/api/state").json()
        self.assertEqual(state["scenario_key"], "nominal-orbital")
        self.assertTrue(state["running"])
        self.assertEqual(state["lifecycle"]["stage"], workflow.S0)
        self.assertGreater(len(state["history"]), 0)
        self.assertIsNotNone(state["frame"])
        self.assertEqual(state["telemetry_mode"], "SIMULATED_FALLBACK")
        self.assertIn("SIMULATED", state["provenance_banner"])

    def test_clock_advertises_one_hz_and_the_tau_basis(self):
        clock = self.client.get("/api/state").json()["clock"]
        self.assertEqual(clock["hz"], 1.0)
        self.assertEqual(clock["period_s"], 1.0)
        self.assertEqual(clock["mission_seconds_per_demo_hour"], 60.0)
        self.assertIn("mission", clock["tau_basis"].lower())

    def test_health_reports_the_clock(self):
        health = self.client.get("/api/health").json()
        self.assertEqual(health["clock_hz"], 1.0)

    def test_pause_step_play_are_deterministic(self):
        paused = self.client.post("/api/transport", json={"action": "pause"}, headers=CREW).json()
        self.assertFalse(paused["running"])
        t0 = paused["t_s"]
        stepped = self.step(10.0)
        self.assertEqual(stepped["t_s"], t0 + 10.0)
        self.assertEqual(len(stepped["history"]), len(paused["history"]) + 1)
        again = self.client.get("/api/state").json()
        self.assertEqual(again["t_s"], stepped["t_s"])  # paused means paused
        played = self.client.post("/api/transport", json={"action": "play"}, headers=CREW).json()
        self.assertTrue(played["running"])

    def test_transport_validates_input_and_role(self):
        self.assertEqual(self.client.post("/api/transport", json={"action": "step", "dt_s": 0},
                                          headers=CREW).status_code, 400)
        self.assertEqual(self.client.post("/api/transport", json={"action": "step", "dt_s": 61},
                                          headers=CREW).status_code, 400)
        self.assertEqual(self.client.post("/api/transport", json={"action": "rewind"},
                                          headers=CREW).status_code, 400)
        self.assertEqual(self.client.post("/api/transport", json={"action": "pause"},
                                          headers=RESEARCH).status_code, 403)

    def test_transport_writes_audit_blocks(self):
        self.client.post("/api/transport", json={"action": "pause"}, headers=CREW)
        self.step(1.0)
        events = [e["event"] for e in self.client.get("/api/state").json()["audit"]["entries"]]
        self.assertIn("transport.pause", events)
        self.assertIn("transport.step", events)

    def test_real_one_hz_task_advances_mission_time(self):
        app = create_app(db_path=self.db_path, clock_enabled=True)
        with TestClient(app) as live:
            live.get("/api/state")
            before = live.get("/api/state").json()["t_s"]
            # Wait on the event loop, not on a fixed sleep, so slow CI still passes.
            async def wait_for_ticks():
                for _ in range(60):
                    await asyncio.sleep(0.1)
                    if live.get("/api/state").json()["t_s"] > before:
                        return True
                return False
            self.assertTrue(asyncio.run(wait_for_ticks()))
            after = live.get("/api/state").json()
            self.assertGreater(after["t_s"], before)
            self.assertGreater(len(after["history"]), 1)


class DecayTests(WorkstationTestCase):
    def test_tau_decays_on_the_mission_clock_and_an_exam_restores_it(self):
        self.scenario("sans-stale-eye")
        eyes = next(o for o in self.client.get("/api/state").json()["organs"]
                    if o["system"] == "head-eyes")
        stale = eyes["staleness_tau"]
        self.assertIsNotNone(stale)
        self.assertLess(stale, 0.5)
        self.assertIn("60 mission seconds", eyes["tau_basis"])
        self.step(10.0)
        decayed = next(o for o in self.client.get("/api/state").json()["organs"]
                       if o["system"] == "head-eyes")["staleness_tau"]
        self.assertLess(decayed, stale)
        fixed = self.client.post("/api/exams/ultrasound", json={"sample": "nominal"},
                                 headers=CREW).json()
        eye = next(o for o in fixed["organs"] if o["system"] == "head-eyes")
        self.assertEqual(eye["staleness_tau"], 1.0)


class LifecycleTests(WorkstationTestCase):
    def test_every_demo_scenario_lands_on_its_declared_stage(self):
        expected = {"nominal-orbital": workflow.S0, "eva-ared-exercise": workflow.S1,
                    "sans-stale-eye": workflow.S2, "spe-radiation": workflow.S4,
                    "glycemic-circadian": workflow.S3}
        for scenario_id, stage in expected.items():
            with self.subTest(scenario=scenario_id):
                state = self.scenario(scenario_id)
                self.assertEqual(state["lifecycle"]["stage"], stage)
        self.assertEqual(len(self.client.get("/api/state").json()["demo_scenarios"]), 5)

    def test_exercise_is_suppressed_not_escalated(self):
        state = self.scenario("eva-ared-exercise")
        self.assertEqual(state["gates"][1]["outcome"], "BLOCK")
        self.assertTrue(state["frame"]["suppressed"])
        self.assertEqual(state["triage"]["tier"], "WATCH")
        self.assertEqual(state["comms"]["packets"], [])

    def test_stale_eye_hold_requests_the_ultrasound_and_flags_action_required(self):
        state = self.scenario("sans-stale-eye")
        self.assertEqual(state["gates"][2]["outcome"], "HOLD")
        self.assertTrue(state["lifecycle"]["action_required"])
        self.assertEqual(state["lifecycle"]["requested_exam"], "ultrasound")
        self.assertEqual(state["active_sensing"]["top"]["exam"], "onsd")
        self.assertEqual(state["comms"]["packets"], [])

    def test_normal_onsd_resolves_the_hold_to_a_crew_countermeasure(self):
        self.scenario("sans-stale-eye")
        state = self.client.post("/api/exams/ultrasound", json={"sample": "nominal"},
                                 headers=CREW).json()
        self.assertEqual(state["lifecycle"]["stage"], workflow.S3)
        self.assertFalse(state["lifecycle"]["action_required"])
        self.assertNotEqual(state["gates"][2]["outcome"], "HOLD")
        self.assertEqual(state["comms"]["packets"], [])

    def test_elevated_onsd_escalates_and_queues_exactly_one_packet(self):
        self.scenario("sans-stale-eye")
        state = self.client.post("/api/exams/ultrasound", json={"sample": "sans"},
                                 headers=CREW).json()
        self.assertEqual(state["lifecycle"]["stage"], workflow.S4)
        self.assertEqual(state["triage"]["tier"], "SURGEON")
        packets = state["comms"]["packets"]
        self.assertEqual(len(packets), 1)
        self.assertIn(packets[0]["comms_state"], {"QUEUED_BLACKOUT", "IN_TRANSIT"})
        for field in ("situation", "background", "assessment", "recommendation"):
            self.assertTrue(packets[0]["sbar"][field])
        self.step(1.0)
        self.assertEqual(len(self.client.get("/api/state").json()["comms"]["packets"]), 1)

    def test_hard_ceiling_is_never_held_by_the_eye_rule(self):
        self.scenario("sans-stale-eye")
        # The CO2 eye-evidence rule must not be able to swallow a hard-ceiling rate.
        from api.gates import GateInput, HoldClock, evaluate
        from api.models import Calibration, SqReading
        cal = Calibration(subject_id="s1", calibrated=True, n_windows=60, lane="SIMULATED",
                          source="test fixture", rest_hr_median=68.0, rest_hr_scale=2.0,
                          rest_activity_median=1.0, rest_activity_scale=0.01, residual_q95=4.0,
                          kurtosis_low=1.5, kurtosis_high=6.0, slew_high=500.0)
        frame = evaluate(GateInput(t_s=1.0, hr_bpm=185.0, activity_norm=0.0, hr_status="OK",
                                   sqi=SqReading(kurtosis=3.0, slew=10.0, calibrated=True),
                                   co2_mmhg=4.2, onsd_tau=0.1, min_tau=0.1,
                                   stale_manual=True), cal, HoldClock())
        self.assertNotEqual(frame.gates[2].outcome, "HOLD")
        self.assertEqual(frame.state, "SURGEON_ALERT")


class SurgeonLoopTests(WorkstationTestCase):
    def escalated_packet(self) -> tuple[dict, str]:
        self.scenario("sans-stale-eye")
        state = self.client.post("/api/exams/ultrasound", json={"sample": "sans"},
                                 headers=CREW).json()
        return state, state["comms"]["packets"][0]["packet_id"]

    def test_ack_is_refused_before_delivery(self):
        _, packet_id = self.escalated_packet()
        self.assertEqual(self.acknowledge(packet_id).status_code, 409)

    def test_full_s2_to_s4_to_acknowledged_loop(self):
        state, packet_id = self.escalated_packet()
        self.assertEqual(state["lifecycle"]["stage"], workflow.S4)
        self.deliver()
        outbox = self.client.get("/api/surgeon/outbox", headers=SURGEON).json()
        self.assertEqual(outbox["packets"][0]["comms_state"], "DELIVERED")
        response = self.acknowledge(packet_id)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["lifecycle"]["stage"], workflow.S4_ACK)
        self.assertTrue(body["lifecycle"]["acknowledged"])
        self.assertEqual(body["triage"]["tier"], "SURGEON")
        packet = body["comms"]["packets"][0]
        self.assertEqual(packet["comms_state"], "ACKNOWLEDGED")
        self.assertEqual(len(packet["receipt"]["sha256"]), 64)
        self.assertEqual(len(body["receipt"]["receipt_id"]), len(packet["receipt"]["receipt_id"]))
        events = [e["event"] for e in body["audit"]["entries"]]
        self.assertIn("surgeon.receipt", events)
        self.assertTrue(body["audit"]["verification"]["ok"])
        # The acknowledgement survives further ticks of the same finding.
        self.assertEqual(self.step(1.0)["lifecycle"]["stage"], workflow.S4_ACK)

    def test_only_a_flight_surgeon_can_acknowledge(self):
        _, packet_id = self.escalated_packet()
        self.deliver()
        for headers in (CREW, OPS, {"x-role": "researcher"}, {}):
            with self.subTest(role=headers):
                self.assertEqual(self.client.post(
                    "/api/surgeon/acknowledge",
                    json={"packet_id": packet_id, "directive": "x"}, headers=headers).status_code, 403)

    def test_unknown_packet_and_empty_directive_are_rejected(self):
        self.escalated_packet()
        self.deliver()
        self.assertEqual(self.acknowledge("pkt-doesnotexist").status_code, 404)
        self.assertEqual(self.client.post("/api/surgeon/acknowledge",
                                          json={"packet_id": "pkt-doesnotexist", "directive": "  "},
                                          headers=SURGEON).status_code, 400)

    def test_a_new_finding_re_escalates_after_acknowledgement(self):
        _, packet_id = self.escalated_packet()
        self.deliver()
        self.assertEqual(self.acknowledge(packet_id).json()["lifecycle"]["stage"], workflow.S4_ACK)
        state = self.client.post("/api/exams/vitals", json={"temp_c": 39.4}, headers=CREW).json()
        self.assertEqual(state["lifecycle"]["stage"], workflow.S4)
        self.assertFalse(state["lifecycle"]["acknowledged"])
        states = [p["comms_state"] for p in state["comms"]["packets"]]
        self.assertIn("ACKNOWLEDGED", states)
        self.assertEqual(len(state["comms"]["packets"]), 2)


class CommsTests(WorkstationTestCase):
    def test_profiles_carry_the_declared_delays_and_honest_notes(self):
        delays = {}
        for habitat, expected in (("station", 0.2), ("lunar", 1.3), ("transit", 12.0), ("rover", 5.0)):
            state = self.client.post("/api/scenario", json={"habitat": habitat}, headers=CREW).json()
            profile = state["comms"]["profile"]
            self.assertEqual(profile["delay_s"], expected)
            self.assertTrue(profile["real_world_note"])
            delays[habitat] = profile["delay_s"]
        self.assertEqual(delays["transit"], 12.0)

    def test_transit_packet_counts_down_then_delivers(self):
        state = self.scenario("spe-radiation", habitat="transit")
        packet = state["comms"]["packets"][0]
        self.assertEqual(packet["comms_state"], "IN_TRANSIT")
        self.assertIsNotNone(packet["countdown_s"])
        self.assertGreater(packet["countdown_s"], 0)
        self.deliver()
        self.assertEqual(self.client.get("/api/surgeon/outbox", headers=SURGEON)
                         .json()["packets"][0]["comms_state"], "DELIVERED")

    def test_blackout_queues_then_releases(self):
        self.client.post("/api/scenario", json={"habitat": "rover"}, headers=CREW).json()
        self.client.post("/api/surgeon/blackout", json={"blackout": True}, headers=CREW)
        state = self.scenario("spe-radiation")
        packet = state["comms"]["packets"][0]
        self.assertEqual(packet["comms_state"], "QUEUED_BLACKOUT")
        self.assertTrue(state["comms"]["blackout"])
        self.deliver()  # still blacked out: no release
        self.assertEqual(self.client.get("/api/surgeon/outbox", headers=SURGEON)
                         .json()["packets"][0]["comms_state"], "QUEUED_BLACKOUT")
        restored = self.client.post("/api/surgeon/blackout", json={"blackout": False},
                                    headers=CREW).json()
        self.assertFalse(restored["blackout"])
        self.assertNotEqual(restored["packets"][0]["comms_state"], "QUEUED_BLACKOUT")

    def test_crew_can_watch_the_outbox_but_only_a_surgeon_may_acknowledge(self):
        # The crew cockpit shows the outbox, so reading it is allowed; writing a receipt is not.
        self.assertEqual(self.client.get("/api/surgeon/outbox", headers=CREW).status_code, 200)
        self.assertEqual(self.client.get("/api/surgeon/outbox", headers=RESEARCH).status_code, 403)
        self.scenario("spe-radiation")
        self.deliver()
        packet_id = self.client.get("/api/surgeon/outbox", headers=CREW).json()["packets"][0]["packet_id"]
        self.assertEqual(self.client.post("/api/surgeon/acknowledge",
                                          json={"packet_id": packet_id, "directive": "x"},
                                          headers=CREW).status_code, 403)


class PersistenceTests(WorkstationTestCase):
    def test_restart_restores_clock_exams_stage_and_outbox(self):
        self.scenario("sans-stale-eye")
        self.client.post("/api/exams/ultrasound", json={"sample": "sans"}, headers=CREW)
        self.client.post("/api/transport", json={"action": "pause"}, headers=CREW)
        self.step(10.0)
        packet_id = self.client.get("/api/state").json()["comms"]["packets"][0]["packet_id"]
        self.deliver()
        self.assertEqual(self.acknowledge(packet_id).status_code, 200)
        before = self.client.get("/api/state").json()

        self.client.close()
        self.client = self.boot()
        after = self.client.get("/api/state").json()
        self.assertEqual(after["t_s"], before["t_s"])
        self.assertEqual(after["running"], before["running"])
        self.assertEqual(after["lifecycle"]["stage"], workflow.S4_ACK)
        self.assertEqual(after["scenario_key"], before["scenario_key"])
        self.assertEqual(len(after["history"]), len(before["history"]))
        self.assertEqual([p["packet_id"] for p in after["comms"]["packets"]],
                         [p["packet_id"] for p in before["comms"]["packets"]])
        self.assertEqual(after["comms"]["packets"][0]["comms_state"], "ACKNOWLEDGED")
        self.assertEqual(after["audit"]["verification"]["head"],
                         before["audit"]["verification"]["head"])
        self.assertTrue(after["audit"]["verification"]["ok"])
        eye = next(o for o in after["organs"] if o["system"] == "head-eyes")
        self.assertEqual(eye["value"], 6.1)

    def test_restart_does_not_reseed_a_persisted_case(self):
        self.client.post("/api/transport", json={"action": "pause"}, headers=CREW)
        self.step(30.0)
        self.client.close()
        self.client = self.boot()
        state = self.client.get("/api/state").json()
        self.assertEqual(state["t_s"], 32.0)  # boot seed 2.0 + one 30 s step
        self.assertFalse(state["running"])

    def test_calibration_survives_restart(self):
        cal = self.client.post("/api/calibration/demo-crew-1", headers=OPS)
        self.assertEqual(cal.status_code, 200, cal.text)
        self.client.close()
        self.client = self.boot()
        subjects = self.client.get("/api/subjects").json()["subjects"]
        cal_row = next(s for s in subjects if s["subject_id"] == "demo-crew-1")["calibration"]
        self.assertTrue(cal_row["calibrated"])

    def test_cases_are_isolated(self):
        created = self.client.post("/api/case/new", json={"case_id": "case-two"}, headers=CREW)
        self.assertEqual(created.status_code, 200, created.text)
        other = {"x-role": "crew", "x-case-id": "case-two"}
        self.client.post("/api/scenario", json={"scenario_id": "spe-radiation"}, headers=other)
        default_state = self.client.get("/api/state").json()
        other_state = self.client.get("/api/state", headers=other).json()
        self.assertEqual(default_state["case_id"], "case-default")
        self.assertEqual(other_state["case_id"], "case-two")
        self.assertEqual(default_state["lifecycle"]["stage"], workflow.S0)
        self.assertEqual(other_state["lifecycle"]["stage"], workflow.S4)
        self.assertEqual(default_state["comms"]["packets"], [])
        listed = self.client.get("/api/cases", headers=CREW).json()["cases"]
        self.assertEqual({c["case_id"] for c in listed}, {"case-default", "case-two"})

    def test_schema_version_is_recorded(self):
        db = StateDatabase(self.db_path)
        rows = db.query("SELECT value FROM meta WHERE key='schema_version'")
        self.assertEqual(rows[0]["value"], "1")


class ResetTests(WorkstationTestCase):
    def test_reset_returns_to_nominal_and_clears_case_payload(self):
        self.scenario("spe-radiation")
        self.client.post("/api/exams/vitals", json={"glucose_mgdl": 220}, headers=CREW)
        before = self.client.get("/api/state").json()
        self.assertGreater(len(before["comms"]["packets"]), 0)
        state = self.client.post("/api/case/reset", json={}, headers=CREW).json()
        self.assertEqual(state["lifecycle"]["stage"], workflow.S0)
        self.assertEqual(state["scenario_key"], "nominal-orbital")
        self.assertEqual(state["comms"]["packets"], [])
        self.assertEqual(state["t_s"], 2.0)
        self.assertTrue(state["audit"]["verification"]["ok"])
        self.assertGreaterEqual(state["audit"]["verification"]["entries"],
                                before["audit"]["verification"]["entries"])
        events = [e["event"] for e in state["audit"]["entries"]]
        self.assertIn("case.reset", events)
        metabolic = next(o for o in state["organs"] if o["system"] == "metabolic")
        self.assertEqual(metabolic["status"], "NOMINAL")
        self.assertEqual(metabolic["value"], 92.0)  # back to the nominal demo baseline

    def test_reset_is_audited_with_the_prior_head_and_survives_restart(self):
        before = self.client.get("/api/state").json()["audit"]["verification"]
        self.client.post("/api/case/reset", json={}, headers=CREW)
        reset_blocks = [e for e in self.client.get("/api/state").json()["audit"]["entries"]
                        if e["event"] == "case.reset"]
        self.assertEqual(len(reset_blocks), 1)
        self.assertEqual(reset_blocks[0]["detail"]["prior_head_sha256"], before["head"])
        self.client.close()
        self.client = self.boot()
        state = self.client.get("/api/state").json()
        self.assertEqual(state["lifecycle"]["stage"], workflow.S0)
        self.assertTrue(state["audit"]["verification"]["ok"])
        # reset block + the re-seeded scenario.start, and nothing extra on restart.
        self.assertEqual(state["audit"]["verification"]["entries"], before["entries"] + 2)

    def test_reset_requires_a_role(self):
        self.assertEqual(self.client.post("/api/case/reset", json={},
                                          headers=RESEARCH).status_code, 403)


class ReplayLaneTests(WorkstationTestCase):
    def test_recorded_lane_is_labelled_non_astronaut_and_measured(self):
        state = self.client.post("/api/scenario", json={"replay_participant": "s1"},
                                 headers=CREW).json()
        self.assertEqual(state["telemetry_mode"], "RECORDED_REPLAY")
        self.assertIn("NON-ASTRONAUT", state["provenance_banner"])
        self.assertEqual(state["replay"]["participant"], "s1")
        self.assertEqual(state["replay"]["n_windows"], 3332)
        self.assertEqual(state["replay"]["window_s"], 8.0)
        self.assertEqual(state["replay"]["replay_rate_hz"], 1.0)
        self.assertIsNotNone(state["frame"]["hr_bpm"])
        self.assertEqual(state["frame"]["lane"], "RECORDED-NON-ASTRONAUT")
        self.assertTrue(state["gates"][0]["evidence"]["basis"] == "RECORDED_RR_SCREEN"
                        or "RR" in state["gates"][0]["reason"])

    def test_replay_advances_one_window_per_second(self):
        self.client.post("/api/scenario", json={"replay_participant": "s2"}, headers=CREW)
        self.client.post("/api/transport", json={"action": "pause"}, headers=CREW)
        first = self.step(1.0)
        second = self.step(1.0)
        self.assertEqual(second["replay"]["window_index"], first["replay"]["window_index"] + 1)
        self.assertNotEqual(first["frame"]["hr_bpm"], second["frame"]["hr_bpm"])

    def test_unknown_participant_is_rejected(self):
        response = self.client.post("/api/scenario", json={"replay_participant": "s99"},
                                    headers=CREW)
        self.assertEqual(response.status_code, 400)

    def test_replay_status_lists_the_frozen_eight(self):
        body = self.client.get("/api/replay").json()["replay"]
        self.assertTrue(body["available"])
        self.assertEqual(sorted(body["participants"]), ["s1", "s2", "s3", "s4", "s5", "s6", "s8", "s9"])


class ProvenanceLaneTests(WorkstationTestCase):
    def test_goes_is_flux_in_pfu_with_a_dose_disclaimer(self):
        goes = self.client.get("/api/state").json()["sources"]["goes"]
        self.assertEqual(goes["unit"], "pfu")
        self.assertIn("cm^2", goes["unit_long"])
        self.assertIn("not absorbed tissue dose", goes["dose_note"].lower())
        self.assertIn("cache_age_s", goes)
        self.assertFalse(goes["available"])  # offline sandbox: never fabricated

    def test_simulated_dose_placeholder_is_never_attributed_to_goes(self):
        overlays = self.scenario("spe-radiation")["overlays"]
        self.assertEqual(overlays["proton_mgy_day"], 2.6)
        self.assertIn("never derived", overlays["label"])
        self.assertIn("pfu", overlays["label"])

    def test_lab_lane_reports_unavailable_when_uncached(self):
        body = self.client.get("/api/lab/osd575", headers=CREW).json()
        self.assertIn("available", body)
        self.assertIn("OSD-575", str(body))


if __name__ == "__main__":
    unittest.main()
