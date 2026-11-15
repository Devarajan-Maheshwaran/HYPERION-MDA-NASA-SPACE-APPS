"""Unified live-workstation state engine registered onto the FastAPI app.

Adds /api/state, /api/scenario, /api/exams/*, /api/goes/refresh and /api/ml/benchmark, plus
the S0-S4 lifecycle, the surgeon outbox and the recorded-replay lane. Everything simulated
is labelled; everything unavailable says so. No neural risk head, no LLM, no treatment
advice, no on-chain claim.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import Body, FastAPI, Header, HTTPException

from . import benchmark, goes, lanes, outbox, replay, wearable, workflow
from .actions import (CHECK_SENSOR, CONTACT_FLIGHT_SURGEON, REPEAT_MEASUREMENT,
                      REST_AND_RECHECK, actions_for)
from .conformal import upper_bound
from .context import co2_hr_drive
from .gates import ACTIVITY_SATURATION_SCALE, HR_RESERVE_BPM, kurtosis, slew_rate
from .models import Calibration, ManualCheck
from .organs import (MISSION_SECONDS_PER_DEMO_HOUR, MISSION_TAU_LABEL,
                     effective_age_hours, latest_by_kind, organ_readings,
                     readiness_streak, tau)
from .robust import bitflip_demo
from .scenarios import rest_calibration_samples

HABITAT_KEYS = {
    "station": ("Space Station (0g)", "ISS Station (0g, Comms 0.2 s demo)"),
    "transit": ("Transit Ship", "Mars Transit (0g, 12 s demo delay / 20 min scale)"),
    "lunar": ("Lunar Base (0.16g)", "Lunar Base (0.16g, Comms 1.3 s)"),
    "rover": ("Rover", "Surface Rover (EVA, blackout queue)"),
}
HABITAT_BY_LABEL = {v[0]: k for k, v in HABITAT_KEYS.items()}

REAL_BANNER = ("REAL EMPIRICAL DATA MODE — NASA OSD-575 lab lane + NOAA GOES proton flux lane "
               "+ WESAD/PhysioNet availability, each labelled available or NOT AVAILABLE below. "
               "No live astronaut wearable sensor is connected: live telemetry is NOT AVAILABLE "
               "and no simulated frames are shown. Select a scenario or the recorded human replay "
               "to run a labelled stream.")
SIM_BANNER = ("SIMULATED MISSION TELEMETRY FALLBACK (Physics-Guided Physiological Scenario "
              "Engine — Explicitly Labeled Non-Flight Simulation)")
REPLAY_BANNER = ("RECORDED HUMAN REPLAY — PhysioNet Wrist PPG During Exercise v1.0.0, "
                 "RECORDED-NON-ASTRONAUT (8 terrestrial adults, ODC-By 1.0). Heart rate is the "
                 "chest-ECG annotation reference per 8 s window, replayed time-compressed at 1 Hz. "
                 "Not astronaut telemetry, not a wearable estimate, not clinical data.")

DEMO_SCENARIOS: list[dict[str, Any]] = [
    {"id": "nominal-orbital", "label": "1. Nominal 0g", "underlying": "rest-nominal",
     "habitat": "station", "advance_s": 2, "enmo_g": 0.02, "co2_mmhg": 2.5, "proton_mgy_day": 0.3,
     "water_ml": 1800, "ared_min": 30, "stage_hint": "S0",
     "seed": {"bp": (122, 78), "glucose": 92, "temperature": 36.8, "sleep": 7.2,
              "onsd": 4.6, "pvt": 290, "mood": 7}},
    {"id": "eva-ared-exercise", "label": "2. Exercise False-Alarm Test", "underlying": "exercise-false-alarm",
     "habitat": "rover", "advance_s": 55, "enmo_g": 0.31, "co2_mmhg": 3.0, "proton_mgy_day": 0.3,
     "water_ml": 1600, "ared_min": 35, "stage_hint": "S1",
     "seed": {"bp": (122, 78), "glucose": 92, "temperature": 36.8, "sleep": 7.2,
              "onsd": 4.6, "pvt": 290, "mood": 7}},
    {"id": "sans-stale-eye", "label": "3. SANS + Stale Eye Scan", "underlying": "rest-nominal",
     "habitat": "station", "advance_s": 2, "enmo_g": 0.03, "co2_mmhg": 4.2, "proton_mgy_day": 0.3,
     "water_ml": 1700, "ared_min": 25, "stage_hint": "S2",
     "seed": {"bp": (122, 78), "glucose": 92, "temperature": 36.8, "sleep": 7.2,
              "pvt": 290, "mood": 7}, "stale_onsd": {"value": 5.9, "tau": 0.18}},
    {"id": "spe-radiation", "label": "4. Solar Radiation Spike", "underlying": "rest-nominal",
     "habitat": "transit", "advance_s": 2, "enmo_g": 0.02, "co2_mmhg": 2.5, "proton_mgy_day": 2.6,
     "water_ml": 1800, "ared_min": 30, "stage_hint": "S4",
     "seed": {"bp": (122, 78), "glucose": 92, "temperature": 38.1, "sleep": 7.2,
              "onsd": 4.6, "pvt": 290, "mood": 6}},
    {"id": "glycemic-circadian", "label": "5. Glycemic & Sleep Drift", "underlying": "rest-nominal",
     "habitat": "lunar", "advance_s": 2, "enmo_g": 0.02, "co2_mmhg": 2.6, "proton_mgy_day": 0.3,
     "water_ml": 1500, "ared_min": 25, "stage_hint": "S3",
     "seed": {"bp": (122, 78), "glucose": 118, "temperature": 36.8, "sleep": 4.2,
              "onsd": 4.6, "pvt": 365, "mood": 5}},
]
DEMO_BY_ID = {s["id"]: s for s in DEMO_SCENARIOS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _check(subject: str, kind: str, value: float | None = None, *,
           systolic: float | None = None, diastolic: float | None = None,
           hours_ago: float = 0.0, mission_t_s: float | None = None,
           source: str = "scenario seed (SIMULATED, unverified)") -> ManualCheck:
    units = {"bp": "mmHg", "glucose": "mg/dL", "temperature": "degC", "sleep": "h",
             "onsd": "mm", "pvt": "ms", "mood": "1-10"}
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="milliseconds")
    return ManualCheck(subject_id=subject, kind=kind, value=value, systolic=systolic,  # type: ignore[arg-type]
                       diastolic=diastolic, unit=units.get(kind, ""), recorded_at=ts,
                       lane="INJECTED", source=source, mission_t_s=mission_t_s)


def _calibrate(store: Any, subject: str) -> Calibration:
    samples = rest_calibration_samples()
    hrs = [s["hr_bpm"] for s in samples]
    mags = [s["magnitude"] for s in samples]
    kurts = [k for k in (kurtosis(s["window"]) for s in samples) if k is not None]
    slews = [v for v in (slew_rate(s["window"], 25.0) for s in samples) if v is not None]
    hr_med = statistics.median(hrs)
    hr_scale = statistics.pstdev(hrs) or 1.0
    residuals = [abs(h - hr_med) for h in hrs]
    q95 = sorted(residuals)[max(0, int(0.95 * len(residuals)) - 1)]
    cal = Calibration(
        subject_id=subject, calibrated=True, n_windows=len(samples),
        source="SIMULATED resting window (workstation demo calibration)", lane="SIMULATED",
        rest_hr_median=hr_med, rest_hr_scale=hr_scale,
        rest_activity_median=statistics.median(mags),
        rest_activity_scale=statistics.pstdev(mags) or 0.01,
        residual_q95=q95,
        kurtosis_low=min(kurts) * 0.8 if kurts else None,
        kurtosis_high=max(kurts) * 1.25 if kurts else None,
        slew_high=max(slews) * 1.5 if slews else None,
        created_at=_now(),
        note="DEMO calibration from SIMULATED data. Activity is per-person rest scales, not ENMO in g.",
    )
    store.calibrations[subject] = cal
    store.holds.pop(subject, None)
    return cal


def _calibrate_recorded(store: Any, subject: str, windows: list) -> Calibration:
    """Descriptive calibration from the replayed participant's own recorded windows."""
    values = replay.calibration_values(windows)
    cal = Calibration(
        subject_id=subject, calibrated=bool(values["rest_hr_median"] is not None),
        n_windows=len(windows), lane="RECORDED-NON-ASTRONAUT",
        source="PhysioNet recorded windows for this participant (descriptive centre/scale)",
        created_at=_now(),
        **{k: v for k, v in values.items()},
        note=("RECORDED-derived DEMO calibration from this participant's own windows. "
              "Not a clinical calibration. Accelerometer magnitude is uncalibrated header "
              "units, never ENMO in g."),
    )
    store.calibrations[subject] = cal
    store.holds.pop(subject, None)
    return cal


def onsd_from_pixels(x1: float, y1: float, x2: float, y2: float, px_per_mm: float) -> float:
    if px_per_mm <= 0 or not math.isfinite(px_per_mm):
        raise ValueError("px_per_mm must be a positive finite scale")
    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
        raise ValueError("caliper coordinates must be finite")
    return math.hypot(x2 - x1, y2 - y1) / px_per_mm


def _finite_number(payload: dict, key: str, lo: float, hi: float) -> float:
    try:
        value = float(payload[key])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, f"{key} must be a number")
    if not math.isfinite(value) or not (lo <= value <= hi):
        raise HTTPException(400, f"{key} must be finite and in [{lo:g}, {hi:g}]")
    return value


def _exam_subject(store: Any, payload: dict) -> str:
    subject = payload.get("subject_id", store.subject_id)
    if subject not in store.subjects:
        raise HTTPException(400, "unknown subject_id")
    return subject


def _build_ml_benchmark() -> dict[str, Any]:
    m6 = lanes.m6_results()
    hr_rows: list[dict[str, Any]] = []
    if m6.get("available") and isinstance(m6.get("results"), dict):
        models = (((m6["results"].get("hr") or {}).get("primary") or {}).get("models") or {})
        for name, model in models.items():
            mae = ((model or {}).get("aggregate") or {}).get("mae") or {}
            if isinstance(mae.get("mean"), (int, float)):
                hr_rows.append({"model": name, "mae_bpm": mae["mean"],
                                "ci_low": mae.get("ci_low"), "ci_high": mae.get("ci_high")})
    from hyperion_mda import fl_sim  # src already on sys.path via api.lanes
    run = fl_sim.run_fedavg(n_clients=4, rounds=3, seed=7)
    last = run.logs[-1]
    vectors = [u.weights for u in last.updates]
    flip = bitflip_demo(vectors, silo_index=1)
    measured = benchmark.load()
    return {
        "provenance": "M6 measured offline on non-astronaut PhysioNet (ODC-By 1.0). "
                      "The legacy FL panel below is a toy SIMULATION; the measured FL/DP "
                      "benchmark is reported separately in fl_dp_benchmark.",
        "measured_m6_hr": hr_rows,
        "not_implemented": [
            "PyTorch HyperionCoreNet (~12K params, LayerNorm)",
            "MC-dropout sigma_epistemic",
            "2D-CNN ONSD regressor",
            "Flower framework integration (the measured FL benchmark uses a numpy FedAvg)",
            "Opacus integration (the measured DP benchmark uses a numpy DP-SGD + RDP accountant)",
        ],
        "requested_benchmarks": [
            {"model": "sklearn LogisticRegression", "status": "NOT_IMPLEMENTED", "metric": None},
            {"model": "sklearn RandomForest", "status": "NOT_IMPLEMENTED", "metric": None},
            {"model": "PyTorch HyperionCoreNet (~12K, LayerNorm)", "status": "NOT_IMPLEMENTED", "metric": None},
            {"model": "Flower 4-silo FL", "status": "SIMULATED_TOY_FEDAVG", "metric": None},
            {"model": "Opacus DP-SGD", "status": "NOT_IMPLEMENTED", "metric": "epsilon/delta not available"},
        ],
        "fl_simulation": {"n_clients": run.n_clients, "rounds": run.logs[-1].round_no,
                          "global_weights": last.global_weights,
                          "label": "FL SIMULATION — one process, toy data, no privacy guarantee, no accuracy claim"},
        "cosine_median_demo": flip,
        "fl_dp_benchmark": measured,
    }


def register_workstation(app: FastAPI, store: Any, *, frame_at: Callable, maybe_alert: Callable,
                         envelope: Callable, now: Callable, require: Callable, role_of: Callable,
                         manager: Any, audited: Callable, app_state: dict) -> None:
    ml_benchmark = _build_ml_benchmark()
    # Anchor the toy FL rounds once per audit chain, not once per process: a restart must
    # restore the chain, not append duplicate genesis blocks to it.
    anchored = {e.detail.get("round") for e in manager.audit.entries()
                if e.event == "FEDERATED_ROUND_ANCHORED"}
    for round_no in range(1, ml_benchmark["fl_simulation"]["rounds"] + 1):
        if round_no in anchored:
            continue
        manager.audit.append("FEDERATED_ROUND_ANCHORED", "system", "fl-simulation", "SIMULATED",
                             {"round": round_no, "n_clients": ml_benchmark["fl_simulation"]["n_clients"]})

    def habitat_key() -> str:
        return HABITAT_BY_LABEL.get(store.habitat, "station")

    def seed_scenario(scenario_id: str, role: str) -> None:
        sc = DEMO_BY_ID[scenario_id]
        st = manager.current
        subject = st.subject_id
        _calibrate(st, subject)
        st.checks[subject] = []
        st.t_s = 0.0
        for kind, val in sc["seed"].items():
            if kind == "bp":
                st.checks[subject].append(_check(subject, "bp", systolic=val[0], diastolic=val[1],
                                                 mission_t_s=0.0))
            else:
                st.checks[subject].append(_check(subject, kind, float(val), mission_t_s=0.0))
        if "stale_onsd" in sc:
            target_tau = sc["stale_onsd"]["tau"]
            hours = -math.log(target_tau) / 0.15
            st.checks[subject].append(_check(subject, "onsd", sc["stale_onsd"]["value"],
                                             hours_ago=hours,
                                             mission_t_s=-hours * MISSION_SECONDS_PER_DEMO_HOUR))
        st.ws.update({"booted": True, "mode": "SIMULATED_FALLBACK", "scenario_key": sc["id"],
                      "enmo_g": sc["enmo_g"], "co2_mmhg": sc["co2_mmhg"],
                      "proton_mgy_day": sc["proton_mgy_day"], "water_ml": sc.get("water_ml"),
                      "ared_min": sc.get("ared_min"), "replay_participant": None,
                      "underlying_scenario_id": sc["underlying"]})
        st.habitat = HABITAT_KEYS[sc["habitat"]][0]
        st.scenario_id = sc["underlying"]
        st.running = True
        st.frames = []
        st.outbox = []
        st.workflow = workflow.WorkflowRecord(updated_at=_now())
        st.holds.pop(subject, None)
        st.replay_windows = []
        audited("scenario.start", role, subject, "SIMULATED",
                {"scenario_id": sc["id"], "underlying": sc["underlying"]})
        blocked = False
        for t in range(0, int(sc["advance_s"]) + 1):
            st.t_s = float(t)
            frame = frame_at(sc["underlying"], float(t))
            st.frames.append(frame)
            maybe_alert(frame, role)
            blocked = blocked or frame.suppressed
        st.frames = st.frames[-600:]
        if blocked:
            audited("GATE_2_FALSE_ALARM_BLOCKED", role, subject, "SIMULATED", {"scenario_id": sc["id"]})
        refresh_workflow(st, role, escalated_audit=True)

    def start_replay(participant: str, role: str) -> None:
        st = manager.current
        known = replay.participants()
        if known and participant not in known:
            raise HTTPException(400, f"unknown replay participant {participant!r}; choose from {known}")
        windows = replay.load(participant)
        if not windows:
            raise HTTPException(409, f"no verified recorded windows for participant {participant!r}; "
                                     "the committed M6 windows.csv is required")
        subject = st.subject_id
        st.replay_windows = windows
        _calibrate_recorded(st, subject, windows)
        st.checks[subject] = []
        st.t_s = 0.0
        st.frames = []
        st.outbox = []
        st.workflow = workflow.WorkflowRecord(updated_at=_now())
        st.holds.pop(subject, None)
        st.ws.update({"booted": True, "mode": "RECORDED_REPLAY", "scenario_key": None, "enmo_g": None,
                      "co2_mmhg": None, "proton_mgy_day": None, "water_ml": None,
                      "ared_min": None, "replay_participant": participant,
                      "underlying_scenario_id": f"replay:{participant}"})
        st.scenario_id = f"replay:{participant}"
        st.running = True
        audited("replay.start", role, subject, "RECORDED-NON-ASTRONAUT",
                {"participant": participant, "n_windows": len(windows)})
        frame = frame_at(st.scenario_id, 0.0)
        st.frames.append(frame)
        refresh_workflow(st, role, escalated_audit=True)

    def refresh_workflow(st: Any, role: str, *, escalated_audit: bool = False) -> None:
        """Recompute organs/triage, advance the FSM, run the outbox and broadcast."""
        frame = st.frames[-1].model_dump() if st.frames else None
        organs = [o.model_dump() for o in organ_readings(
            st.checks_for(st.subject_id), context=_context(st, frame),
            mission_now_s=_mission_now(st))]
        top = active_sensing(organs, st)["top"]
        transition = workflow.apply(st.workflow, frame, organs, mission_t_s=st.t_s, now=_now(),
                                    active_top=(top or {}).get("exam"))
        if transition:
            manager.db.record_transition(st.case_id, transition["from_stage"], transition["to_stage"],
                                         transition["reason"], st.t_s, transition["ts"])
            audited("workflow.transition", role, st.subject_id, (frame or {}).get("lane", "NONE"),
                    {"from_stage": transition["from_stage"], "to_stage": transition["to_stage"],
                     "reason_code": transition["to_stage"]})
        if st.workflow.stage == workflow.S4:
            enqueue_escalation(st, frame, organs, role)
        if escalated_audit and frame and frame.get("state") == "SURGEON_ALERT":
            audited("SURGEON_ESCALATION", role, st.subject_id, frame.get("lane", "NONE"),
                    {"scenario_id": st.ws.get("scenario_key") or st.scenario_id})
        changed = outbox.advance(st.outbox, now_iso=_now(), blackout=comms_blackout(st))
        for change in changed:
            audited("comms.packet_state", "system", st.subject_id, "NONE", change)

    def comms_blackout(st: Any) -> bool:
        profile = outbox.profile_for(HABITAT_BY_LABEL.get(st.habitat, "station"))
        return bool(st.ws.get("blackout")) or profile.blackout

    def enqueue_escalation(st: Any, frame: dict | None, organs: list[dict], role: str) -> None:
        fp = st.workflow.finding_fingerprint or "no-finding"
        if any(p["fingerprint"] == fp and p["comms_state"] != outbox.ACKNOWLEDGED
               for p in st.outbox):
            return
        if any(p["fingerprint"] == fp for p in st.outbox) and st.workflow.stage == workflow.S4_ACK:
            return
        alert_organs = [o for o in organs if o["status"] == "ALERT"]
        organ = alert_organs[0]["label"] if alert_organs else "Deterministic gate"
        finding = alert_organs[0]["indicator"] if alert_organs else (frame or {}).get("state", "alert")
        sbar = outbox.build_sbar(organ=organ, finding=finding, frame=frame, organs=organs,
                                 triage=triage_for(st, frame, organs),
                                 habitat_label=HABITAT_KEYS[habitat_key()][1],
                                 lane=(frame or {}).get("lane", "NONE"))
        packet = outbox.enqueue(case_id=st.case_id, organ=organ, finding=finding, fingerprint=fp,
                                habitat=habitat_key(), sbar=sbar, now_iso=_now(),
                                blackout_override=comms_blackout(st))
        st.outbox.append(packet)
        audited("surgeon.packet_queued", role, st.subject_id, (frame or {}).get("lane", "NONE"),
                {"packet_id": packet["packet_id"], "comms_state": packet["comms_state"],
                 "sbar_sha256": outbox.digest(sbar)})

    def tick_hook(st: Any, *, advanced: bool) -> None:
        """Called by the 1 Hz clock and after manual steps/exams."""
        if advanced and st.scenario_id is not None:
            frame = frame_at(st.scenario_id, st.t_s)
            st.frames.append(frame)
            st.frames = st.frames[-600:]
            maybe_alert(frame, st.role)
            st.broadcast(frame)
        refresh_workflow(st, st.role)
        if app_state.get("live_payload") and st.state_subscribers:
            token = manager.set_active(st.case_id)
            try:
                st.broadcast_state(app_state["live_payload"]())
            finally:
                manager.reset_active(token)

    manager.tick_hook = tick_hook
    app_state["seed_scenario"] = seed_scenario
    app_state["start_replay"] = start_replay
    app_state["refresh_workflow"] = refresh_workflow

    def reevaluate_current(role: str) -> None:
        """Re-run the gates at the current mission time after a crew exam.

        Replaces the last frame instead of appending a duplicate timestamp, then advances
        the lifecycle so an examined finding resolves or escalates immediately.
        """
        st = manager.current
        if st.scenario_id is None or not st.frames:
            refresh_workflow(st, role)
            return
        frame = frame_at(st.scenario_id, st.t_s)
        st.frames[-1] = frame
        maybe_alert(frame, role)
        st.broadcast(frame)
        audited("exam.reevaluate", role, st.subject_id, frame.lane,
                {"scenario_id": st.ws.get("scenario_key") or st.scenario_id})
        refresh_workflow(st, role)

    def _mission_now(st: Any) -> float | None:
        if st.ws.get("scenario_key") or st.ws.get("mode") == "RECORDED_REPLAY":
            return float(st.t_s)
        return None

    def _context(st: Any, frame: dict | None) -> dict:
        return {**st.ws, "hr_bpm": (frame or {}).get("hr_bpm"),
                "hr_suppressed": (frame or {}).get("suppressed", False)}

    def latest_tau(kind: str) -> float | None:
        st = manager.current
        checks = st.checks_for(st.subject_id)
        check = latest_by_kind(checks).get(kind)
        if check is None:
            return None
        age = effective_age_hours(check, mission_now_s=_mission_now(st))
        return tau(age) if age is not None else None

    def active_sensing(organs: list[dict], st: Any | None = None) -> dict:
        organ_by_kind = {"onsd": "head-eyes", "pvt": "brain", "bp": "heart",
                         "glucose": "metabolic", "temperature": "chest-immune", "sleep": "brain"}
        weight = {"ALERT": 1.0, "WATCH": 0.6, "UNKNOWN": 0.8, "NOT_AVAILABLE": 0.7, "NOMINAL": 0.1}
        cost = {"onsd": 2.0, "pvt": 0.25, "bp": 1.0, "glucose": 1.0, "temperature": 0.5, "sleep": 0.5}
        label = {"onsd": "Guided eye ultrasound (ONSD mm)", "pvt": "15 s click PVT",
                 "bp": "Cuff blood pressure", "glucose": "Fingerstick glucose",
                 "temperature": "Core temperature", "sleep": "Sleep log"}
        status_by_system = {o["system"]: o["status"] for o in organs}
        ranked = []
        for kind, system in organ_by_kind.items():
            t = latest_tau(kind)
            freshness = t if t is not None else 0.0
            risk = weight.get(status_by_system.get(system, "NOT_AVAILABLE"), 0.7)
            score = risk * (1.0 - freshness) / max(cost[kind], 0.1)
            ranked.append({"exam": kind, "label": label[kind], "tau": t, "score": round(score, 4),
                           "cost_min": cost[kind]})
        ranked.sort(key=lambda r: r["score"], reverse=True)
        return {"ranked": ranked, "top": ranked[0] if ranked else None,
                "label": "demo active-sensing heuristic (risk weight x staleness / cost); "
                         "NOT the deck's conformal score because sigma_epistemic does not exist"}

    def triage_for(st: Any, frame: dict | None, organs: list[dict]) -> dict:
        """Triage tier follows the persisted S0-S4 stage so banner and card never disagree."""
        stage = st.workflow.stage
        gate3 = next((g for g in (frame or {}).get("gates", []) if g["gate"] == 3), None)
        tier = workflow.STAGE_TRIAGE.get(stage, "UNKNOWN")
        if stage == workflow.S1:
            actions = actions_for(REST_AND_RECHECK)
            why = "Gate 2 blocked an exercise false alarm; movement explains the rate."
        elif stage == workflow.S2:
            requested = (gate3 or {}).get("evidence", {}).get("requested_exam")
            actions = actions_for(REPEAT_MEASUREMENT, REST_AND_RECHECK)
            why = st.workflow.reason + (
                " Run the guided eye ultrasound in the instrument bay next."
                if requested == "ultrasound" else " Complete the highlighted crew check next.")
        elif stage == workflow.S3:
            actions = actions_for(REST_AND_RECHECK, REPEAT_MEASUREMENT)
            why = st.workflow.reason + ". Onboard crew countermeasure/recheck loop (demo routing)."
        elif stage == workflow.S4_ACK:
            actions = actions_for(REPEAT_MEASUREMENT)
            why = "Flight surgeon acknowledged this finding; receipt anchored in the local audit chain."
        elif stage == workflow.S4:
            actions = actions_for(CONTACT_FLIGHT_SURGEON, REPEAT_MEASUREMENT)
            why = st.workflow.reason + ". SBAR packet queued in the store-and-forward outbox."
        elif frame is None or (frame or {}).get("state") == "UNKNOWN":
            tier, actions = "UNKNOWN", actions_for(CHECK_SENSOR, REPEAT_MEASUREMENT)
            why = "No calibrated decision is available."
        else:
            actions = actions_for(REPEAT_MEASUREMENT)
            why = "No demo rule or gate raised a finding."
        return {"tier": tier, "why": why,
                "crew_or_surgeon": "Flight surgeon escalation" if tier == "SURGEON"
                else "Can be handled by crew onboard" if tier in {"CREW", "WATCH", "NOMINAL"} else "Unknown",
                "actions": actions,
                "steps": ["Read the lane/provenance badge before acting.",
                          "Repeat the indicated measurement with the listed crew tool.",
                          "If the finding persists or escalates, contact the flight surgeon."],
                "label": "DEMO triage, not NASA-STD-3001 compliance and not treatment advice"}

    # Backwards-compatible alias used by the earlier seeding path.
    def triage(frame: dict | None, organs: list[dict]) -> dict:
        return triage_for(manager.current, frame, organs)

    def state_payload(*, live: bool = False) -> dict[str, Any]:
        st = manager.current
        ws = st.ws
        subject = st.subject_id
        checks = st.checks_for(subject)
        frame = st.frames[-1].model_dump() if st.frames else None
        cal = st.calibration(subject)
        mission_now = _mission_now(st)
        context = _context(st, frame)
        organs = [o.model_dump() for o in organ_readings(checks, context=context,
                                                        mission_now_s=mission_now)]
        if frame and frame.get("hr_bpm") is not None and cal.calibrated and cal.rest_hr_median is not None and cal.rest_hr_scale:
            z = (frame["hr_bpm"] - cal.rest_hr_median) / cal.rest_hr_scale
            for organ in organs:
                if organ["system"] == "heart":
                    organ["z_score"] = z
                    organ["baseline_note"] = (
                        "z_t vs this lane's personal resting HR calibration (demo, not a clinical z-score).")
        scores = []
        expected = None
        if cal.calibrated and cal.rest_hr_median is not None:
            if ws.get("mode") == "RECORDED_REPLAY":
                scores = [w.hr_bpm - cal.rest_hr_median for w in st.replay_windows if w.hr_bpm is not None]
            else:
                scores = [s["hr_bpm"] - cal.rest_hr_median for s in rest_calibration_samples()]
            expected = cal.rest_hr_median
            if frame and frame.get("activity_norm") is not None:
                drive = 1.0 - math.exp(-max(0.0, frame["activity_norm"]) / ACTIVITY_SATURATION_SCALE)
                expected = cal.rest_hr_median + HR_RESERVE_BPM * drive + co2_hr_drive(ws.get("co2_mmhg"))
        conf = upper_bound(expected, scores, ws["alpha"])
        history = []
        for f in st.frames[-180:]:
            d = f.model_dump()
            history.append({"t_s": d["t_s"], "hr_bpm": d["hr_bpm"], "residual_bpm": d["residual_bpm"],
                            "activity_norm": d["activity_norm"], "enmo_g": ws["enmo_g"],
                            "co2_mmhg": ws["co2_mmhg"], "band_upper": d["band_upper"],
                            "band_lower": d["band_lower"], "conformal_upper": conf["upper"],
                            "state": d["state"], "suppressed": d["suppressed"]})
        taus = [o["staleness_tau"] for o in organs if o["staleness_tau"] is not None]
        freshness = sum(taus) / len(taus) if taus else None
        readiness = readiness_streak(checks)
        logged = {c.kind for c in checks}
        badges = [{"id": k, "label": l, "unlocked": k in logged} for k, l in
                  [("bp", "Vitals"), ("glucose", "Glycemic"), ("onsd", "SANS watch"),
                   ("pvt", "Alertness"), ("sleep", "Circadian")]]
        lab = lanes.lab_lane()
        goes_state = goes.summary()
        wear = wearable.status()
        mode = ws["mode"]
        if mode == "RECORDED_REPLAY":
            banner = REPLAY_BANNER
            telemetry_mode = "RECORDED_REPLAY"
        elif mode == "REAL_EMPIRICAL":
            banner = REAL_BANNER
            telemetry_mode = "REAL_EMPIRICAL" if wear["available"] else "NOT_AVAILABLE"
        else:
            banner = SIM_BANNER
            telemetry_mode = "SIMULATED_FALLBACK"
        audit_state = manager.audit.verify()
        entries = [e.model_dump() for e in manager.audit.entries()[-50:]]
        key = habitat_key()
        sensing = active_sensing(organs, st)
        result = envelope(
            lane=(frame or {}).get("lane", "SIMULATED" if telemetry_mode == "SIMULATED_FALLBACK" else lab.lane),
            provenance=banner,
            habitat=key, habitat_label=HABITAT_KEYS[key][1], habitat_options=[
                {"key": k, "label": v[1]} for k, v in HABITAT_KEYS.items()],
            data_source_mode="SIMULATED_FALLBACK" if mode == "SIMULATED_FALLBACK" else "REAL_EMPIRICAL",
            telemetry_mode=telemetry_mode, provenance_banner=banner,
            subject_id=subject, scenario_key=ws["scenario_key"], running=st.running, t_s=st.t_s,
            case_id=st.case_id, session_id=st.session_id,
            clock={"hz": 1.0, "period_s": 1.0, "running": st.running,
                   "mission_seconds_per_demo_hour": MISSION_SECONDS_PER_DEMO_HOUR,
                   "tau_basis": MISSION_TAU_LABEL},
            lifecycle=workflow.banner(st.workflow),
            comms={"profile": outbox.profile_for(key).__dict__, "blackout": comms_blackout(st),
                   "packets": outbox.public_view(st.outbox)},
            demo_scenarios=[{"id": s["id"], "label": s["label"], "stage_hint": s["stage_hint"]}
                            for s in DEMO_SCENARIOS],
            replay={"active": mode == "RECORDED_REPLAY", "participant": ws.get("replay_participant"),
                    "active_windows": len(st.replay_windows),
                    "window_index": (int(st.t_s) % len(st.replay_windows)) if st.replay_windows else None,
                    **replay.status()},
            sources={"lab": lab.model_dump(), "goes": goes_state, "wearable": wear},
            organs=organs, frame=frame, history=history,
            gates=(frame or {}).get("gates", []),
            conformal=conf, active_sensing=sensing, triage=triage_for(st, frame, organs),
            overlays={"enmo_g": ws["enmo_g"], "co2_mmhg": ws["co2_mmhg"],
                      "proton_mgy_day": ws["proton_mgy_day"], "water_ml": ws["water_ml"],
                      "ared_min": ws["ared_min"],
                      "label": "SIMULATED reference channels; ENMO g is a demo display value, "
                               "the gate uses per-person scale-normalised activity. "
                               "proton_mgy_day is a SIMULATED dose placeholder, never derived "
                               "from GOES flux (pfu)."},
            countermeasure_flags={"water_low": None if ws["water_ml"] is None else ws["water_ml"] < 1400,
                                  "ared_low": None if ws["ared_min"] is None else ws["ared_min"] < 20,
                                  "label": "DEMO countermeasure flags, not treatment advice"},
            readiness={**readiness, "freshness_tau_avg": freshness, "badges": badges},
            audit={"verification": audit_state, "entries": entries,
                   "contract": "HealthAudit.sol reference only — NOT deployed, NOT on-chain",
                   "badge": "ZERO RAW PRIVATE HEALTH DATA ON-CHAIN (local hash chain; no chain exists)"},
        )
        if not live:
            result["ml_benchmark"] = ml_benchmark
        return result

    def live_payload() -> dict[str, Any]:
        return state_payload(live=True)

    app_state["state_payload"] = state_payload
    app_state["live_payload"] = live_payload

    @app.get("/api/state")
    def get_state() -> dict:
        boot = app_state.get("ensure_booted")
        if boot is not None:
            boot()
        return state_payload()

    @app.post("/api/scenario")
    def post_scenario(payload: dict = Body(default_factory=dict),
                      x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        st = manager.current
        if payload.get("replay_participant"):
            start_replay(str(payload["replay_participant"]), role)
        if "scenario_id" in payload and payload["scenario_id"]:
            sid = payload["scenario_id"]
            if sid not in DEMO_BY_ID:
                raise HTTPException(400, f"unknown demo scenario {sid!r}; choose from {[s['id'] for s in DEMO_SCENARIOS]}")
            seed_scenario(sid, role)
        if "habitat" in payload and payload["habitat"]:
            key = payload["habitat"]
            if key not in HABITAT_KEYS:
                raise HTTPException(400, f"habitat must be one of {list(HABITAT_KEYS)}")
            st.habitat = HABITAT_KEYS[key][0]
            outbox.advance(st.outbox, now_iso=_now(), blackout=comms_blackout(st))
        if "mode" in payload and payload["mode"]:
            mode = payload["mode"]
            if mode not in {"REAL_EMPIRICAL", "SIMULATED_FALLBACK"}:
                raise HTTPException(400, "mode must be REAL_EMPIRICAL or SIMULATED_FALLBACK")
            st.ws["mode"] = mode
            st.ws["booted"] = True
            if mode == "REAL_EMPIRICAL":
                st.running = False
                st.frames = []
                st.scenario_id = None
                st.replay_windows = []
                st.ws["scenario_key"] = None
                st.ws["replay_participant"] = None
                st.ws.update({"enmo_g": None, "co2_mmhg": None, "proton_mgy_day": None,
                              "water_ml": None, "ared_min": None})
            audited("session.change", role, st.subject_id, "NONE", {"mode": mode})
        refresh_workflow(st, role)
        return state_payload()

    def _stamp(exam: ManualCheck) -> ManualCheck:
        exam.mission_t_s = float(manager.current.t_s)
        return exam

    @app.post("/api/exams/pvt")
    def exam_pvt(payload: dict = Body(...), x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        times = payload.get("reaction_ms") or []
        if not isinstance(times, list) or not times:
            raise HTTPException(400, "reaction_ms must be a non-empty list")
        try:
            values = [float(v) for v in times]
        except (TypeError, ValueError):
            raise HTTPException(400, "reaction_ms must be numeric")
        if any(not math.isfinite(v) or v <= 0 or v > 10000 for v in values):
            raise HTTPException(400, "reaction_ms out of plausible range (0, 10000]")
        if len(values) > 5:
            raise HTTPException(400, "the demo PVT accepts at most 5 trials")
        median = statistics.median(values)
        st = manager.current
        subject = _exam_subject(st, payload)
        st.checks.setdefault(subject, []).append(_stamp(
            ManualCheck(subject_id=subject, kind="pvt", value=median, unit="ms",
                        recorded_at=now(), source="15 s reaction test (crew, demo)")))
        audited("pvt.result", role, subject, "INJECTED", {"kind": "pvt", "n": len(values)})
        reevaluate_current(role)
        return state_payload()

    @app.post("/api/exams/ultrasound")
    def exam_ultrasound(payload: dict = Body(...), x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        st = manager.current
        subject = _exam_subject(st, payload)
        sample_kind = payload.get("sample")
        if sample_kind in {"nominal", "sans"}:
            mm = 4.6 if sample_kind == "nominal" else 6.1
            px_per_mm = 20.0
            x1, y1, x2, y2 = 100.0, 100.0, 100.0 + mm * px_per_mm, 100.0
            source = f"SAMPLE B-mode frame ({sample_kind}); known ONSD, not a patient scan"
        else:
            try:
                px_per_mm = float(payload["px_per_mm"])
                x1, y1, x2, y2 = (float(payload[k]) for k in ("x1", "y1", "x2", "y2"))
                mm = onsd_from_pixels(x1, y1, x2, y2, px_per_mm)
            except (KeyError, TypeError, ValueError):
                raise HTTPException(400, "custom caliper requires px_per_mm and x1,y1,x2,y2; "
                                         "an uploaded image without a pixel scale cannot yield mm")
            source = "manual retrobulbar caliper (crew, demo); not automated diagnosis"
        if not (1.0 <= mm <= 15.0):
            raise HTTPException(400, "computed ONSD outside plausible demo range 1-15 mm")
        st.checks.setdefault(subject, []).append(_stamp(
            ManualCheck(subject_id=subject, kind="onsd", value=mm, unit="mm",
                        recorded_at=now(), source=source)))
        audited("manual.entry", role, subject, "INJECTED", {"kind": "onsd"})
        reevaluate_current(role)
        state = state_payload()
        state["caliper"] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "px_per_mm": px_per_mm,
                            "onsd_mm": mm, "retrobulbar_mm": 3.0,
                            "note": "measurement line placed 3 mm behind the globe; manual caliper, demo only"}
        return state

    @app.post("/api/exams/vitals")
    def exam_vitals(payload: dict = Body(...), x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        st = manager.current
        subject = _exam_subject(st, payload)
        kinds: list[str] = []
        ranges = {"glucose_mgdl": (20, 600), "temp_c": (30, 43), "sleep_hrs": (0, 24),
                  "mood_score": (1, 10), "water_ml": (0, 10000), "ared_min": (0, 600),
                  "bp_sys": (50, 250), "bp_dia": (30, 150)}
        parsed = {key: _finite_number(payload, key, lo, hi)
                  for key, (lo, hi) in ranges.items() if payload.get(key) is not None}
        if ("bp_sys" in parsed) != ("bp_dia" in parsed):
            raise HTTPException(400, "bp_sys and bp_dia must be supplied together")
        if "bp_sys" in parsed:
            if parsed["bp_dia"] >= parsed["bp_sys"]:
                raise HTTPException(400, "bp_dia must be lower than bp_sys")
            st.checks.setdefault(subject, []).append(_stamp(
                ManualCheck(subject_id=subject, kind="bp", systolic=parsed["bp_sys"],
                            diastolic=parsed["bp_dia"], unit="mmHg", recorded_at=now(),
                            source="keyboard crew vitals (demo, unverified)")))
            kinds.append("bp")
        mapping = {"glucose_mgdl": ("glucose", "mg/dL"), "temp_c": ("temperature", "degC"),
                   "sleep_hrs": ("sleep", "h"), "mood_score": ("mood", "1-10")}
        for field, (kind, unit) in mapping.items():
            if field in parsed:
                st.checks.setdefault(subject, []).append(_stamp(
                    ManualCheck(subject_id=subject, kind=kind, value=parsed[field],  # type: ignore[arg-type]
                                unit=unit, recorded_at=now(),
                                source="keyboard crew vitals (demo, unverified)")))
                kinds.append(kind)
        if "water_ml" in parsed:
            st.ws["water_ml"] = parsed["water_ml"]
        if "ared_min" in parsed:
            st.ws["ared_min"] = parsed["ared_min"]
        if not kinds and "water_ml" not in parsed and "ared_min" not in parsed:
            raise HTTPException(400, "no vitals fields supplied")
        audited("manual.entry", role, subject, "INJECTED", {"kinds": kinds})
        reevaluate_current(role)
        return state_payload()

    @app.post("/api/goes/refresh")
    def refresh_goes(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("ops", "researcher", "flight-surgeon", "crew"))
        return envelope(lane="NONE", provenance="NOAA GOES integral proton flux lane (pfu, not dose)",
                        goes=goes.load(fetch=True))

    @app.get("/api/ml/benchmark")
    def get_ml_benchmark() -> dict:
        return envelope(lane="RECORDED-NON-ASTRONAUT", provenance=ml_benchmark["provenance"],
                        benchmark=ml_benchmark)

    @app.get("/api/benchmark/fl-dp")
    def get_fl_dp_benchmark() -> dict:
        return envelope(lane="RECORDED-NON-ASTRONAUT",
                        provenance="committed artifacts/fl_dp_benchmark_results.json",
                        benchmark=benchmark.load())