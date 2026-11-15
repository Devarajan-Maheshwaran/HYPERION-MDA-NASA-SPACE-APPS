"""SQLite persistence for the live workstation (P0-2).

Every case is isolated by `case_id`. A case owns its telemetry history, manual exams,
calibrations, workflow stage, surgeon outbox and alerts. The audit chain is app-wide and
append-only, and each block records the case id inside its hashed detail.

Design notes
------------
* `db_path=None` or `":memory:"` keeps a private in-process database. That is the default
  for `create_app()` so the existing test-suite stays isolated per app instance.
* A file path (env `HYPERION_STATE_DB`, default `data/hyperion_state.db` via backend_api)
  survives a process restart. `load_case` rebuilds the exact working state.
* Connections are opened per operation for file databases (threadpool-safe); an in-memory
  database keeps one connection guarded by a lock because it is connection-scoped.
* No raw measurement is written to the audit chain. Measurements live in `manual_exams`
  and `telemetry_history`; the chain stores event metadata and payload digests only.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    habitat TEXT NOT NULL,
    scenario_key TEXT,
    mode TEXT NOT NULL,
    mission_t_s REAL NOT NULL,
    running INTEGER NOT NULL,
    stage TEXT NOT NULL,
    ws_json TEXT NOT NULL,
    hold_json TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS telemetry_history (
    case_id TEXT NOT NULL,
    t_s REAL NOT NULL,
    frame_json TEXT NOT NULL,
    PRIMARY KEY (case_id, t_s)
);
CREATE TABLE IF NOT EXISTS manual_exams (
    exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    mission_t_s REAL
);
CREATE INDEX IF NOT EXISTS idx_exams_case ON manual_exams(case_id, exam_id);
CREATE TABLE IF NOT EXISTS personal_calibrations (
    case_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    cal_json TEXT NOT NULL,
    PRIMARY KEY (case_id, subject_id)
);
CREATE TABLE IF NOT EXISTS s0_s4_workflow_state (
    case_id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    since_mission_t_s REAL NOT NULL,
    requested_exam TEXT,
    finding_fingerprint TEXT,
    acknowledged_fingerprint TEXT,
    reason TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    from_stage TEXT NOT NULL,
    to_stage TEXT NOT NULL,
    reason TEXT NOT NULL,
    mission_t_s REAL NOT NULL,
    ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS surgeon_outbox_packets (
    packet_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    organ TEXT NOT NULL,
    finding TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    sbar_json TEXT NOT NULL,
    comms_state TEXT NOT NULL,
    habitat TEXT NOT NULL,
    delay_s REAL NOT NULL,
    release_at_epoch_s REAL,
    delivered_at TEXT,
    acknowledged_at TEXT,
    receipt_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_case ON surgeon_outbox_packets(case_id, created_at);
CREATE TABLE IF NOT EXISTS alerts (
    case_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (case_id, alert_id)
);
CREATE TABLE IF NOT EXISTS audit_chain_blocks (
    seq INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,
    role TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    lane TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    prev_sha256 TEXT NOT NULL,
    sha256 TEXT NOT NULL
);
"""


def _dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class StateDatabase:
    """Thin, lock-guarded SQLite wrapper. One instance per app."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.path = str(db_path) if db_path is not None else ":memory:"
        self.in_memory = self.path == ":memory:"
        self._lock = threading.RLock()
        self._shared: sqlite3.Connection | None = None
        if not self.in_memory:
            parent = Path(self.path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(SCHEMA)
                conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                             (str(SCHEMA_VERSION),))
                conn.commit()
            finally:
                self._close(conn)

    # ---------------- connection handling ----------------
    def _connect(self) -> sqlite3.Connection:
        if self.in_memory:
            if self._shared is None:
                self._shared = sqlite3.connect(":memory:", check_same_thread=False)
                self._shared.row_factory = sqlite3.Row
                self._shared.execute("PRAGMA foreign_keys=ON")
            return self._shared
        conn = sqlite3.connect(self.path, timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _close(self, conn: sqlite3.Connection) -> None:
        if not self.in_memory:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(sql, params)
                conn.commit()
            finally:
                self._close(conn)

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executemany(sql, rows)
                conn.commit()
            finally:
                self._close(conn)

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            conn = self._connect()
            try:
                return list(conn.execute(sql, params).fetchall())
            finally:
                self._close(conn)

    def transaction(self):
        """Context manager yielding a connection inside the lock."""
        return _Transaction(self)

    # ---------------- audit chain ----------------
    def append_audit(self, entry: dict[str, Any]) -> None:
        self.execute(
            "INSERT OR REPLACE INTO audit_chain_blocks"
            "(seq, ts, event, role, subject_id, lane, detail_json, prev_sha256, sha256)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (entry["seq"], entry["ts"], entry["event"], entry["role"], entry["subject_id"],
             entry["lane"], _dumps(entry["detail"]), entry["prev_sha256"], entry["sha256"]),
        )

    def load_audit(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM audit_chain_blocks ORDER BY seq")
        return [{"seq": r["seq"], "ts": r["ts"], "event": r["event"], "role": r["role"],
                 "subject_id": r["subject_id"], "lane": r["lane"],
                 "detail": json.loads(r["detail_json"]), "prev_sha256": r["prev_sha256"],
                 "sha256": r["sha256"]} for r in rows]

    def clear_audit(self) -> None:
        self.execute("DELETE FROM audit_chain_blocks")

    # ---------------- case snapshot ----------------
    def save_case(self, snapshot: dict[str, Any]) -> None:
        """Write a full case snapshot atomically. Small state, so a rewrite is cheap."""
        c = snapshot["case"]
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cases"
                "(case_id, session_id, subject_id, habitat, scenario_key, mode, mission_t_s,"
                " running, stage, ws_json, hold_json, role, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (c["case_id"], c["session_id"], c["subject_id"], c["habitat"], c["scenario_key"],
                 c["mode"], c["mission_t_s"], int(c["running"]), c["stage"], _dumps(c["ws"]),
                 _dumps(c["holds"]), c["role"], c["created_at"], c["updated_at"]),
            )
            conn.execute("DELETE FROM telemetry_history WHERE case_id=?", (c["case_id"],))
            conn.executemany(
                "INSERT INTO telemetry_history(case_id, t_s, frame_json) VALUES(?,?,?)",
                [(c["case_id"], f["t_s"], _dumps(f)) for f in snapshot["frames"]],
            )
            conn.execute("DELETE FROM manual_exams WHERE case_id=?", (c["case_id"],))
            conn.executemany(
                "INSERT INTO manual_exams(case_id, subject_id, kind, payload_json, recorded_at, mission_t_s)"
                " VALUES(?,?,?,?,?,?)",
                [(c["case_id"], e["subject_id"], e["kind"], _dumps(e), e["recorded_at"],
                  e.get("mission_t_s")) for e in snapshot["exams"]],
            )
            conn.execute("DELETE FROM personal_calibrations WHERE case_id=?", (c["case_id"],))
            conn.executemany(
                "INSERT INTO personal_calibrations(case_id, subject_id, cal_json) VALUES(?,?,?)",
                [(c["case_id"], subject, _dumps(cal)) for subject, cal in snapshot["calibrations"].items()],
            )
            conn.execute("DELETE FROM alerts WHERE case_id=?", (c["case_id"],))
            conn.executemany(
                "INSERT INTO alerts(case_id, alert_id, payload_json) VALUES(?,?,?)",
                [(c["case_id"], a["alert_id"], _dumps(a)) for a in snapshot["alerts"]],
            )
            w = snapshot["workflow"]
            conn.execute(
                "INSERT OR REPLACE INTO s0_s4_workflow_state"
                "(case_id, stage, since_mission_t_s, requested_exam, finding_fingerprint,"
                " acknowledged_fingerprint, reason, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (c["case_id"], w["stage"], w["since_mission_t_s"], w["requested_exam"],
                 w["finding_fingerprint"], w["acknowledged_fingerprint"], w["reason"], w["updated_at"]),
            )
            # The snapshot is authoritative: packets dropped by a scenario switch or a
            # case reset must not resurrect from the database on the next hydrate.
            conn.execute("DELETE FROM surgeon_outbox_packets WHERE case_id=?", (c["case_id"],))
            for packet in snapshot["outbox"]:
                conn.execute(
                    "INSERT OR REPLACE INTO surgeon_outbox_packets"
                    "(packet_id, case_id, created_at, organ, finding, fingerprint, sbar_json,"
                    " comms_state, habitat, delay_s, release_at_epoch_s, delivered_at,"
                    " acknowledged_at, receipt_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (packet["packet_id"], c["case_id"], packet["created_at"], packet["organ"],
                     packet["finding"], packet["fingerprint"], _dumps(packet["sbar"]),
                     packet["comms_state"], packet["habitat"], packet["delay_s"],
                     packet["release_at_epoch_s"], packet["delivered_at"],
                     packet["acknowledged_at"],
                     None if packet["receipt"] is None else _dumps(packet["receipt"])),
                )

    def delete_case_payload(self, case_id: str) -> None:
        """Clear clinical case rows. The audit chain is deliberately NOT touched."""
        with self.transaction() as conn:
            for table in ("telemetry_history", "manual_exams", "personal_calibrations",
                          "alerts", "surgeon_outbox_packets", "workflow_transitions"):
                conn.execute(f"DELETE FROM {table} WHERE case_id=?", (case_id,))  # noqa: S608 - fixed table names

    def record_transition(self, case_id: str, from_stage: str, to_stage: str, reason: str,
                          mission_t_s: float, ts: str) -> None:
        self.execute(
            "INSERT INTO workflow_transitions(case_id, from_stage, to_stage, reason, mission_t_s, ts)"
            " VALUES(?,?,?,?,?,?)", (case_id, from_stage, to_stage, reason, mission_t_s, ts))

    def transitions(self, case_id: str) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM workflow_transitions WHERE case_id=? ORDER BY id", (case_id,))
        return [dict(r) for r in rows]

    def list_cases(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT case_id, session_id, subject_id, stage, scenario_key, mode,"
                          " mission_t_s, running, updated_at FROM cases ORDER BY updated_at DESC")
        return [dict(r) for r in rows]

    def load_case(self, case_id: str) -> dict[str, Any] | None:
        rows = self.query("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not rows:
            return None
        r = rows[0]
        case = {"case_id": r["case_id"], "session_id": r["session_id"], "subject_id": r["subject_id"],
                "habitat": r["habitat"], "scenario_key": r["scenario_key"], "mode": r["mode"],
                "mission_t_s": r["mission_t_s"], "running": bool(r["running"]), "stage": r["stage"],
                "ws": json.loads(r["ws_json"]), "holds": json.loads(r["hold_json"]),
                "role": r["role"], "created_at": r["created_at"], "updated_at": r["updated_at"]}
        frames = [json.loads(x["frame_json"]) for x in self.query(
            "SELECT frame_json FROM telemetry_history WHERE case_id=? ORDER BY t_s", (case_id,))]
        exams = [json.loads(x["payload_json"]) for x in self.query(
            "SELECT payload_json FROM manual_exams WHERE case_id=? ORDER BY exam_id", (case_id,))]
        cals = {x["subject_id"]: json.loads(x["cal_json"]) for x in self.query(
            "SELECT subject_id, cal_json FROM personal_calibrations WHERE case_id=?", (case_id,))}
        alerts = [json.loads(x["payload_json"]) for x in self.query(
            "SELECT payload_json FROM alerts WHERE case_id=? ORDER BY rowid", (case_id,))]
        wf = self.query("SELECT * FROM s0_s4_workflow_state WHERE case_id=?", (case_id,))
        workflow = ({"stage": wf[0]["stage"], "since_mission_t_s": wf[0]["since_mission_t_s"],
                     "requested_exam": wf[0]["requested_exam"],
                     "finding_fingerprint": wf[0]["finding_fingerprint"],
                     "acknowledged_fingerprint": wf[0]["acknowledged_fingerprint"],
                     "reason": wf[0]["reason"], "updated_at": wf[0]["updated_at"]}
                    if wf else None)
        outbox = []
        for p in self.query("SELECT * FROM surgeon_outbox_packets WHERE case_id=? ORDER BY created_at, packet_id",
                            (case_id,)):
            outbox.append({"packet_id": p["packet_id"], "case_id": p["case_id"],
                           "created_at": p["created_at"], "organ": p["organ"], "finding": p["finding"],
                           "fingerprint": p["fingerprint"], "sbar": json.loads(p["sbar_json"]),
                           "comms_state": p["comms_state"], "habitat": p["habitat"],
                           "delay_s": p["delay_s"], "release_at_epoch_s": p["release_at_epoch_s"],
                           "delivered_at": p["delivered_at"], "acknowledged_at": p["acknowledged_at"],
                           "receipt": None if p["receipt_json"] is None else json.loads(p["receipt_json"])})
        return {"case": case, "frames": frames, "exams": exams, "calibrations": cals,
                "alerts": alerts, "workflow": workflow, "outbox": outbox}


class _Transaction:
    def __init__(self, db: StateDatabase) -> None:
        self.db = db
        self.conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self.db._lock.acquire()
        self.conn = self.db._connect()
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.db._close(self.conn)
            self.db._lock.release()
