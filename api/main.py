"""FastAPI workstation API. Composition layer above the lanes; no lane imports this.

Run:  uvicorn api.main:app --host 0.0.0.0 --port 8000
Not a medical device. Demo thresholds, not clinically validated.

Architecture (P0-1 / P0-2 / P0-3 / P0-5)
---------------------------------------
* `CaseManager` owns one `Store` per `case_id`. The active case is selected per request by
  the `X-Case-Id` header through a pure-ASGI middleware, so two sessions never overwrite
  each other. Endpoints keep addressing `store` through a forwarding proxy.
* Every mutating request and every clock tick writes a full case snapshot to SQLite.
* A 1 Hz asyncio clock advances every running case, re-runs the deterministic gates,
  advances the S0-S4 lifecycle and the surgeon outbox, and broadcasts an SSE state event.
* `create_app()` defaults to a private in-memory database so each test app is isolated.
  `backend_api` passes `HYPERION_STATE_DB` (default data/hyperion_state.db) for persistence.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import statistics
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, lanes, outbox, replay, workflow
from .actions import ALLOWED_ACTIONS
from .audit import AuditLog
from .gates import (HARD_HR_CEILING_BPM, MAX_SUPPRESSION_HOLD_S, GateInput, HoldClock,
                    evaluate, kurtosis, normalise_activity, slew_rate)
from .models import (DISCLAIMER, Alert, Calibration, Frame, ManualCheck, SqReading,
                     Subject)
from .organs import (VALIDITY_HOURS, any_stale, effective_age_hours, min_tau,
                     organ_readings, readiness_streak, tau)
from .persistence import StateDatabase
from .scenarios import BY_ID, catalogue, rest_calibration_samples, sample

REPO_ROOT = Path(__file__).resolve().parents[1]
ROLE_ORDER = ("crew", "flight-surgeon", "ops", "researcher")
HABITATS = ("Space Station (0g)", "Transit Ship", "Lunar Base (0.16g)", "Rover")
DEFAULT_CASE_ID = "case-default"
CLOCK_PERIOD_S = 1.0
HISTORY_LIMIT = 600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _envelope(lane: str = "NONE", provenance: str = "", **extra: Any) -> dict[str, Any]:
    return {"lane": lane, "provenance": provenance, "generated_at": _now(),
            "disclaimer": DISCLAIMER, **extra}


def default_ws() -> dict[str, Any]:
    return {"mode": "SIMULATED_FALLBACK", "scenario_key": None, "enmo_g": None,
            "co2_mmhg": None, "proton_mgy_day": None, "water_ml": None, "ared_min": None,
            "alpha": 0.1, "replay_participant": None, "blackout": False,
            "booted": False, "underlying_scenario_id": None}


class Store:
    """One case. Persisted as a snapshot; hydrates exactly from SQLite."""

    def __init__(self, audit: AuditLog, case_id: str = DEFAULT_CASE_ID,
                 session_id: str | None = None) -> None:
        self.case_id = case_id
        self.session_id = session_id or f"session-{case_id}"
        self.created_at = _now()
        self.updated_at = self.created_at
        self.role = "crew"
        self.habitat = HABITATS[0]
        self.subject_id = "demo-crew-1"
        self.calibrations: dict[str, Calibration] = {}
        self.checks: dict[str, list[ManualCheck]] = {}
        self.alerts: list[Alert] = []
        self.audit = audit
        self.holds: dict[str, HoldClock] = {}
        self.scenario_id: str | None = None
        self.t_s = 0.0
        self.running = False
        self.frames: list[Frame] = []
        self.subscribers: list[asyncio.Queue] = []
        self.loop: asyncio.AbstractEventLoop | None = None
        self.ws: dict[str, Any] = default_ws()
        self.workflow = workflow.WorkflowRecord(updated_at=self.created_at)
        self.outbox: list[dict[str, Any]] = []
        self.replay_windows: list[replay.ReplayWindow] = []
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
        """Hand a frame to every SSE subscriber on the event loop's own thread."""
        loop = self.loop
        for queue in list(self.subscribers):
            def put(target: asyncio.Queue = queue) -> None:
                try:
                    target.put_nowait(frame)
                except asyncio.QueueFull:
                    pass
            if loop is not None and loop.is_running():
                loop.call_soon_threadsafe(put)
            else:
                put()

    def broadcast_state(self, payload: dict[str, Any]) -> None:
        loop = self.loop
        for queue in list(self.state_subscribers):
            def put(target: asyncio.Queue = queue, data: dict = payload) -> None:
                try:
                    target.put_nowait(data)
                except asyncio.QueueFull:
                    pass
            if loop is not None and loop.is_running():
                loop.call_soon_threadsafe(put)
            else:
                put()

    @property
    def state_subscribers(self) -> list[asyncio.Queue]:
        if not hasattr(self, "_state_subscribers"):
            self._state_subscribers: list[asyncio.Queue] = []
        return self._state_subscribers

    # ---------------- persistence ----------------
    def snapshot(self) -> dict[str, Any]:
        return {
            "case": {"case_id": self.case_id, "session_id": self.session_id,
                     "subject_id": self.subject_id, "habitat": self.habitat,
                     "scenario_key": self.ws.get("scenario_key"), "mode": self.ws["mode"],
                     "mission_t_s": self.t_s, "running": self.running,
                     "stage": self.workflow.stage, "ws": self.ws,
                     "holds": {k: {"held_since": v.held_since, "last_t": v.last_t,
                                   "latched": v.latched} for k, v in self.holds.items()},
                     "role": self.role, "created_at": self.created_at, "updated_at": _now()},
            "frames": [f.model_dump() for f in self.frames],
            "exams": [c.model_dump() for group in self.checks.values() for c in group],
            "calibrations": {k: v.model_dump() for k, v in self.calibrations.items()},
            "alerts": [a.model_dump() for a in self.alerts],
            "workflow": self.workflow.to_dict(),
            "outbox": self.outbox,
        }

    def hydrate(self, data: dict[str, Any]) -> None:
        c = data["case"]
        self.session_id = c["session_id"]
        self.subject_id = c["subject_id"]
        self.habitat = c["habitat"]
        self.role = c["role"]
        self.created_at = c["created_at"]
        self.updated_at = c["updated_at"]
        self.ws = {**default_ws(), **c["ws"]}
        self.t_s = float(c["mission_t_s"])
        self.running = bool(c["running"])
        self.scenario_id = self.ws.get("underlying_scenario_id")
        self.frames = [Frame.model_validate(f) for f in data["frames"]]
        self.checks = {}
        for exam in data["exams"]:
            check = ManualCheck.model_validate(exam)
            self.checks.setdefault(check.subject_id, []).append(check)
        self.calibrations = {k: Calibration.model_validate(v) for k, v in data["calibrations"].items()}
        self.alerts = [Alert.model_validate(a) for a in data["alerts"]]
        self.holds = {}
        for subject, hold in (c["holds"] or {}).items():
            self.holds[subject] = HoldClock(held_since=hold.get("held_since"),
                                          last_t=hold.get("last_t"), latched=bool(hold.get("latched")))
        self.workflow = workflow.WorkflowRecord.from_dict(data["workflow"])
        self.outbox = data["outbox"]
        if self.ws.get("mode") == "RECORDED_REPLAY" and self.ws.get("replay_participant"):
            self.replay_windows = replay.load(self.ws["replay_participant"])


class CaseManager:
    """Per-case stores, request-scoped case selection and the 1 Hz clock."""

    def __init__(self, db: StateDatabase, audit: AuditLog) -> None:
        self.db = db
        self.audit = audit
        self._stores: dict[str, Store] = {}
        self._active: contextvars.ContextVar[str] = contextvars.ContextVar(
            "hyperion_case_id", default=DEFAULT_CASE_ID)
        self.tick_hook = None  # set by register_workstation to refresh workflow/outbox

    def set_active(self, case_id: str):
        return self._active.set(case_id)

    def reset_active(self, token) -> None:
        self._active.reset(token)

    @property
    def active_case_id(self) -> str:
        return self._active.get()

    def store_for(self, case_id: str) -> Store:
        if case_id not in self._stores:
            store = Store(self.audit, case_id)
            data = self.db.load_case(case_id)
            if data is not None:
                store.hydrate(data)
            self._stores[case_id] = store
        return self._stores[case_id]

    @property
    def current(self) -> Store:
        return self.store_for(self._active.get())

    def save(self, case_id: str | None = None) -> None:
        store = self._stores.get(case_id or self._active.get())
        if store is not None:
            store.updated_at = _now()
            self.db.save_case(store.snapshot())

    def known_case_ids(self) -> list[str]:
        ids = {row["case_id"] for row in self.db.list_cases()} | set(self._stores)
        return sorted(ids)

    def tick(self, case_id: str, dt_s: float = CLOCK_PERIOD_S) -> dict[str, Any] | None:
        """Advance one case by dt_s. Returns a tick summary, or None when paused."""
        store = self.store_for(case_id)
        if not store.running or store.scenario_id is None:
            if self.tick_hook is not None:
                self.tick_hook(store, advanced=False)
                self.save(case_id)
            return None
        store.t_s = round(store.t_s + dt_s, 3)
        if self.tick_hook is not None:
            self.tick_hook(store, advanced=True)
        self.save(case_id)
        return {"case_id": case_id, "t_s": store.t_s, "stage": store.workflow.stage}


class StoreProxy:
    """Forwards attribute access to the request's active case store."""

    def __init__(self, manager: CaseManager) -> None:
        object.__setattr__(self, "_manager", manager)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_manager").current, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_manager").current, name, value)


class CaseContextMiddleware:
    """Pure-ASGI middleware: selects the case and persists after mutating requests.

    Pure ASGI (not BaseHTTPMiddleware) so the context variable propagates into the
    endpoint coroutine and into the threadpool worker that runs sync endpoints.
    """

    MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app, manager: CaseManager) -> None:
        self.app = app
        self.manager = manager

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}
        raw = headers.get("x-case-id", DEFAULT_CASE_ID).strip()
        case_id = raw if raw and len(raw) <= 64 and all(
            ch.isalnum() or ch in "-_" for ch in raw) else DEFAULT_CASE_ID
        token = self.manager.set_active(case_id)
        try:
            await self.app(scope, receive, send)
        finally:
            if scope.get("method", "GET") in self.MUTATING:
                try:
                    self.manager.save(case_id)
                except Exception:  # persistence must never mask the endpoint's own error
                    pass
            self.manager.reset_active(token)


def create_app(audit_path: Path | None = None, db_path: str | Path | None = None,
               *, boot_scenario: str | None = "nominal-orbital",
               clock_enabled: bool = True) -> FastAPI:
    db = StateDatabase(db_path)
    audit = AuditLog(audit_path, db=db)
    manager = CaseManager(db, audit)
    store = StoreProxy(manager)
    app_state: dict[str, Any] = {"frame_at": None, "maybe_alert": None, "live_payload": None}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        for case_id in manager.known_case_ids():
            manager.store_for(case_id).loop = asyncio.get_running_loop()
        manager.store_for(DEFAULT_CASE_ID).loop = asyncio.get_running_loop()
        task = asyncio.create_task(_clock_loop()) if clock_enabled else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            for case_id in manager.known_case_ids():
                st = manager.store_for(case_id)
                st.subscribers.clear()
                st.state_subscribers.clear()
                st.loop = None
            manager.save(DEFAULT_CASE_ID)

    async def _clock_loop() -> None:
        """1 Hz mission clock. Every running case advances, persists and broadcasts."""
        while True:
            await asyncio.sleep(CLOCK_PERIOD_S)
            for case_id in manager.known_case_ids():
                token = manager.set_active(case_id)
                try:
                    manager.tick(case_id)
                except Exception as exc:  # a bad case must not stop the clock for others
                    audit.append("clock.error", "system", case_id, "NONE",
                                 {"error": type(exc).__name__})
                finally:
                    manager.reset_active(token)

    app = FastAPI(
        title="HYPERION-MDA Workstation API",
        version=__version__,
        description=("Composition layer above the NASA lab, RECORDED, SIMULATED and INJECTED lanes. "
                     + DISCLAIMER),
        lifespan=lifespan,
    )
    # Same-origin in production (the SPA is served by this app). Permissive here because
    # this is a local research demo with demo-grade role headers (docs/SAFETY_ISSUES.md S10).
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Case-Id"],
    )
    app.add_middleware(CaseContextMiddleware, manager=manager)
    app.state.store = store
    app.state.manager = manager
    app.state.db = db

    def role_of(x_role: str | None) -> str:
        role = (x_role or manager.current.role).strip()
        return role if role in ROLE_ORDER else "crew"

    def require(x_role: str | None, allowed: tuple[str, ...]) -> str:
        role = role_of(x_role)
        if role not in allowed:
            raise HTTPException(status_code=403,
                                detail=f"Role {role!r} may not perform this action. "
                                       f"Allowed: {', '.join(allowed)}. (Demo-grade auth.)")
        return role

    def audited(event: str, role: str, subject: str, lane: str, detail: dict) -> None:
        """Every block records its case inside the hashed detail."""
        manager.current.audit.append(event, role, subject, lane,
                                     {**detail, "case_id": manager.active_case_id})

    # ---------------- health / session ----------------
    @app.get("/api/health")
    def health() -> dict:
        return _envelope(version=__version__, status="ok",
                         lanes={l.lane: l.available for l in lanes.lanes()},
                         allowed_actions=list(ALLOWED_ACTIONS),
                         hard_hr_ceiling_bpm=HARD_HR_CEILING_BPM,
                         max_suppression_hold_s=MAX_SUPPRESSION_HOLD_S,
                         clock_hz=1.0 / CLOCK_PERIOD_S,
                         persistence={"backend": "sqlite", "in_memory": db.in_memory,
                                      "path": None if db.in_memory else db.path},
                         recorded_replay=replay.status(),
                         auth="demo-grade role header, not an identity")

    @app.get("/api/session")
    def session(x_role: str | None = Header(default=None)) -> dict:
        st = manager.current
        return _envelope(lane="SIMULATED", provenance="demo session",
                         role=role_of(x_role), subject_id=st.subject_id, habitat=st.habitat,
                         case_id=st.case_id, session_id=st.session_id,
                         subjects=[Subject(subject_id=k, label=v, lane="SIMULATED",
                                           calibration=st.calibration(k)).model_dump()
                                   for k, v in st.subjects.items()],
                         running=st.running, scenario_id=st.scenario_id, t_s=st.t_s,
                         habitats=list(HABITATS), roles=list(ROLE_ORDER))

    @app.post("/api/session")
    def set_session(payload: dict = Body(default_factory=dict),
                    x_role: str | None = Header(default=None)) -> dict:
        st = manager.current
        role = role_of(x_role)
        if "role" in payload:
            if payload["role"] not in ROLE_ORDER:
                raise HTTPException(400, f"role must be one of {ROLE_ORDER}")
            st.role = payload["role"]
            role = st.role
        if "subject_id" in payload:
            if payload["subject_id"] not in st.subjects:
                raise HTTPException(400, "unknown subject_id")
            st.subject_id = payload["subject_id"]
        if "habitat" in payload:
            if payload["habitat"] not in HABITATS:
                raise HTTPException(400, f"habitat must be one of {HABITATS}")
            st.habitat = payload["habitat"]
        audited("session.change", role, st.subject_id, "SIMULATED", {"habitat": st.habitat})
        return session(x_role=role)

    @app.get("/api/subjects")
    def subjects() -> dict:
        st = manager.current
        return _envelope(lane="SIMULATED", provenance="demo subjects",
                         subjects=[Subject(subject_id=k, label=v, lane="SIMULATED",
                                           calibration=st.calibration(k)).model_dump()
                                   for k, v in st.subjects.items()])

    # ---------------- cases (P0-2) ----------------
    @app.get("/api/cases")
    def list_cases() -> dict:
        return _envelope(cases=db.list_cases(), active_case_id=manager.active_case_id,
                         provenance="SQLite case registry")

    @app.post("/api/case/new")
    def new_case(payload: dict = Body(default_factory=dict),
                 x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        requested = str(payload.get("case_id") or f"case-{uuid.uuid4().hex[:8]}")
        if not requested or len(requested) > 64 or not all(c.isalnum() or c in "-_" for c in requested):
            raise HTTPException(400, "case_id must be 1-64 chars of [A-Za-z0-9-_]")
        if db.load_case(requested) is not None:
            raise HTTPException(409, f"case {requested!r} already exists")
        token = manager.set_active(requested)
        try:
            manager.store_for(requested)
            audited("case.create", role, manager.current.subject_id, "NONE", {})
            manager.save(requested)
            return _envelope(case_id=requested, session_id=manager.current.session_id,
                             provenance="new isolated SQLite case")
        finally:
            manager.reset_active(token)

    @app.get("/api/case")
    def get_case() -> dict:
        st = manager.current
        return _envelope(case_id=st.case_id, session_id=st.session_id,
                         created_at=st.created_at, updated_at=st.updated_at,
                         stage=st.workflow.stage, mission_t_s=st.t_s, running=st.running,
                         scenario_key=st.ws.get("scenario_key"), mode=st.ws["mode"],
                         persistence={"backend": "sqlite", "in_memory": db.in_memory},
                         transitions=db.transitions(st.case_id)[-20:],
                         provenance="persisted case record")

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
        # Crew may inspect their own verified lab provenance in the cockpit drawer (P0-4).
        require(x_role, ("crew", "flight-surgeon", "researcher", "ops"))
        data = lanes.lab_rows()
        manifest = {}
        try:
            manifest = lanes.osdr_manifest()
        except Exception as exc:
            manifest = {"available": False, "detail": f"manifest unreadable: {exc}"}
        return _envelope(**{**data, "lane": "LAB DATA", "manifest": manifest,
                            "provenance": data.get("provenance", "")})

    @app.get("/api/research/m6")
    def get_m6(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("researcher", "flight-surgeon", "ops"))
        data = lanes.m6_results()
        return _envelope(**{**data, "lane": data.get("lane", "RECORDED-NON-ASTRONAUT"),
                            "provenance": data.get("provenance", "")})

    @app.get("/api/replay")
    def get_replay() -> dict:
        return _envelope(lane="RECORDED-NON-ASTRONAUT", provenance=replay.PROVENANCE,
                         replay=replay.status())

    # ---------------- calibration ----------------
    @app.post("/api/calibration/{subject_id}")
    def calibrate(subject_id: str, x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("ops",))
        st = manager.current
        if subject_id not in st.subjects:
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
        st.calibrations[subject_id] = cal
        st.holds.pop(subject_id, None)
        audited("calibration.create", role, subject_id, "SIMULATED", {"n_windows": cal.n_windows})
        return _envelope(lane="SIMULATED", provenance=cal.source, calibration=cal.model_dump())

    @app.delete("/api/calibration/{subject_id}")
    def uncalibrate(subject_id: str, x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("ops",))
        st = manager.current
        st.calibrations.pop(subject_id, None)
        st.holds.pop(subject_id, None)
        audited("calibration.delete", role, subject_id, "NONE", {})
        return _envelope(calibration=Calibration(subject_id=subject_id).model_dump())

    # ---------------- manual checks / organs ----------------
    @app.post("/api/manual")
    def post_manual(check: ManualCheck, x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        st = manager.current
        if check.subject_id not in st.subjects:
            raise HTTPException(400, "unknown subject_id")
        if not check.recorded_at:
            check.recorded_at = _now()
        if check.kind == "bp" and (check.systolic is None or check.diastolic is None):
            raise HTTPException(400, "bp requires systolic and diastolic")
        if check.kind != "bp" and check.value is None:
            raise HTTPException(400, f"{check.kind} requires value")
        st.checks.setdefault(check.subject_id, []).append(check)
        audited("manual.entry", role, check.subject_id, check.lane, {"kind": check.kind})
        return _envelope(lane=check.lane, provenance=check.source, check=check.model_dump(),
                         readiness=readiness_streak(st.checks_for(check.subject_id)))

    @app.get("/api/manual/{subject_id}")
    def get_manual(subject_id: str, x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("crew", "flight-surgeon", "ops"))
        checks = manager.current.checks_for(subject_id)
        return _envelope(lane="INJECTED", provenance="crew entry (demo-grade, unverified)",
                         checks=[c.model_dump() for c in checks],
                         validity_hours=VALIDITY_HOURS,
                         readiness=readiness_streak(checks))

    @app.post("/api/pvt")
    def post_pvt(payload: dict = Body(...), x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "flight-surgeon"))
        st = manager.current
        subject_id = payload.get("subject_id", st.subject_id)
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
        st.checks.setdefault(subject_id, []).append(check)
        audited("pvt.result", role, subject_id, "INJECTED", {"n": len(values)})
        return _envelope(lane="INJECTED", provenance=check.source, median_ms=median,
                         n=len(values), lapses_over_350ms=sum(v > 350 for v in values),
                         check=check.model_dump(),
                         note="Demo reaction test. Not a validated cognitive assessment.")

    @app.get("/api/organs")
    def get_organs(subject_id: str | None = None,
                   x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("crew", "flight-surgeon", "ops"))
        st = manager.current
        sid = subject_id or st.subject_id
        checks = st.checks_for(sid)
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

    def _raw_at(st: Store, scenario_id: str, t_s: float) -> dict:
        if st.ws.get("mode") == "RECORDED_REPLAY":
            return replay.sample(st.replay_windows, t_s)
        return sample(scenario_id, t_s)

    def _frame_at(scenario_id: str, t_s: float) -> Frame:
        st = manager.current
        raw = _raw_at(st, scenario_id, t_s)
        cal = st.calibration(st.subject_id)
        activity = normalise_activity(raw["magnitude"], cal)
        recorded_quality = raw.get("recorded_quality")
        sqi = SqReading(kurtosis=kurtosis(raw["window"]) if raw["window"] else None,
                        slew=slew_rate(raw["window"], 25.0) if raw["window"] else None,
                        calibrated=cal.calibrated)
        checks = st.checks_for(st.subject_id)
        mission_now = st.t_s if st.ws.get("scenario_key") or st.ws.get("mode") == "RECORDED_REPLAY" else None
        stale = raw["stale_manual"] or any_stale(checks, mission_now_s=mission_now)
        tau_min = (0.1 if raw["stale_manual"] else min_tau(checks, mission_now_s=mission_now))
        co2 = st.ws.get("co2_mmhg") if st.ws.get("scenario_key") else None
        onsd_check = next((c for c in sorted(checks, key=lambda c: c.recorded_at, reverse=True)
                           if c.kind == "onsd"), None)
        onsd_tau = None
        if onsd_check is not None:
            age = effective_age_hours(onsd_check, mission_now_s=mission_now)
            onsd_tau = tau(age) if age is not None else None
        flags = list(raw["non_rate_flags"])
        if st.ws.get("scenario_key") and st.ws.get("proton_mgy_day") is not None and st.ws["proton_mgy_day"] > 2.0:
            flags.append("SIMULATED proton dose > 2 mGy/day (demo chest/immune rule)")
        temp_check = next((c for c in sorted(checks, key=lambda c: c.recorded_at, reverse=True)
                           if c.kind == "temperature"), None)
        if st.ws.get("scenario_key") and temp_check is not None and temp_check.value is not None and temp_check.value >= 38.0:
            flags.append("crew-entered temperature >= 38 degC (demo chest/immune rule)")
        inp = GateInput(t_s=t_s, hr_bpm=raw["hr_bpm"], activity_norm=activity, sqi=sqi,
                        non_rate_flags=flags, stale_manual=stale, min_tau=tau_min,
                        hr_status="OK" if raw["hr_bpm"] is not None else "NOT_AVAILABLE",
                        co2_mmhg=co2, onsd_tau=onsd_tau, recorded_quality=recorded_quality)
        frame = evaluate(inp, cal, st.hold(st.subject_id))
        frame.lane = raw["lane"]
        frame.subject_id = st.subject_id
        frame.habitat = st.habitat  # type: ignore[assignment]
        frame.scenario_id = scenario_id
        return frame

    def _maybe_alert(frame: Frame, role: str) -> Alert | None:
        st = manager.current
        if frame.state not in {"SURGEON_ALERT", "CREW_CHECK"}:
            return None
        severity = "ALERT" if frame.state == "SURGEON_ALERT" else "HOLD"
        open_same = next((a for a in st.alerts
                          if a.subject_id == frame.subject_id and a.state == frame.state
                          and a.acknowledged_at is None), None)
        if open_same is not None:
            return open_same
        alert = Alert(alert_id=uuid.uuid4().hex[:12], subject_id=frame.subject_id,
                      created_at=_now(), lane=frame.lane, state=frame.state, severity=severity,
                      reason=(frame.suppression_reason or frame.gates[-1].reason
                              if frame.gates else frame.state),
                      actions=frame.actions, non_rate_flags=frame.non_rate_flags)
        st.alerts.append(alert)
        audited("alert.raise", role, frame.subject_id, frame.lane,
                {"alert_id": alert.alert_id, "state": frame.state,
                 "severity": severity, "non_rate_flags": frame.non_rate_flags})
        return alert

    @app.post("/api/scenarios/{scenario_id}/start")
    def start(scenario_id: str, x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        st = manager.current
        if scenario_id not in BY_ID:
            raise HTTPException(404, f"unknown scenario {scenario_id!r}")
        st.ws["mode"] = "SIMULATED_FALLBACK"
        st.ws["scenario_key"] = None
        st.scenario_id = scenario_id
        st.ws["underlying_scenario_id"] = scenario_id
        st.t_s = 0.0
        st.running = True
        st.frames = []
        st.holds.pop(st.subject_id, None)
        if scenario_id == "uncalibrated":
            st.calibrations.pop(st.subject_id, None)
        audited("scenario.start", role, st.subject_id, BY_ID[scenario_id].info.lane,
                {"scenario_id": scenario_id})
        frame = _frame_at(scenario_id, 0.0)
        st.frames.append(frame)
        return _envelope(lane=frame.lane, provenance="api/scenarios.py",
                         scenario=BY_ID[scenario_id].info.model_dump(), frame=frame.model_dump())

    @app.post("/api/stream/stop")
    def stop(x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        st = manager.current
        st.running = False
        audited("scenario.stop", role, st.subject_id, "NONE",
                {"scenario_id": st.scenario_id})
        return _envelope(running=False, t_s=st.t_s)

    @app.post("/api/stream/step")
    def step(dt_s: float = 1.0, x_role: str | None = Header(default=None)) -> dict:
        """Advance one frame deterministically. Used by tests, the cockpit and the clock."""
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        st = manager.current
        if st.scenario_id is None:
            raise HTTPException(409, "no scenario started")
        if dt_s <= 0 or dt_s > 60:
            raise HTTPException(400, "dt_s must be in (0, 60]")
        st.t_s = round(st.t_s + dt_s, 3)
        frame = _frame_at(st.scenario_id, st.t_s)
        st.frames.append(frame)
        st.frames = st.frames[-HISTORY_LIMIT:]
        alert = _maybe_alert(frame, role)
        st.broadcast(frame)
        if manager.tick_hook is not None:
            manager.tick_hook(st, advanced=False)
        return _envelope(lane=frame.lane, provenance="api/scenarios.py",
                         frame=frame.model_dump(),
                         alert=alert.model_dump() if alert else None)

    @app.get("/api/stream/state")
    def stream_state() -> dict:
        st = manager.current
        latest = st.frames[-1].model_dump() if st.frames else None
        return _envelope(lane=st.frames[-1].lane if st.frames else "NONE",
                         running=st.running, t_s=st.t_s, scenario_id=st.scenario_id,
                         frame=latest, history=[f.model_dump() for f in st.frames[-180:]])

    @app.get("/api/stream/events")
    async def events(request: Request) -> StreamingResponse:
        """SSE: `frame` events for the legacy contract, `state` events for the cockpit."""
        st = manager.current
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        state_queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        st.subscribers.append(queue)
        st.state_subscribers.append(state_queue)
        st.loop = asyncio.get_running_loop()

        async def gen():
            try:
                yield f"event: hello\ndata: {json.dumps({'t_s': st.t_s, 'case_id': st.case_id})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    delivered = False
                    try:
                        frame = await asyncio.wait_for(queue.get(), timeout=0.25)
                        yield f"event: frame\ndata: {frame.model_dump_json()}\n\n"
                        delivered = True
                    except asyncio.TimeoutError:
                        pass
                    try:
                        payload = state_queue.get_nowait()
                        yield f"event: state\ndata: {json.dumps(payload)}\n\n"
                        delivered = True
                    except asyncio.QueueEmpty:
                        pass
                    if not delivered:
                        yield ": keep-alive\n\n"
            finally:
                if queue in st.subscribers:
                    st.subscribers.remove(queue)
                if state_queue in st.state_subscribers:
                    st.state_subscribers.remove(state_queue)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                          "X-Case-Id": st.case_id})

    # ---------------- transport (P0-1) ----------------
    @app.post("/api/transport")
    def transport(payload: dict = Body(default_factory=dict),
                  x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        action = str(payload.get("action", "")).lower()
        st = manager.current
        if action == "play":
            if st.scenario_id is None:
                raise HTTPException(409, "no scenario or replay loaded")
            st.running = True
            audited("transport.play", role, st.subject_id, "NONE", {})
        elif action == "pause":
            st.running = False
            audited("transport.pause", role, st.subject_id, "NONE", {})
        elif action == "step":
            dt = float(payload.get("dt_s", 10.0))
            if dt <= 0 or dt > 60:
                raise HTTPException(400, "dt_s must be in (0, 60]")
            if st.scenario_id is None:
                raise HTTPException(409, "no scenario or replay loaded")
            st.t_s = round(st.t_s + dt, 3)
            frame = _frame_at(st.scenario_id, st.t_s)
            st.frames.append(frame)
            st.frames = st.frames[-HISTORY_LIMIT:]
            _maybe_alert(frame, role)
            st.broadcast(frame)
            audited("transport.step", role, st.subject_id, frame.lane, {"dt_s": dt})
        else:
            raise HTTPException(400, "action must be play, pause or step")
        if manager.tick_hook is not None:
            manager.tick_hook(st, advanced=False)
        manager.save()
        payload_fn = app_state.get("live_payload")
        return payload_fn() if payload_fn else _envelope(running=st.running, t_s=st.t_s)

    # ---------------- alerts / audit ----------------
    @app.get("/api/alerts")
    def get_alerts(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("flight-surgeon", "ops", "crew"))
        return _envelope(alerts=[a.model_dump() for a in manager.current.alerts])

    @app.post("/api/alerts/{alert_id}/ack")
    def ack(alert_id: str, payload: dict = Body(default_factory=dict),
            x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("flight-surgeon",))
        st = manager.current
        alert = next((a for a in st.alerts if a.alert_id == alert_id), None)
        if alert is None:
            raise HTTPException(404, "unknown alert_id")
        alert.acknowledged_by = role
        alert.acknowledged_at = _now()
        alert.ack_note = str(payload.get("note", ""))[:500]
        import hashlib
        note_hash = hashlib.sha256((alert.ack_note or "").encode("utf-8")).hexdigest()
        audited("alert.ack", role, alert.subject_id, alert.lane,
                {"alert_id": alert_id, "note_sha256": note_hash})
        return _envelope(lane=alert.lane, alert=alert.model_dump())

    @app.get("/api/audit")
    def get_audit(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("flight-surgeon", "ops", "researcher"))
        return _envelope(entries=[e.model_dump() for e in audit.entries()],
                         provenance="local SHA-256 hash chain (not a blockchain)")

    @app.get("/api/audit/verify")
    def verify_audit() -> dict:
        return _envelope(provenance="local SHA-256 hash chain (not a blockchain)",
                         **audit.verify())

    # ---------------- surgeon outbox (P0-3 / P0-5) ----------------
    @app.get("/api/surgeon/outbox")
    def get_outbox(x_role: str | None = Header(default=None)) -> dict:
        require(x_role, ("crew", "ops", "flight-surgeon"))
        st = manager.current
        return _envelope(lane="NONE", provenance="persisted store-and-forward outbox (demo comms timers)",
                         case_id=st.case_id, stage=st.workflow.stage,
                         comms=outbox.profile_for(workflow_habitat_key(st)).__dict__,
                         blackout=bool(st.ws.get("blackout")),
                         packets=outbox.public_view(st.outbox))

    @app.post("/api/surgeon/blackout")
    def set_blackout(payload: dict = Body(default_factory=dict),
                     x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        st = manager.current
        st.ws["blackout"] = bool(payload.get("blackout", False))
        changed = outbox.advance(st.outbox, now_iso=_now(), blackout=bool(st.ws["blackout"]))
        audited("comms.blackout", role, st.subject_id, "NONE",
                {"blackout": bool(st.ws["blackout"]), "packets_changed": len(changed)})
        manager.save()
        return get_outbox(x_role=role)

    @app.post("/api/surgeon/acknowledge")
    def surgeon_acknowledge(payload: dict = Body(default_factory=dict),
                            x_role: str | None = Header(default=None)) -> dict:
        role = require(x_role, ("flight-surgeon",))
        st = manager.current
        packet_id = str(payload.get("packet_id", ""))
        directive = str(payload.get("directive", ""))[:500]
        if not directive.strip():
            raise HTTPException(400, "directive text is required for the acknowledgement receipt")
        packet = next((p for p in st.outbox if p["packet_id"] == packet_id), None)
        if packet is None:
            raise HTTPException(404, "unknown packet_id")
        if packet["comms_state"] != outbox.DELIVERED:
            raise HTTPException(409, f"packet is {packet['comms_state']}; only "
                                     f"{outbox.DELIVERED} packets can be acknowledged")
        receipt = outbox.acknowledge_packet(packet, directive=directive, role=role, now_iso=_now())
        try:
            transition = workflow.acknowledge(st.workflow, packet_fingerprint=packet["fingerprint"],
                                              mission_t_s=st.t_s, now=_now())
        except ValueError:
            transition = {"from_stage": st.workflow.stage, "to_stage": st.workflow.stage,
                          "reason": "packet acknowledged outside an escalated stage",
                          "mission_t_s": st.t_s, "ts": _now()}
        db.record_transition(st.case_id, transition["from_stage"], transition["to_stage"],
                             transition["reason"], st.t_s, transition["ts"])
        audited("surgeon.receipt", role, st.subject_id, "NONE",
                {"packet_id": packet["packet_id"], "receipt_id": receipt["receipt_id"],
                 "receipt_sha256": receipt["sha256"], "stage": st.workflow.stage})
        manager.save()
        payload_fn = app_state.get("live_payload")
        result = payload_fn() if payload_fn else _envelope()
        return {**result, "receipt": receipt}

    def workflow_habitat_key(st: Store) -> str:
        from .workstation import HABITAT_BY_LABEL
        return HABITAT_BY_LABEL.get(st.habitat, "station")

    # ---------------- unified live workstation ----------------
    from .workstation import register_workstation
    register_workstation(app, store, frame_at=_frame_at, maybe_alert=_maybe_alert,
                         envelope=_envelope, now=_now, require=require, role_of=role_of,
                         manager=manager, audited=audited, app_state=app_state)

    # ---------------- deterministic reset (P0-6) ----------------
    @app.post("/api/case/reset")
    def reset_case(payload: dict = Body(default_factory=dict),
                   x_role: str | None = Header(default=None)) -> dict:
        """Reset the active case to clean nominal monitoring.

        Clinical case rows are cleared. The audit chain is deliberately preserved and a
        reset block is appended: an audit log that erases itself on reset is not an audit log.
        """
        role = require(x_role, ("crew", "ops", "flight-surgeon"))
        st = manager.current
        head_before = audit.verify().get("head")
        db.delete_case_payload(st.case_id)
        st.checks = {}
        st.calibrations = {}
        st.alerts = []
        st.holds = {}
        st.frames = []
        st.outbox = []
        st.replay_windows = []
        st.t_s = 0.0
        st.running = False
        st.scenario_id = None
        st.ws = default_ws()
        st.workflow = workflow.WorkflowRecord(updated_at=_now())
        audited("case.reset", role, st.subject_id, "NONE",
                {"prior_head_sha256": head_before, "genesis_stage": workflow.S0})
        seed = app_state.get("seed_scenario")
        if seed is not None:
            seed("nominal-orbital", role)
        db.record_transition(st.case_id, "RESET", workflow.S0, "deterministic case reset", 0.0, _now())
        manager.save()
        payload_fn = app_state.get("state_payload")
        return payload_fn() if payload_fn else _envelope(stage=workflow.S0)

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

    def ensure_booted() -> None:
        """Boot the cockpit's case into a live labelled stream on first read (P0-1).

        Done on the first `GET /api/state` rather than in the constructor so a bare app
        still has no scenario until something asks for the workstation view. A persisted
        case is never re-seeded: restart restores the exact prior state.
        """
        if not boot_scenario:
            return
        st = manager.current
        if st.ws.get("booted"):
            return
        seed = app_state.get("seed_scenario")
        if seed is None:
            return
        seed(boot_scenario, "system")
        st.ws["booted"] = True
        manager.save()

    app_state["ensure_booted"] = ensure_booted
    return app


app = create_app(Path(os.environ["HYPERION_AUDIT_LOG"]) if os.environ.get("HYPERION_AUDIT_LOG") else None,
                 os.environ.get("HYPERION_STATE_DB"))