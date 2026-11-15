"""FastAPI workstation API. Composition layer above the lanes; no lane imports this.

Run:  uvicorn api.main:app --host 0.0.0.0 --port 8000
Not a medical device. Demo thresholds, not clinically validated.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, lanes
from .actions import ALLOWED_ACTIONS
from .audit import AuditLog
from .gates import (HARD_HR_CEILING_BPM, MAX_SUPPRESSION_HOLD_S, GateInput, HoldClock,
                    evaluate, kurtosis, normalise_activity, slew_rate)
from .models import (DISCLAIMER, Alert, Calibration, Frame, ManualCheck, SqReading,
                     Subject)
from .organs import (VALIDITY_HOURS, any_stale, min_tau, organ_readings,
                     readiness_streak)
from .scenarios import BY_ID, catalogue, rest_calibration_samples, sample

REPO_ROOT = Path(__file__).resolve().parents[1]
ROLE_ORDER = ("crew", "flight-surgeon", "ops", "researcher")
HABITATS = ("Space Station (0g)", "Transit Ship", "Lunar Base (0.16g)", "Rover")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _envelope(lane: str = "NONE", provenance: str = "", **extra: Any) -> dict[str, Any]:
    return {"lane": lane, "provenance": provenance, "generated_at": _now(),
            "disclaimer": DISCLAIMER, **extra}


class Store:
    """Process-local demo state. Not a database; restarting clears it."""

    def __init__(self, audit_path: Path | None = None) -> None:
        self.role = "crew"
        self.habitat = HABITATS[0]
        self.subject_id = "demo-crew-1"
        self.calibrations: dict[str, Calibration] = {}
        self.checks: dict[str, list[ManualCheck]] = {}
        self.alerts: list[Alert] = []
        self.audit = AuditLog(audit_path)
        self.holds: dict[str, HoldClock] = {}
        self.scenario_id: str | None = None
        self.t_s = 0.0
        self.running = False
        self.frames: list[Frame] = []
        self.subscribers: list[asyncio.Queue] = []
        self.subjects = {
            "demo-crew-1": "Demo crew member 1 (SIMULATED)",
            "demo-crew-2": "Demo crew member 2 (SIMULATED)",
            "demo-crew-3": "Demo crew member 3 (uncalibrated)",
        }

    def calibration(self, subject_id: str) -> Calibration:
        return self.calibrations.get(subject_id, Calibration(subject_id=subject_id))

    def hold(self, subject_id: str) -> HoldClock:
        return self.holds.setdefault(subject_id, HoldClock())

    def checks_for(self, subject_id: str) -> list[ManualCheck]:
        return self.checks.get(subject_id, [])

    def broadcast(self, frame: Frame) -> None:
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                pass


def create_app(audit_path: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="HYPERION-MDA Workstation API",
        version=__version__,
        description=("Composition layer above the NASA lab, SIMULATED and RECORDED lanes. "
                     + DISCLAIMER),
    )
    # The Vite dev server proxies /api, so same-origin in production. Permissive here
    # because this is a local demo with demo-grade auth (docs/SAFETY_ISSUES.md S10).
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"],
    )
    store = Store(audit_path)
    app.state.store = store

    def role_of(x_role: str | None) -> str:
        role = (x_role or store.role).strip()
        return role if role in ROLE_ORDER else "crew"

    def require(x_role: str | None, allowed: tuple[str, ...]) -> str:
        role = role_of(x_role)
        if role not in allowed:
            raise HTTPException(status_code=403,
                                detail=f"Role {role!r} may not perform this action. "
                                       f"Allowed: {', '.join(allowed)}. (Demo-grade auth.)")
        return role

    # ---------------- health / session ----------------
    @app.get("/api/health")
    def health() -> dict:
        return _envelope(version=__version__, status="ok",
                         lanes={l.lane: l.available for l in lanes.lanes()},
                         allowed_actions=list(ALLOWED_ACTIONS),
                         hard_hr_ceiling_bpm=HARD_HR_CEILING_BPM,
                         max_suppression_hold_s=MAX_SUPPRESSION_HOLD_S,
                         auth="demo-grade role header, not an identity")

    @app.get("/api/session")
    def session(x_role: str | None = Header(default=None)) -> dict:
        subject = store.subject_id
        return _envelope(lane="SIMULATED", provenance="demo session",
                         role=role_of(x_role), subject_id=subject, habitat=store.habitat,
                         subjects=[Subject(subject_id=k, label=v, lane="SIMULATED",
                                           calibration=store.calibration(k)).model_dump()
                                   for k, v in store.subjects.items()],
                         running=store.running, scenario_id=store.scenario_id, t_s=store.t_s,
                         habitats=list(HABITATS), roles=list(ROLE_ORDER))

    @app.post("/api/session")
    def set_session(payload: dict = Body(default_factory=dict),
                    x_role: str | None = Header(default=None)) -> dict:
        role = role_of(x_role)
        if "role" in payload:
            if payload["role"] not in ROLE_ORDER:
                raise HTTPException(400, f"role must be one of {ROLE_ORDER}")
            store.role = payload["role"]
            role = store.role
        if "subject_id" in payload:
            if payload["subject_id"] not in store.subjects:
                raise HTTPException(400, "unknown subject_id")
            store.subject_id = payload["subject_id"]
        if "habitat" in payload:
            if payload["habitat"] not in HABITATS:
                raise HTTPException(400, f"habitat must be one of {HABITATS}")
            store.habitat = payload["habitat"]
        store.audit.append("session.change", role, store.subject_id, "SIMULATED",
                           {"habitat": store.habitat})
        return session(x_role=role)

    @app.get("/api/subjects")
    def subjects() -> dict:
        return _envelope(lane="SIMULATED", provenance="demo subjects",
                         subjects=[Subject(subject_id=k, label=v, lane="SIMULATED",
                                           calibration=store.calibration(k)).model_dump()
                                   for k, v in store.subjects.items()])

    # ---------------- lanes / registry ----------------
    @app.get("/api/lanes")
    def get_lanes() -> dict:
        return _envelope(lanes=[l.model_dump() for l in lanes.lanes()])

    @app.get("/api/registry")
    def get_registry() -> dict:
        return _envelope(**lanes.registry_summary(), channels=lanes.registry_channels(),
                         provenance="src/hyperion_mda/signal_registry.py")

    @app.get("/api/lab/osd575")
    def get_lab(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("flight-surgeon", "researcher", "ops"))
        data = lanes.lab_rows()
        return _envelope(**{**data, "lane": "LAB DATA",
                            "provenance": data.get("provenance", "")})

    @app.get("/api/research/m6")
    def get_m6(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("researcher", "flight-surgeon", "ops"))
        data = lanes.m6_results()
        return _envelope(**{**data, "lane": data.get("lane", "RECORDED-NON-ASTRONAUT"),
                            "provenance": data.get("provenance", "")})

    # ---------------- calibration ----------------
    @app.post("/api/calibration/{subject_id}")
    def calibrate(subject_id: str, x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("ops",))
        if subject_id not in store.subjects:
            raise HTTPException(400, "unknown subject_id")
        samples = rest_calibration_samples()
        hrs = [s["hr_bpm"] for s in samples]
        mags = [s["magnitude"] for s in samples]
        kurts = [k for k in (kurtosis(s["window"]) for s in samples) if k is not None]
        slews = [v for v in (slew_rate(s["window"], 25.0) for s in samples) if v is not None]
        hr_med = statistics.median(hrs)
        hr_scale = statistics.pstdev(hrs) or 1.0
        act_med = statistics.median(mags)
        act_scale = statistics.pstdev(mags) or 0.01
        residuals = [abs(h - hr_med) for h in hrs]
        q95 = sorted(residuals)[max(0, int(0.95 * len(residuals)) - 1)]
        cal = Calibration(
            subject_id=subject_id, calibrated=True, n_windows=len(samples),
            source="SIMULATED resting window (api/scenarios.py rest-nominal)", lane="SIMULATED",
            rest_hr_median=hr_med, rest_hr_scale=hr_scale,
            rest_activity_median=act_med, rest_activity_scale=act_scale,
            residual_q95=q95,
            kurtosis_low=min(kurts) * 0.8 if kurts else None,
            kurtosis_high=max(kurts) * 1.25 if kurts else None,
            slew_high=max(slews) * 1.5 if slews else None,
            created_at=_now(),
            note=("DEMO calibration from SIMULATED data. Not a clinical calibration. "
                  "Activity is per-person scale-normalised, not ENMO in g."),
        )
        store.calibrations[subject_id] = cal
        store.holds.pop(subject_id, None)
        store.audit.append("calibration.create", role, subject_id, "SIMULATED",
                           {"n_windows": cal.n_windows, "rest_hr_median": hr_med})
        return _envelope(lane="SIMULATED", provenance=cal.source, calibration=cal.model_dump())

    @app.delete("/api/calibration/{subject_id}")
    def uncalibrate(subject_id: str, x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("ops",))
        store.calibrations.pop(subject_id, None)
        store.holds.pop(subject_id, None)
        store.audit.append("calibration.delete", role, subject_id, "NONE", {})
        return _envelope(calibration=Calibration(subject_id=subject_id).model_dump())

    # ---------------- manual checks / organs ----------------
    @app.post("/api/manual")
    def post_manual(check: ManualCheck, x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        if check.subject_id not in store.subjects:
            raise HTTPException(400, "unknown subject_id")
        if not check.recorded_at:
            check.recorded_at = _now()
        if check.kind == "bp" and (check.systolic is None or check.diastolic is None):
            raise HTTPException(400, "bp requires systolic and diastolic")
        if check.kind != "bp" and check.value is None:
            raise HTTPException(400, f"{check.kind} requires value")
        store.checks.setdefault(check.subject_id, []).append(check)
        store.audit.append("manual.entry", role, check.subject_id, check.lane,
                           {"kind": check.kind})
        return _envelope(lane=check.lane, provenance=check.source, check=check.model_dump(),
                         readiness=readiness_streak(store.checks_for(check.subject_id)))

    @app.get("/api/manual/{subject_id}")
    def get_manual(subject_id: str, x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("crew", "flight-surgeon", "ops"))
        checks = store.checks_for(subject_id)
        return _envelope(lane="INJECTED", provenance="crew entry (demo-grade, unverified)",
                         checks=[c.model_dump() for c in checks],
                         validity_hours=VALIDITY_HOURS,
                         readiness=readiness_streak(checks))

    @app.post("/api/pvt")
    def post_pvt(payload: dict = Body(...), x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        subject_id = payload.get("subject_id", store.subject_id)
        times = payload.get("reaction_ms") or []
        if not isinstance(times, list) or not times:
            raise HTTPException(400, "reaction_ms must be a non-empty list")
        try:
            values = [float(v) for v in times]
        except (TypeError, ValueError):
            raise HTTPException(400, "reaction_ms must be numeric")
        if any(v <= 0 or v > 10000 for v in values):
            raise HTTPException(400, "reaction_ms out of plausible range (0, 10000]")
        median = statistics.median(values)
        check = ManualCheck(subject_id=subject_id, kind="pvt", value=median, unit="ms",
                            recorded_at=_now(), source="15 s reaction test (crew, demo)")
        store.checks.setdefault(subject_id, []).append(check)
        store.audit.append("pvt.result", role, subject_id, "INJECTED",
                           {"median_ms": median, "n": len(values)})
        return _envelope(lane="INJECTED", provenance=check.source, median_ms=median,
                         n=len(values), lapses_over_350ms=sum(v > 350 for v in values),
                         check=check.model_dump(),
                         note="Demo reaction test. Not a validated cognitive assessment.")

    @app.get("/api/organs")
    def get_organs(subject_id: str | None = None,
                   x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("crew", "flight-surgeon", "ops"))
        sid = subject_id or store.subject_id
        checks = store.checks_for(sid)
        return _envelope(lane="INJECTED", provenance="crew entry (demo-grade, unverified)",
                         subject_id=sid, organs=[o.model_dump() for o in organ_readings(checks)],
                         readiness=readiness_streak(checks),
                         threshold_notice=("Every threshold below is a DEMO value quoted from the "
                                           "concept deck. Not NASA-STD-3001 compliance."))

    # ---------------- scenarios / stream ----------------
    @app.get("/api/scenarios")
    def get_scenarios() -> dict:
        return _envelope(lane="SIMULATED", provenance="api/scenarios.py",
                         scenarios=[s.model_dump() for s in catalogue()])

    def _frame_at(scenario_id: str, t_s: float) -> Frame:
        raw = sample(scenario_id, t_s)
        cal = store.calibration(store.subject_id)
        activity = normalise_activity(raw["magnitude"], cal)
        sqi = SqReading(kurtosis=kurtosis(raw["window"]),
                        slew=slew_rate(raw["window"], 25.0), calibrated=cal.calibrated)
        checks = store.checks_for(store.subject_id)
        stale = raw["stale_manual"] or any_stale(checks)
        tau_min = 0.1 if raw["stale_manual"] else min_tau(checks)
        inp = GateInput(t_s=t_s, hr_bpm=raw["hr_bpm"], activity_norm=activity, sqi=sqi,
                        non_rate_flags=raw["non_rate_flags"], stale_manual=stale,
                        min_tau=tau_min, hr_status="OK")
        frame = evaluate(inp, cal, store.hold(store.subject_id))
        frame.lane = raw["lane"]
        frame.subject_id = store.subject_id
        frame.habitat = store.habitat  # type: ignore[assignment]
        frame.scenario_id = scenario_id
        return frame

    def _maybe_alert(frame: Frame, role: str) -> Alert | None:
        if frame.state not in {"SURGEON_ALERT", "CREW_CHECK"}:
            return None
        severity = "ALERT" if frame.state == "SURGEON_ALERT" else "HOLD"
        open_same = next((a for a in store.alerts
                          if a.subject_id == frame.subject_id and a.state == frame.state
                          and a.acknowledged_at is None), None)
        if open_same is not None:
            return open_same
        alert = Alert(alert_id=uuid.uuid4().hex[:12], subject_id=frame.subject_id,
                      created_at=_now(), lane=frame.lane, state=frame.state, severity=severity,
                      reason=(frame.suppression_reason or frame.gates[-1].reason
                              if frame.gates else frame.state),
                      actions=frame.actions, non_rate_flags=frame.non_rate_flags)
        store.alerts.append(alert)
        store.audit.append("alert.raise", role, frame.subject_id, frame.lane,
                           {"alert_id": alert.alert_id, "state": frame.state,
                            "severity": severity, "non_rate_flags": frame.non_rate_flags})
        return alert

    @app.post("/api/scenarios/{scenario_id}/start")
    def start(scenario_id: str, x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        if scenario_id not in BY_ID:
            raise HTTPException(404, f"unknown scenario {scenario_id!r}")
        store.scenario_id = scenario_id
        store.t_s = 0.0
        store.running = True
        store.frames = []
        store.holds.pop(store.subject_id, None)
        if scenario_id == "uncalibrated":
            store.calibrations.pop(store.subject_id, None)
        store.audit.append("scenario.start", role, store.subject_id,
                           BY_ID[scenario_id].info.lane, {"scenario_id": scenario_id})
        frame = _frame_at(scenario_id, 0.0)
        store.frames.append(frame)
        return _envelope(lane=frame.lane, provenance="api/scenarios.py",
                         scenario=BY_ID[scenario_id].info.model_dump(), frame=frame.model_dump())

    @app.post("/api/stream/stop")
    def stop(x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        store.running = False
        store.audit.append("scenario.stop", role, store.subject_id, "NONE",
                           {"scenario_id": store.scenario_id, "t_s": store.t_s})
        return _envelope(running=False, t_s=store.t_s)

    @app.post("/api/stream/step")
    def step(dt_s: float = 1.0, x_role: str | None = Header(default=None)) -> dict:
        """Advance one frame deterministically. Used by tests and by the SSE loop."""
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        if store.scenario_id is None:
            raise HTTPException(409, "no scenario started")
        if dt_s <= 0 or dt_s > 60:
            raise HTTPException(400, "dt_s must be in (0, 60]")
        store.t_s += dt_s
        frame = _frame_at(store.scenario_id, store.t_s)
        store.frames.append(frame)
        store.frames = store.frames[-600:]
        alert = _maybe_alert(frame, role)
        store.broadcast(frame)
        return _envelope(lane=frame.lane, provenance="api/scenarios.py",
                         frame=frame.model_dump(),
                         alert=alert.model_dump() if alert else None)

    @app.get("/api/stream/state")
    def stream_state() -> dict:
        latest = store.frames[-1].model_dump() if store.frames else None
        return _envelope(lane=store.frames[-1].lane if store.frames else "NONE",
                         running=store.running, t_s=store.t_s, scenario_id=store.scenario_id,
                         frame=latest, history=[f.model_dump() for f in store.frames[-180:]])

    @app.get("/api/stream/events")
    async def events(request: Request) -> StreamingResponse:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        store.subscribers.append(queue)

        async def gen():
            try:
                yield f"event: hello\ndata: {json.dumps({'t_s': store.t_s})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        frame = await asyncio.wait_for(queue.get(), timeout=1.0)
                        yield f"event: frame\ndata: {frame.model_dump_json()}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
            finally:
                if queue in store.subscribers:
                    store.subscribers.remove(queue)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    # ---------------- alerts / audit ----------------
    @app.get("/api/alerts")
    def get_alerts(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("flight-surgeon", "ops", "crew"))
        return _envelope(alerts=[a.model_dump() for a in store.alerts])

    @app.post("/api/alerts/{alert_id}/ack")
    def ack(alert_id: str, payload: dict = Body(default_factory=dict),
            x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("flight-surgeon",))
        alert = next((a for a in store.alerts if a.alert_id == alert_id), None)
        if alert is None:
            raise HTTPException(404, "unknown alert_id")
        alert.acknowledged_by = role
        alert.acknowledged_at = _now()
        alert.ack_note = str(payload.get("note", ""))[:500]
        store.audit.append("alert.ack", role, alert.subject_id, alert.lane,
                           {"alert_id": alert_id, "note": alert.ack_note})
        return _envelope(lane=alert.lane, alert=alert.model_dump())

    @app.get("/api/audit")
    def get_audit(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("flight-surgeon", "ops", "researcher"))
        return _envelope(entries=[e.model_dump() for e in store.audit.entries()],
                         provenance="local SHA-256 hash chain (not a blockchain)")

    @app.get("/api/audit/verify")
    def verify_audit() -> dict:
        return _envelope(provenance="local SHA-256 hash chain (not a blockchain)",
                         **store.audit.verify())

    # ---------------- static web build ----------------
    dist = REPO_ROOT / "web" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str) -> FileResponse:
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app(Path(os.environ["HYPERION_AUDIT_LOG"]) if os.environ.get("HYPERION_AUDIT_LOG") else None)
