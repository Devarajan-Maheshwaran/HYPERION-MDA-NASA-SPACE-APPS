"""Unified live-workstation state engine registered onto the existing FastAPI app.

Adds /api/state, /api/scenario, /api/exams/*, /api/goes/refresh and /api/ml/benchmark
without rewriting the tested gate engine. Everything simulated is labelled; everything
unavailable says so. No neural risk head, no LLM, no treatment advice, no on-chain claim.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import Body, FastAPI, Header, HTTPException

from . import goes, lanes, wearable
from .actions import (CHECK_SENSOR, CONTACT_FLIGHT_SURGEON, REPEAT_MEASUREMENT,
                      REST_AND_RECHECK, actions_for)
from .conformal import upper_bound
from .context import co2_hr_drive
from .gates import ACTIVITY_SATURATION_SCALE, HR_RESERVE_BPM, kurtosis, slew_rate
from .models import Calibration, ManualCheck
from .organs import (age_hours, latest_by_kind, organ_readings, readiness_streak, tau)
from .robust import bitflip_demo
from .scenarios import rest_calibration_samples

HABITAT_KEYS = {
    "station": ("Space Station (0g)", "Orbital Space Station (0g, Delay: 0.1s)"),
    "transit": ("Transit Ship", "Deep-Space Transit Ship (0g, Delay: 20 min)"),
    "lunar": ("Lunar Base (0.16g)", "Lunar Base (0.16g, Delay: 1.3s)"),
    "rover": ("Rover", "Surface Rover (EVA High Exertion)"),
}
HABITAT_BY_LABEL = {v[0]: k for k, v in HABITAT_KEYS.items()}

REAL_BANNER = ("REAL EMPIRICAL DATA MODE — NASA OSD-575 lab lane + NOAA GOES proton lane "
               "+ WESAD/PhysioNet wearable lane, each labelled available or NOT AVAILABLE below. "
               "No live astronaut wearable sensor is connected: live telemetry is NOT AVAILABLE "
               "and no simulated frames are shown. Select a scenario to run explicitly labelled "
               "SIMULATED_FALLBACK.")
SIM_BANNER = ("SIMULATED MISSION TELEMETRY FALLBACK (Physics-Guided Physiological Scenario "
              "Engine — Explicitly Labeled Non-Flight Simulation)")

DEMO_SCENARIOS: list[dict[str, Any]] = [
    {"id": "nominal-orbital", "label": "1. Nominal 0g", "underlying": "rest-nominal",
     "habitat": "station", "advance_s": 2, "enmo_g": 0.02, "co2_mmhg": 2.5, "proton_mgy_day": 0.3,
     "water_ml": 1800, "ared_min": 30,
     "seed": {"bp": (122, 78), "glucose": 92, "temperature": 36.8, "sleep": 7.2,
              "onsd": 4.6, "pvt": 290, "mood": 7}},
    {"id": "eva-ared-exercise", "label": "2. Exercise False-Alarm Test", "underlying": "exercise-false-alarm",
     "habitat": "rover", "advance_s": 55, "enmo_g": 0.31, "co2_mmhg": 3.0, "proton_mgy_day": 0.3,
     "water_ml": 1600, "ared_min": 35,
     "seed": {"bp": (122, 78), "glucose": 92, "temperature": 36.8, "sleep": 7.2,
              "onsd": 4.6, "pvt": 290, "mood": 7}},
    {"id": "sans-stale-eye", "label": "3. SANS + Stale Eye Scan", "underlying": "stale-manual",
     "habitat": "station", "advance_s": 2, "enmo_g": 0.03, "co2_mmhg": 4.2, "proton_mgy_day": 0.3,
     "water_ml": 1700, "ared_min": 25,
     "seed": {"bp": (122, 78), "glucose": 92, "temperature": 36.8, "sleep": 7.2,
              "pvt": 290, "mood": 7}, "stale_onsd": {"value": 5.9, "tau": 0.18}},
    {"id": "spe-radiation", "label": "4. Solar Radiation Spike", "underlying": "rest-nominal",
     "habitat": "transit", "advance_s": 2, "enmo_g": 0.02, "co2_mmhg": 2.5, "proton_mgy_day": 2.6,
     "water_ml": 1800, "ared_min": 30,
     "seed": {"bp": (122, 78), "glucose": 92, "temperature": 38.1, "sleep": 7.2,
              "onsd": 4.6, "pvt": 290, "mood": 6}},
    {"id": "glycemic-circadian", "label": "5. Glycemic & Sleep Drift", "underlying": "rest-nominal",
     "habitat": "lunar", "advance_s": 2, "enmo_g": 0.02, "co2_mmhg": 2.6, "proton_mgy_day": 0.3,
     "water_ml": 1500, "ared_min": 25,
     "seed": {"bp": (122, 78), "glucose": 118, "temperature": 36.8, "sleep": 4.2,
              "onsd": 4.6, "pvt": 365, "mood": 5}},
]
DEMO_BY_ID = {s["id"]: s for s in DEMO_SCENARIOS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _check(subject: str, kind: str, value: float | None = None, *,
           systolic: float | None = None, diastolic: float | None = None,
           hours_ago: float = 0.0, source: str = "scenario seed (SIMULATED, unverified)") -> ManualCheck:
    units = {"bp": "mmHg", "glucose": "mg/dL", "temperature": "degC", "sleep": "h",
             "onsd": "mm", "pvt": "ms", "mood": "1-10"}
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="milliseconds")
    return ManualCheck(subject_id=subject, kind=kind, value=value, systolic=systolic,  # type: ignore[arg-type]
                       diastolic=diastolic, unit=units.get(kind, ""), recorded_at=ts,
                       lane="INJECTED", source=source)


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
    return {
        "provenance": "M6 measured offline on non-astronaut PhysioNet (ODC-By 1.0). "
                      "FL panel is the existing toy FedAvg SIMULATION, not Flower, not DP.",
        "measured_m6_hr": hr_rows,
        "not_implemented": [
            "scikit-learn LogisticRegression / RandomForest baselines (M6 uses numpy/scipy ridge/logistic)",
            "PyTorch HyperionCoreNet (~12K params, LayerNorm)",
            "Flower 4-silo federated learning across real sites",
            "Opacus DP-SGD (epsilon, delta)",
            "MC-dropout sigma_epistemic",
        ],
        "requested_benchmarks": [
            {"model": "sklearn LogisticRegression", "status": "NOT_IMPLEMENTED", "metric": None},
            {"model": "sklearn RandomForest", "status": "NOT_IMPLEMENTED", "metric": None},
            {"model": "PyTorch HyperionCoreNet (~12K, LayerNorm)", "status": "NOT_IMPLEMENTED", "metric": None},
            {"model": "Flower 4-silo FL", "status": "SIMULATED_TOY_FEDAVG", "metric": None},
            {"model": "Opacus DP-SGD", "status": "NOT_IMPLEMENTED", "metric": "epsilon/delta not available"},
        ],
        "fl_simulation": {"n_clients": run.n_clients, "rounds": run.rounds,
                          "global_weights": last.global_weights,
                          "label": "FL SIMULATION — one process, toy data, no privacy guarantee, no accuracy claim"},
        "cosine_median_demo": flip,
    }


def register_workstation(app: FastAPI, store: Any, *, frame_at: Callable, maybe_alert: Callable,
                         envelope: Callable, now: Callable, require: Callable, role_of: Callable) -> None:
    store.ws = {
        "mode": "SIMULATED_FALLBACK", "scenario_key": None,
        "enmo_g": None, "co2_mmhg": None, "proton_mgy_day": None,
        "water_ml": None, "ared_min": None, "alpha": 0.1,
    }
    ml_benchmark = _build_ml_benchmark()
    for round_no in range(1, ml_benchmark["fl_simulation"]["rounds"] + 1):
        store.audit.append("FEDERATED_ROUND_ANCHORED", "system", "fl-simulation", "SIMULATED",
                           {"round": round_no, "n_clients": ml_benchmark["fl_simulation"]["n_clients"]})

    def habitat_key() -> str:
        return HABITAT_BY_LABEL.get(store.habitat, "station")

    def seed_scenario(sc: dict[str, Any], role: str) -> None:
        subject = store.subject_id
        _calibrate(store, subject)
        store.checks[subject] = []
        for kind, val in sc["seed"].items():
            if kind == "bp":
                store.checks[subject].append(_check(subject, "bp", systolic=val[0], diastolic=val[1]))
            else:
                store.checks[subject].append(_check(subject, kind, float(val)))
        if "stale_onsd" in sc:
            target_tau = sc["stale_onsd"]["tau"]
            hours = -math.log(target_tau) / 0.15
            store.checks[subject].append(_check(subject, "onsd", sc["stale_onsd"]["value"], hours_ago=hours))
        store.ws.update({"mode": "SIMULATED_FALLBACK", "scenario_key": sc["id"],
                         "enmo_g": sc["enmo_g"], "co2_mmhg": sc["co2_mmhg"],
                         "proton_mgy_day": sc["proton_mgy_day"],
                         "water_ml": sc.get("water_ml"), "ared_min": sc.get("ared_min")})
        store.habitat = HABITAT_KEYS[sc["habitat"]][0]
        store.scenario_id = sc["underlying"]
        store.t_s = 0.0
        store.running = True
        store.frames = []
        store.holds.pop(subject, None)
        store.audit.append("scenario.start", role, subject, "SIMULATED",
                           {"scenario_id": sc["id"], "underlying": sc["underlying"]})
        blocked = False
        for t in range(0, int(sc["advance_s"]) + 1):
            store.t_s = float(t)
            frame = frame_at(sc["underlying"], float(t))
            store.frames.append(frame)
            maybe_alert(frame, role)
            blocked = blocked or frame.suppressed
        store.frames = store.frames[-600:]
        if blocked:
            store.audit.append("GATE_2_FALSE_ALARM_BLOCKED", role, subject, "SIMULATED",
                               {"scenario_id": sc["id"]})
        final = store.frames[-1] if store.frames else None
        if final is not None and final.state == "SURGEON_ALERT":
            store.audit.append("SURGEON_ESCALATION", role, subject, final.lane,
                               {"scenario_id": sc["id"]})

    def reevaluate_current(role: str) -> None:
        """Re-run the deterministic gates at the current mission time after a crew exam.
        Replaces the last frame instead of appending a duplicate timestamp."""
        if store.scenario_id is None or not store.frames:
            return
        frame = frame_at(store.scenario_id, store.t_s)
        store.frames[-1] = frame
        maybe_alert(frame, role)
        store.broadcast(frame)
        store.audit.append("exam.reevaluate", role, store.subject_id, frame.lane,
                           {"scenario_id": store.ws.get("scenario_id") or store.scenario_id})

    def latest_tau(kind: str) -> float | None:
        checks = store.checks_for(store.subject_id)
        check = latest_by_kind(checks).get(kind)
        if check is None:
            return None
        age = age_hours(check)
        return tau(age) if age is not None else None

    def active_sensing(organs: list[dict]) -> dict:
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

    def triage(frame: dict | None, organs: list[dict]) -> dict:
        states = {o["status"] for o in organs}
        fstate = frame["state"] if frame else "UNKNOWN"
        gate3 = next((g for g in (frame or {}).get("gates", []) if g["gate"] == 3), None)
        if fstate == "CREW_CHECK" and gate3 and gate3["outcome"] == "HOLD":
            requested = (gate3.get("evidence") or {}).get("requested_exam")
            tier, actions = "CREW", actions_for(REPEAT_MEASUREMENT, REST_AND_RECHECK)
            why = ("Gate 3 held the ground alarm: " + gate3["reason"] +
                   (" Run the guided eye ultrasound tab next." if requested == "ultrasound" else ""))
        elif "ALERT" in states or fstate == "SURGEON_ALERT":
            tier, actions = "SURGEON", actions_for(CONTACT_FLIGHT_SURGEON, REPEAT_MEASUREMENT)
            why = "A demo rule or the deterministic gate raised an alert-level finding."
        elif fstate == "SENSOR_ISSUE":
            tier, actions = "CREW", actions_for(CHECK_SENSOR, REPEAT_MEASUREMENT)
            why = "The sensor window failed the calibrated quality gate."
        elif fstate == "CONTEXT_COMPENSATED":
            tier, actions = "WATCH", actions_for(REST_AND_RECHECK)
            why = "Gate 2 blocked an exercise false alarm; movement explains the rate."
        elif fstate == "CREW_CHECK" or "WATCH" in states or "UNKNOWN" in states:
            tier, actions = "CREW", actions_for(REPEAT_MEASUREMENT, REST_AND_RECHECK)
            why = "A reading is stale, watch-level, or unknown; a crew check is requested first."
        elif fstate == "UNKNOWN":
            tier, actions = "UNKNOWN", actions_for(CHECK_SENSOR, REPEAT_MEASUREMENT)
            why = "No calibrated decision is available."
        else:
            tier, actions = "NOMINAL", actions_for(REPEAT_MEASUREMENT)
            why = "No demo rule or gate raised a finding."
        return {"tier": tier, "why": why, "crew_or_surgeon": "Flight surgeon escalation" if tier == "SURGEON"
                else "Can be handled by crew onboard" if tier in {"CREW", "WATCH", "NOMINAL"} else "Unknown",
                "actions": actions,
                "steps": ["Read the lane/provenance badge before acting.",
                          "Repeat the indicated measurement with the listed crew tool.",
                          "If the finding persists or escalates, contact the flight surgeon."],
                "label": "DEMO triage, not NASA-STD-3001 compliance and not treatment advice"}

    def state_payload() -> dict[str, Any]:
        ws = store.ws
        subject = store.subject_id
        checks = store.checks_for(subject)
        frame = store.frames[-1].model_dump() if store.frames else None
        cal = store.calibration(subject)
        context = {**ws, "hr_bpm": (frame or {}).get("hr_bpm"),
                   "hr_suppressed": (frame or {}).get("suppressed", False)}
        organs = [o.model_dump() for o in organ_readings(checks, context=context)]
        if frame and frame.get("hr_bpm") is not None and cal.calibrated and cal.rest_hr_median is not None and cal.rest_hr_scale:
            z = (frame["hr_bpm"] - cal.rest_hr_median) / cal.rest_hr_scale
            for organ in organs:
                if organ["system"] == "heart":
                    organ["z_score"] = z
                    organ["baseline_note"] = "z_t vs SIMULATED personal resting HR calibration; not a clinical z-score."
        scores = []
        expected = None
        if cal.calibrated and cal.rest_hr_median is not None:
            scores = [s["hr_bpm"] - cal.rest_hr_median for s in rest_calibration_samples()]
            expected = cal.rest_hr_median
            if frame and frame.get("activity_norm") is not None:
                drive = 1.0 - math.exp(-max(0.0, frame["activity_norm"]) / ACTIVITY_SATURATION_SCALE)
                expected = cal.rest_hr_median + HR_RESERVE_BPM * drive + co2_hr_drive(ws.get("co2_mmhg"))
        conf = upper_bound(expected, scores, ws["alpha"])
        history = []
        for f in store.frames[-180:]:
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
        goes_state = goes.load(fetch=False)
        wear = wearable.status()
        mode = ws["mode"]
        banner = REAL_BANNER if mode == "REAL_EMPIRICAL" else SIM_BANNER
        if mode == "REAL_EMPIRICAL":
            telemetry_mode = "REAL_EMPIRICAL" if wear["available"] else "NOT_AVAILABLE"
        else:
            telemetry_mode = "SIMULATED_FALLBACK"
        audit = store.audit.verify()
        entries = [e.model_dump() for e in store.audit.entries()[-50:]]
        key = habitat_key()
        return envelope(
            lane="SIMULATED" if telemetry_mode == "SIMULATED_FALLBACK" else lab.lane,
            provenance=banner,
            habitat=key, habitat_label=HABITAT_KEYS[key][1], habitat_options=[
                {"key": k, "label": v[1]} for k, v in HABITAT_KEYS.items()],
            data_source_mode=mode, telemetry_mode=telemetry_mode, provenance_banner=banner,
            subject_id=subject, scenario_key=ws["scenario_key"], running=store.running, t_s=store.t_s,
            demo_scenarios=[{"id": s["id"], "label": s["label"]} for s in DEMO_SCENARIOS],
            sources={"lab": lab.model_dump(), "goes": goes_state, "wearable": wear},
            organs=organs, frame=frame, history=history,
            gates=(frame or {}).get("gates", []),
            conformal=conf, active_sensing=active_sensing(organs), triage=triage(frame, organs),
            overlays={"enmo_g": ws["enmo_g"], "co2_mmhg": ws["co2_mmhg"],
                      "proton_mgy_day": ws["proton_mgy_day"], "water_ml": ws["water_ml"],
                      "ared_min": ws["ared_min"],
                      "label": "SIMULATED reference channels; ENMO g is a demo display value, "
                               "the gate uses per-person scale-normalised activity"},
            countermeasure_flags={"water_low": None if ws["water_ml"] is None else ws["water_ml"] < 1400,
                                  "ared_low": None if ws["ared_min"] is None else ws["ared_min"] < 20,
                                  "label": "DEMO countermeasure flags, not treatment advice"},
            readiness={**readiness, "freshness_tau_avg": freshness, "badges": badges},
            ml_benchmark=ml_benchmark,
            audit={"verification": audit, "entries": entries,
                   "contract": "HealthAudit.sol reference only — NOT deployed, NOT on-chain",
                   "badge": "ZERO RAW PRIVATE HEALTH DATA ON-CHAIN (local hash chain; no chain exists)"},
        )

    @app.get("/api/state")
    def get_state() -> dict:
        return state_payload()

    @app.post("/api/scenario")
    def post_scenario(payload: dict = Body(default_factory=dict),
                      x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        if "scenario_id" in payload and payload["scenario_id"]:
            sid = payload["scenario_id"]
            if sid not in DEMO_BY_ID:
                raise HTTPException(400, f"unknown demo scenario {sid!r}; choose from {[s['id'] for s in DEMO_SCENARIOS]}")
            seed_scenario(DEMO_BY_ID[sid], role)
        if "habitat" in payload and payload["habitat"]:
            key = payload["habitat"]
            if key not in HABITAT_KEYS:
                raise HTTPException(400, f"habitat must be one of {list(HABITAT_KEYS)}")
            store.habitat = HABITAT_KEYS[key][0]
        if "mode" in payload and payload["mode"]:
            mode = payload["mode"]
            if mode not in {"REAL_EMPIRICAL", "SIMULATED_FALLBACK"}:
                raise HTTPException(400, "mode must be REAL_EMPIRICAL or SIMULATED_FALLBACK")
            store.ws["mode"] = mode
            if mode == "REAL_EMPIRICAL":
                store.running = False
                store.frames = []
                store.scenario_id = None
                store.ws["scenario_key"] = None
                store.ws.update({"enmo_g": None, "co2_mmhg": None, "proton_mgy_day": None,
                                 "water_ml": None, "ared_min": None})
            store.audit.append("session.change", role, store.subject_id, "NONE", {"mode": mode})
        return state_payload()

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
        subject = _exam_subject(store, payload)
        store.checks.setdefault(subject, []).append(
            ManualCheck(subject_id=subject, kind="pvt", value=median, unit="ms",
                        recorded_at=now(), source="15 s reaction test (crew, demo)"))
        store.audit.append("pvt.result", role, subject, "INJECTED", {"kind": "pvt", "n": len(values)})
        reevaluate_current(role)
        return state_payload()

    @app.post("/api/exams/ultrasound")
    def exam_ultrasound(payload: dict = Body(...), x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        subject = _exam_subject(store, payload)
        sample = payload.get("sample")
        if sample in {"nominal", "sans"}:
            mm = 4.6 if sample == "nominal" else 6.1
            px_per_mm = 20.0
            x1, y1, x2, y2 = 100.0, 100.0, 100.0 + mm * px_per_mm, 100.0
            source = f"SAMPLE B-mode frame ({sample}); known ONSD, not a patient scan"
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
        store.checks.setdefault(subject, []).append(
            ManualCheck(subject_id=subject, kind="onsd", value=mm, unit="mm",
                        recorded_at=now(), source=source))
        store.audit.append("manual.entry", role, subject, "INJECTED", {"kind": "onsd"})
        reevaluate_current(role)
        state = state_payload()
        state["caliper"] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "px_per_mm": px_per_mm,
                            "onsd_mm": mm, "retrobulbar_mm": 3.0,
                            "note": "measurement line placed 3 mm behind the globe; manual caliper, demo only"}
        return state

    @app.post("/api/exams/vitals")
    def exam_vitals(payload: dict = Body(...), x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        subject = _exam_subject(store, payload)
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
            store.checks.setdefault(subject, []).append(
                ManualCheck(subject_id=subject, kind="bp", systolic=parsed["bp_sys"],
                            diastolic=parsed["bp_dia"], unit="mmHg", recorded_at=now(),
                            source="keyboard crew vitals (demo, unverified)"))
            kinds.append("bp")
        mapping = {"glucose_mgdl": ("glucose", "mg/dL"), "temp_c": ("temperature", "degC"),
                   "sleep_hrs": ("sleep", "h"), "mood_score": ("mood", "1-10")}
        for field, (kind, unit) in mapping.items():
            if field in parsed:
                store.checks.setdefault(subject, []).append(
                    ManualCheck(subject_id=subject, kind=kind, value=parsed[field],  # type: ignore[arg-type]
                                unit=unit, recorded_at=now(), source="keyboard crew vitals (demo, unverified)"))
                kinds.append(kind)
        if "water_ml" in parsed:
            store.ws["water_ml"] = parsed["water_ml"]
        if "ared_min" in parsed:
            store.ws["ared_min"] = parsed["ared_min"]
        if not kinds and "water_ml" not in parsed and "ared_min" not in parsed:
            raise HTTPException(400, "no vitals fields supplied")
        store.audit.append("manual.entry", role, subject, "INJECTED", {"kinds": kinds})
        reevaluate_current(role)
        return state_payload()

    @app.post("/api/goes/refresh")
    def refresh_goes(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("ops", "researcher", "flight-surgeon"))
        return envelope(lane="NONE", provenance="NOAA GOES proton lane", goes=goes.load(fetch=True))

    @app.get("/api/ml/benchmark")
    def get_ml_benchmark() -> dict:
        return envelope(lane="RECORDED-NON-ASTRONAUT", provenance=ml_benchmark["provenance"],
                        benchmark=ml_benchmark)
