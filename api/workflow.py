"""Deterministic S0-S4 case lifecycle (P0-3).

This is a plain Python finite state machine. No LLM and no agent framework participates:
`resolve()` is a pure function of the current gate frame, the organ readings and the
persisted workflow record, so the transition table is unit-testable and reproducible.

DEMO ROUTING, NOT CLINICAL TRIAGE
---------------------------------
Which finding class routes to an onboard crew countermeasure (S3) and which routes to a
flight surgeon (S4) is a *declared demo routing table*, not a validated clinical protocol.
Organ severity badges are unchanged by routing: a WATCH/ALERT organ stays WATCH/ALERT on
the body map even when the demo routes it to an onboard check first.

Stage set (exactly the six the cockpit displays):
    S0_NOMINAL                  nominal monitoring
    S1_EXERTION_COMPENSATED     Gate 2 blocked an exercise false alarm
    S2_ACTIVE_SENSING_HOLD      Gate 3 held escalation, or evidence is unknown -> crew exam
    S3_CREW_COUNTERMEASURE      onboard crew countermeasure / recheck loop
    S4_SURGEON_ESCALATED        packet queued for the flight surgeon
    S4_SURGEON_ACKNOWLEDGED     surgeon receipt recorded for this finding
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

S0 = "S0_NOMINAL"
S1 = "S1_EXERTION_COMPENSATED"
S2 = "S2_ACTIVE_SENSING_HOLD"
S3 = "S3_CREW_COUNTERMEASURE"
S4 = "S4_SURGEON_ESCALATED"
S4_ACK = "S4_SURGEON_ACKNOWLEDGED"

STAGES: tuple[str, ...] = (S0, S1, S2, S3, S4, S4_ACK)

STAGE_LABELS: dict[str, str] = {
    S0: "S0: NOMINAL MONITORING",
    S1: "S1: EXERTION COMPENSATED — FALSE ALARM BLOCKED",
    S2: "S2: ACTIVE SENSING HOLD — STALE EVIDENCE",
    S3: "S3: ONBOARD CREW COUNTERMEASURE",
    S4: "S4: FLIGHT SURGEON ESCALATION QUEUED",
    S4_ACK: "S4: FLIGHT SURGEON ACKNOWLEDGED",
}

STAGE_TONES: dict[str, str] = {
    S0: "nominal", S1: "teal", S2: "watch", S3: "orange", S4: "critical", S4_ACK: "critical",
}

# Demo routing table. Organ systems whose findings the demo protocol lets the crew handle
# onboard first. Everything else that reaches ALERT goes to the flight surgeon.
CREW_FIRST_SYSTEMS: frozenset[str] = frozenset({"metabolic", "brain", "bones"})
SURGEON_SYSTEMS: frozenset[str] = frozenset({"head-eyes", "heart", "chest-immune"})

ROUTING_LABEL = ("DEMO routing table, not a validated clinical triage protocol. "
                 "Organ severity badges are unaffected by routing.")

# Triage tier follows the stage so the banner and the triage card can never disagree.
STAGE_TRIAGE: dict[str, str] = {
    S0: "NOMINAL", S1: "WATCH", S2: "CREW", S3: "CREW", S4: "SURGEON", S4_ACK: "SURGEON",
}


@dataclass
class WorkflowRecord:
    """Persisted lifecycle state for one case."""

    stage: str = S0
    since_mission_t_s: float = 0.0
    requested_exam: str | None = None
    finding_fingerprint: str | None = None
    acknowledged_fingerprint: str | None = None
    reason: str = "initial nominal monitoring"
    updated_at: str = ""
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "since_mission_t_s": self.since_mission_t_s,
                "requested_exam": self.requested_exam,
                "finding_fingerprint": self.finding_fingerprint,
                "acknowledged_fingerprint": self.acknowledged_fingerprint,
                "reason": self.reason, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WorkflowRecord":
        if not data:
            return cls()
        return cls(stage=data.get("stage", S0),
                   since_mission_t_s=float(data.get("since_mission_t_s", 0.0)),
                   requested_exam=data.get("requested_exam"),
                   finding_fingerprint=data.get("finding_fingerprint"),
                   acknowledged_fingerprint=data.get("acknowledged_fingerprint"),
                   reason=data.get("reason", ""), updated_at=data.get("updated_at", ""))


def fingerprint(systems: list[str], flags: list[str], gate_state: str) -> str:
    """Stable identity of the *finding*, not of the frame.

    Two consecutive frames with the same alerting systems and the same non-rate flags are
    the same finding, so the surgeon is paged once and an acknowledgement stays valid. A
    genuinely new finding produces a new fingerprint and escalates again.
    """
    payload = {"systems": sorted(set(systems)), "flags": sorted(set(flags)), "gate": gate_state}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _requested_exam(gates: list[dict[str, Any]], active_top: str | None) -> str | None:
    for gate in gates:
        if gate.get("gate") == 3 and gate.get("outcome") == "HOLD":
            exam = (gate.get("evidence") or {}).get("requested_exam")
            if exam:
                return str(exam)
    return active_top


def resolve(frame: dict[str, Any] | None, organs: list[dict[str, Any]],
            record: WorkflowRecord, *, active_top: str | None = None) -> tuple[str, str, str | None, str | None]:
    """Return (stage, reason, requested_exam, finding_fingerprint). Pure.

    Precedence is fixed and documented:
      1. no frame / unknown signal      -> S2 (never green on missing evidence)
      2. non-rate finding               -> S4 (never suppressed, never held)
      3. Gate 3 HOLD                    -> S2 with the exact requested exam
      4. surgeon-routed organ ALERT     -> S4
      5. Gate 2 BLOCK                   -> S1
      6. rate alarm from the gate       -> S4
      7. crew-routed ALERT / any WATCH  -> S3
      8. otherwise                      -> S0
    """
    gates = (frame or {}).get("gates", []) or []
    flags = list((frame or {}).get("non_rate_flags", []) or [])
    gate_state = str((frame or {}).get("state", "UNKNOWN"))
    alerting = [o["system"] for o in organs if o.get("status") == "ALERT"]
    watching = [o["system"] for o in organs if o.get("status") == "WATCH"]
    fp = fingerprint(alerting, flags, gate_state) if (alerting or flags) else None

    if frame is None or gate_state in {"UNKNOWN", "SENSOR_ISSUE"}:
        return S2, "signal quality or telemetry unavailable; crew check requested before any assessment", "sensor", None
    if flags:
        return S4, "non-rate finding present; exercise filter and staleness hold do not apply", None, fp
    for gate in gates:
        if gate.get("gate") == 3 and gate.get("outcome") == "HOLD":
            return S2, str(gate.get("reason", "stale evidence held")), _requested_exam(gates, active_top), fp
    surgeon_organs = [s for s in alerting if s in SURGEON_SYSTEMS]
    if surgeon_organs:
        return S4, "alert-level demo rule in " + ", ".join(sorted(surgeon_organs)), None, fp
    if (frame or {}).get("suppressed"):
        return S1, "Gate 2 explained the rate by this person's activity scale", None, None
    if gate_state == "SURGEON_ALERT":
        return S4, "deterministic gate raised a rate alarm that context did not explain", None, fp
    if alerting or watching:
        systems = sorted(set(alerting) | set(watching))
        return S3, "onboard crew countermeasure/recheck for " + ", ".join(systems), _requested_exam(gates, active_top), fp
    if gate_state == "CREW_CHECK":
        return S2, "crew check requested by the gate", _requested_exam(gates, active_top), None
    return S0, "no demo rule or gate raised a finding", None, None


def apply(record: WorkflowRecord, frame: dict[str, Any] | None, organs: list[dict[str, Any]],
          *, mission_t_s: float, now: str, active_top: str | None = None) -> dict[str, Any] | None:
    """Advance the record in place. Returns a transition dict when the stage changed.

    An acknowledged finding stays acknowledged while the same fingerprint persists; a new
    fingerprint re-escalates. This is what makes the acknowledgement durable across ticks.
    """
    stage, reason, exam, fp = resolve(frame, organs, record, active_top=active_top)
    if stage == S4 and fp is not None and fp == record.acknowledged_fingerprint:
        stage, reason = S4_ACK, "surgeon receipt already recorded for this finding"
    previous = record.stage
    changed = previous != stage
    if changed:
        record.stage = stage
        record.since_mission_t_s = mission_t_s
    record.reason = reason
    record.requested_exam = exam
    record.finding_fingerprint = fp
    record.updated_at = now
    if not changed:
        return None
    transition = {"from_stage": previous, "to_stage": stage, "reason": reason,
                  "mission_t_s": round(mission_t_s, 3), "ts": now}
    record.transitions.append(transition)
    return transition


def acknowledge(record: WorkflowRecord, *, packet_fingerprint: str | None, mission_t_s: float,
                now: str) -> dict[str, Any]:
    """Record a surgeon acknowledgement. Only valid from an escalated stage."""
    if record.stage not in {S4, S4_ACK}:
        raise ValueError(f"case is in {record.stage}; only {S4} can be acknowledged")
    previous = record.stage
    record.stage = S4_ACK
    record.acknowledged_fingerprint = packet_fingerprint or record.finding_fingerprint
    record.reason = "flight surgeon acknowledgement receipt recorded"
    record.updated_at = now
    transition = {"from_stage": previous, "to_stage": S4_ACK,
                  "reason": record.reason, "mission_t_s": round(mission_t_s, 3), "ts": now}
    record.transitions.append(transition)
    return transition


def banner(record: WorkflowRecord) -> dict[str, Any]:
    return {"stage": record.stage, "label": STAGE_LABELS[record.stage],
            "tone": STAGE_TONES[record.stage], "reason": record.reason,
            "requested_exam": record.requested_exam,
            "since_mission_t_s": record.since_mission_t_s,
            "acknowledged": record.stage == S4_ACK,
            "action_required": record.stage == S2,
            "routing_label": ROUTING_LABEL,
            "recent_transitions": record.transitions[-8:]}
