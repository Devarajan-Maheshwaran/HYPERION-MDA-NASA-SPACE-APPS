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

    # SPA is served.
    try:
        with urllib.request.urlopen(base + "/", timeout=10) as response:
            html = response.read().decode()
        check("SPA index served", "<div id=\"root\">" in html)
        check("SPA references built assets", "/assets/" in html)
    except Exception as exc:  # noqa: BLE001
        check("SPA index served", False, f"{type(exc).__name__}: {exc}")

    call(base, "/api/stream/stop", method="POST")

    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
    if FAIL:
        for name in FAIL:
            print(f"  FAILED: {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
