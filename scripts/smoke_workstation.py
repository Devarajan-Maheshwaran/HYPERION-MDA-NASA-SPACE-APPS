"""End-to-end smoke test against a RUNNING server over real HTTP.

Usage:
    python scripts/smoke_workstation.py [--base http://127.0.0.1:8000]

Boots nothing: start the API first. Exercises the SPA, the API contract, an SSE frame,
the exercise false-alarm block, the non-rate bypass, an alert, an acknowledgement and the
audit chain. Standard library only. Exits non-zero on the first failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import time
import urllib.request

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def call(base: str, path: str, role: str = "ops", method: str = "GET",
         payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "X-Role": role})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if body.startswith("{") else {"raw": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    print(f"=== HYPERION-MDA workstation smoke test against {base} ===\n")

    status, health = call(base, "/api/health")
    check("health responds 200", status == 200, str(status))
    check("disclaimer present", "Not a medical device" in health.get("disclaimer", ""))
    check("four allowed actions", len(health.get("allowed_actions", [])) == 4)

    status, registry = call(base, "/api/registry")
    check("registry has 49 channels", registry.get("total") == 49, str(registry.get("total")))

    status, _ = call(base, "/api/session", method="POST", payload={"subject_id": "demo-crew-1"})
    check("session switch works", status == 200)

    # Uncalibrated: gates must be UNKNOWN, never a pass.
    call(base, "/api/calibration/demo-crew-1", method="DELETE")
    call(base, "/api/scenarios/rest-nominal/start", method="POST")
    _, step = call(base, "/api/stream/step?dt_s=1", method="POST")
    frame = step["frame"]
    check("uncalibrated state is UNKNOWN", frame["state"] == "UNKNOWN", frame["state"])
    check("uncalibrated gate 1 is UNKNOWN", frame["gates"][0]["outcome"] == "UNKNOWN")

    status, cal = call(base, "/api/calibration/demo-crew-1", method="POST")
    check("ops can calibrate", status == 200 and cal["calibration"]["calibrated"])
    check("crew cannot calibrate", call(base, "/api/calibration/demo-crew-1", role="crew",
                                       method="POST")[0] == 403)

    # Exercise false alarm: Gate 2 must block.
    call(base, "/api/scenarios/exercise-false-alarm/start", method="POST")
    blocked = False
    for _ in range(60):
        _, step = call(base, "/api/stream/step?dt_s=1", method="POST")
        if step["frame"]["suppressed"]:
            blocked = True
            break
    check("exercise false alarm is blocked by gate 2", blocked,
          f"state={step['frame']['state']} hr={step['frame']['hr_bpm']:.1f}")
    check("blocked frame is CONTEXT_COMPENSATED", step["frame"]["state"] == "CONTEXT_COMPENSATED")

    # The same exercise with a non-rate finding must NOT be suppressed.
    call(base, "/api/scenarios/exercise-with-arrhythmia/start", method="POST")
    escalated = False
    for _ in range(60):
        _, step = call(base, "/api/stream/step?dt_s=1", method="POST")
        if step["frame"]["state"] == "SURGEON_ALERT":
            escalated = True
            break
    check("non-rate finding escalates despite exercise", escalated)
    check("non-rate frame is not suppressed", not step["frame"]["suppressed"])

    # Alert + acknowledgement.
    _, alerts = call(base, "/api/alerts", role="flight-surgeon")
    check("alert was raised", len(alerts["alerts"]) > 0, str(len(alerts["alerts"])))
    if alerts["alerts"]:
        aid = alerts["alerts"][0]["alert_id"]
        check("crew cannot acknowledge",
              call(base, f"/api/alerts/{aid}/ack", role="crew", method="POST", payload={})[0] == 403)
        status, acked = call(base, f"/api/alerts/{aid}/ack", role="flight-surgeon", method="POST",
                             payload={"note": "smoke test"})
        check("surgeon can acknowledge", status == 200 and acked["alert"]["acknowledged_by"] == "flight-surgeon")

    # Manual check + organs.
    status, _ = call(base, "/api/manual", role="crew", method="POST",
                     payload={"subject_id": "demo-crew-1", "kind": "glucose", "value": 131,
                              "unit": "mg/dL"})
    check("crew can log a manual check", status == 200)
    _, organs = call(base, "/api/organs", role="crew")
    check("six organ systems returned", len(organs["organs"]) == 6)
    check("missing checks are NOT_AVAILABLE, never nominal",
          all(o["status"] != "NOMINAL" for o in organs["organs"] if o["value"] is None))
    check("organ thresholds labelled DEMO",
          all("DEMO THRESHOLD" in o["threshold_label"] for o in organs["organs"]))
    allowed = set(health["allowed_actions"])
    check("organ actions are on the allow-list",
          all(o["action"] in allowed for o in organs["organs"]))

    # PVT.
    status, pvt = call(base, "/api/pvt", role="crew", method="POST",
                       payload={"subject_id": "demo-crew-1", "reaction_ms": [290, 380, 410]})
    check("PVT result accepted", status == 200 and pvt["lapses_over_350ms"] == 2)

    # Audit chain.
    _, verify = call(base, "/api/audit/verify")
    check("audit chain verifies", verify["ok"], f"{verify['entries']} entries")

    # SSE: read one real frame from the event stream.
    call(base, "/api/scenarios/rest-nominal/start", method="POST")
    got_frame = False
    try:
        request = urllib.request.Request(base + "/api/stream/events")
        with urllib.request.urlopen(request, timeout=10) as stream:
            # Trigger a frame from another connection while the stream is open.
            import threading
            threading.Timer(0.5, lambda: call(base, "/api/stream/step?dt_s=1", method="POST")).start()
            # The `hello` event also carries t_s, so match on the frame's own fields.
            for _ in range(40):
                line = stream.readline().decode(errors="replace").strip()
                if line.startswith("data:") and '"gates"' in line:
                    payload = json.loads(line[5:].strip())
                    got_frame = "gates" in payload and "state" in payload
                    break
    except Exception as exc:  # noqa: BLE001 - report honestly
        check("SSE stream delivers a frame", False, f"{type(exc).__name__}: {exc}")
    else:
        check("SSE stream delivers a frame", got_frame)

    # Unified live workstation: dual-mode state, five scenarios, three exams.
    status, state = call(base, "/api/state")
    check("GET /api/state responds 200", status == 200)
    check("state carries provenance banner", bool(state.get("provenance_banner")))
    check("state has six organs", len(state.get("organs", [])) == 6)
    check("state labels ML gaps honestly", bool(state.get("ml_benchmark", {}).get("not_implemented")))

    status, nominal = call(base, "/api/scenario", role="crew", method="POST",
                           payload={"scenario_id": "nominal-orbital"})
    check("nominal scenario accepted", status == 200 and nominal["data_source_mode"] == "SIMULATED_FALLBACK")
    check("nominal gates pass", all(g["outcome"] == "PASS" for g in nominal["gates"]))

    status, exercise = call(base, "/api/scenario", role="crew", method="POST",
                            payload={"scenario_id": "eva-ared-exercise"})
    g2 = next(g for g in exercise["gates"] if g["gate"] == 2)
    check("exercise scenario blocks false alarm", status == 200 and g2["outcome"] == "BLOCK")

    status, sans = call(base, "/api/scenario", role="crew", method="POST",
                        payload={"scenario_id": "sans-stale-eye"})
    g3 = next(g for g in sans["gates"] if g["gate"] == 3)
    check("SANS scenario holds for eye ultrasound", status == 200 and g3["outcome"] == "HOLD"
          and g3["evidence"].get("requested_exam") == "ultrasound")

    status, spe = call(base, "/api/scenario", role="crew", method="POST",
                       payload={"scenario_id": "spe-radiation"})
    check("SPE scenario escalates", status == 200 and spe["triage"]["tier"] == "SURGEON")
    check("cosine-median catches simulated silo-2 bit-flip",
          spe["ml_benchmark"]["cosine_median_demo"]["caught"])

    status, drift = call(base, "/api/scenario", role="crew", method="POST",
                         payload={"scenario_id": "glycemic-circadian"})
    statuses = {o["system"]: o["status"] for o in drift["organs"]}
    check("glycemic/sleep drift raises metabolic + brain", status == 200
          and statuses["metabolic"] == "WATCH" and statuses["brain"] == "ALERT")

    status, pvt = call(base, "/api/exams/pvt", role="crew", method="POST",
                       payload={"reaction_ms": [288, 305, 340, 310, 295]})
    check("POST /api/exams/pvt responds 200", status == 200)
    status, us = call(base, "/api/exams/ultrasound", role="crew", method="POST",
                      payload={"sample": "sans"})
    check("POST /api/exams/ultrasound responds 200", status == 200 and abs(us["caliper"]["onsd_mm"] - 6.1) < 1e-6)
    status, vitals = call(base, "/api/exams/vitals", role="crew", method="POST",
                          payload={"bp_sys": 122, "bp_dia": 78, "glucose_mgdl": 92, "temp_c": 36.8,
                                   "sleep_hrs": 7.2, "water_ml": 1800, "ared_min": 30, "mood_score": 7})
    check("POST /api/exams/vitals responds 200", status == 200)
    check("exam audit has no raw PII payload", all("value" not in e.get("detail", {}) for e in vitals["audit"]["entries"]))

    status, real = call(base, "/api/scenario", method="POST", payload={"mode": "REAL_EMPIRICAL"})
    check("real mode does not invent telemetry", status == 200 and real["frame"] is None
          and real["telemetry_mode"] in {"NOT_AVAILABLE", "REAL_EMPIRICAL"})

    # SPA is served.
    try:
        with urllib.request.urlopen(base + "/", timeout=10) as response:
            html = response.read().decode()
        check("SPA index served", "<div id=\"root\">" in html)
        # Vite dev serves the TS entrypoint; the production server serves hashed assets.
        if "/src/main.tsx" in html:
            check("SPA entrypoint served (vite dev mode)", "@vite/client" in html)
        else:
            check("SPA references built assets", "/assets/" in html)
    except Exception as exc:  # noqa: BLE001
        check("SPA index served", False, f"{type(exc).__name__}: {exc}")

    # ---- live cockpit: clock, lifecycle, comms, reset, benchmark (P0/P1) ----
    # The section above left the case in REAL_EMPIRICAL mode; reset back to a live case.
    call(base, "/api/case/reset", method="POST", payload={})
    status, boot = call(base, "/api/state")
    check("cockpit boots into a labelled live case",
          status == 200 and boot.get("scenario_key") == "nominal-orbital"
          and boot.get("frame") is not None)
    clock = boot.get("clock", {})
    check("clock advertises 1 Hz and the mission tau basis",
          clock.get("hz") == 1.0 and clock.get("mission_seconds_per_demo_hour") == 60.0
          and "mission" in str(clock.get("tau_basis", "")).lower())
    check("lifecycle banner is present and demo-labelled",
          boot.get("lifecycle", {}).get("stage") == "S0_NOMINAL"
          and "demo" in boot["lifecycle"]["routing_label"].lower())

    call(base, "/api/transport", method="POST", payload={"action": "pause"})
    _, paused = call(base, "/api/state")
    status, stepped = call(base, "/api/transport", method="POST",
                           payload={"action": "step", "dt_s": 10})
    check("transport step advances mission time by exactly 10 s",
          status == 200 and abs(stepped["t_s"] - paused["t_s"] - 10.0) < 1e-6)

    stages = {}
    for scenario_id in ("nominal-orbital", "eva-ared-exercise", "sans-stale-eye",
                        "spe-radiation", "glycemic-circadian"):
        _, sc = call(base, "/api/scenario", method="POST", payload={"scenario_id": scenario_id})
        stages[scenario_id] = sc.get("lifecycle", {}).get("stage")
    check("five demo lanes land on S0/S1/S2/S4/S3",
          stages == {"nominal-orbital": "S0_NOMINAL", "eva-ared-exercise": "S1_EXERTION_COMPENSATED",
                     "sans-stale-eye": "S2_ACTIVE_SENSING_HOLD", "spe-radiation": "S4_SURGEON_ESCALATED",
                     "glycemic-circadian": "S3_CREW_COUNTERMEASURE"}, str(stages))

    call(base, "/api/scenario", method="POST", payload={"scenario_id": "sans-stale-eye"})
    _, resolved = call(base, "/api/exams/ultrasound", method="POST", role="crew", payload={"sample": "nominal"})
    check("normal ONSD resolves the S2 hold",
          resolved["lifecycle"]["stage"] == "S3_CREW_COUNTERMEASURE"
          and not resolved["lifecycle"]["action_required"])
    call(base, "/api/scenario", method="POST", payload={"scenario_id": "sans-stale-eye"})
    _, escalated = call(base, "/api/exams/ultrasound", method="POST", role="crew", payload={"sample": "sans"})
    check("elevated ONSD escalates to S4 and queues one SBAR packet",
          escalated["lifecycle"]["stage"] == "S4_SURGEON_ESCALATED"
          and len(escalated["comms"]["packets"]) == 1)

    packet_id = escalated["comms"]["packets"][0]["packet_id"]
    status, _ = call(base, "/api/surgeon/acknowledge", method="POST", role="crew",
                     payload={"packet_id": packet_id, "directive": "x"})
    check("crew cannot acknowledge a surgeon packet", status == 403)
    call(base, "/api/scenario", method="POST", payload={"habitat": "station"})
    call(base, "/api/transport", method="POST", payload={"action": "step", "dt_s": 1})
    time.sleep(0.4)
    call(base, "/api/transport", method="POST", payload={"action": "step", "dt_s": 1})
    status, acked = call(base, "/api/surgeon/acknowledge", method="POST", role="flight-surgeon",
                         payload={"packet_id": packet_id, "directive": "Recheck ONSD in 30 minutes."})
    check("flight surgeon acknowledgement closes the loop",
          status == 200 and acked["lifecycle"]["stage"] == "S4_SURGEON_ACKNOWLEDGED"
          and len(acked["receipt"]["sha256"]) == 64)

    _, before_reset = call(base, "/api/state")
    status, reset = call(base, "/api/case/reset", method="POST", payload={})
    check("case reset returns to S0 and preserves the audit chain",
          status == 200 and reset["lifecycle"]["stage"] == "S0_NOMINAL"
          and not reset["comms"]["packets"] and reset["audit"]["verification"]["ok"]
          and reset["audit"]["verification"]["entries"] >= before_reset["audit"]["verification"]["entries"])

    _, replayed = call(base, "/api/scenario", method="POST", payload={"replay_participant": "s1"})
    check("recorded replay is labelled non-astronaut",
          replayed["telemetry_mode"] == "RECORDED_REPLAY"
          and "NON-ASTRONAUT" in replayed["provenance_banner"]
          and replayed["replay"]["n_windows"] == 3332)

    goes_lane = replayed["sources"]["goes"]
    check("GOES lane is pfu with a not-dose note",
          goes_lane.get("unit") == "pfu" and "not absorbed tissue dose" in goes_lane.get("dose_note", "").lower())

    status, bench = call(base, "/api/benchmark/fl-dp")
    artifact = bench.get("benchmark", {})
    check("FL/DP benchmark served from the committed artifact",
          status == 200 and artifact.get("available") and len(artifact.get("sha256", "")) == 64)
    if artifact.get("available"):
        results = artifact["results"]
        regimes = {row["regime"] for row in results["accuracy"]["table"]}
        check("benchmark measures all four regimes plus the mean baseline",
              regimes == {"mean_baseline", "local_only", "centralized", "fedavg", "dp_sgd_fl"})
        check("benchmark declares a window-level (not participant-level) threat model",
              results["threat_model"]["level"] == "WINDOW"
              and any("PARTICIPANT-LEVEL" in item for item in results["threat_model"]["not_covered"]))
        check("benchmark cross-check reproduces the frozen M6 A0",
              results["accuracy"]["frozen_m6_cross_check"]["matches"] is True)

    call(base, "/api/case/reset", method="POST", payload={})
    call(base, "/api/stream/stop", method="POST")

    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
    if FAIL:
        for name in FAIL:
            print(f"  FAILED: {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
