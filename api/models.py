"""Pydantic contract for the workstation API.

Every measurement carries an explicit status. UNKNOWN / STALE / NOT_AVAILABLE / FAILED
must never be rendered as healthy by the client; the web layer enforces this and a
Vitest test asserts the colour mapping.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Lane = Literal["LAB DATA", "SIMULATED", "INJECTED", "RECORDED-NON-ASTRONAUT", "NONE"]
Status = Literal["OK", "UNKNOWN", "NOT_AVAILABLE", "STALE", "FAILED"]
Outcome = Literal["PASS", "BLOCK", "HOLD", "UNKNOWN"]
Role = Literal["crew", "flight-surgeon", "ops", "researcher"]
Habitat = Literal["Space Station (0g)", "Transit Ship", "Lunar Base (0.16g)", "Rover"]
WorkflowState = Literal[
    "NOMINAL", "SENSOR_ISSUE", "CONTEXT_COMPENSATED", "CREW_CHECK", "SURGEON_ALERT", "UNKNOWN"
]
OrganStatus = Literal["NOMINAL", "WATCH", "ALERT", "UNKNOWN", "NOT_AVAILABLE"]

DISCLAIMER = "Demo thresholds, not clinically validated. Not a medical device."


class Envelope(BaseModel):
    """Fields every response carries so the UI can never show unlabelled data."""

    lane: Lane = "NONE"
    provenance: str = ""
    generated_at: str = ""
    disclaimer: str = DISCLAIMER


class GateVerdict(BaseModel):
    gate: Literal[1, 2, 3]
    outcome: Outcome
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class SqReading(BaseModel):
    kurtosis: float | None = None
    slew: float | None = None
    calibrated: bool = False


class Frame(BaseModel):
    t_s: float
    lane: Lane
    subject_id: str
    habitat: Habitat
    hr_bpm: float | None = None
    hr_status: Status = "UNKNOWN"
    activity_norm: float | None = None
    activity_unit: str = "per-person rest scale (dimensionless)"
    sqi: SqReading = Field(default_factory=SqReading)
    gates: list[GateVerdict] = Field(default_factory=list)
    residual_bpm: float | None = None
    band_upper: float | None = None
    band_lower: float | None = None
    band_label: str = "demo band (empirical residual quantile)"
    state: WorkflowState = "UNKNOWN"
    suppressed: bool = False
    suppression_reason: str | None = None
    non_rate_flags: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    scenario_id: str | None = None


class Calibration(BaseModel):
    subject_id: str
    calibrated: bool = False
    source: str = ""
    lane: Lane = "NONE"
    n_windows: int = 0
    rest_hr_median: float | None = None
    rest_hr_scale: float | None = None
    rest_activity_median: float | None = None
    rest_activity_scale: float | None = None
    residual_q95: float | None = None
    kurtosis_low: float | None = None
    kurtosis_high: float | None = None
    slew_high: float | None = None
    created_at: str = ""
    note: str = ""


class Subject(BaseModel):
    subject_id: str
    label: str
    lane: Lane
    calibration: Calibration


class OrganReading(BaseModel):
    system: str
    label: str
    status: OrganStatus
    indicator: str
    value: float | None = None
    unit: str = ""
    demo_threshold: str = ""
    threshold_label: str = "DEMO THRESHOLD — not a validated clinical limit"
    hazard: str = ""
    staleness_tau: float | None = None
    age_hours: float | None = None
    tau_basis: str = "wall-clock hours"
    mission_age_s: float | None = None
    z_score: float | None = None
    baseline_note: str = "No personal baseline for this indicator; z_t not available."
    action: str = ""
    evidence: str = ""


class ManualCheck(BaseModel):
    subject_id: str
    kind: Literal["bp", "glucose", "temperature", "sleep", "mood", "onsd", "pvt"]
    systolic: float | None = None
    diastolic: float | None = None
    value: float | None = None
    unit: str = ""
    recorded_at: str = ""
    lane: Lane = "INJECTED"
    source: str = "crew entry (demo-grade, unverified)"
    # Mission-clock stamp for the live cockpit's compressed staleness demo. None on the
    # legacy/manual path, which keeps using wall-clock age exactly as before.
    mission_t_s: float | None = None


class Alert(BaseModel):
    alert_id: str
    subject_id: str
    created_at: str
    lane: Lane
    state: WorkflowState
    severity: Literal["HOLD", "ALERT"]
    reason: str
    actions: list[str] = Field(default_factory=list)
    acknowledged_by: str | None = None
    acknowledged_at: str | None = None
    ack_note: str | None = None
    non_rate_flags: list[str] = Field(default_factory=list)


class AuditEntry(BaseModel):
    seq: int
    ts: str
    event: str
    role: str
    subject_id: str
    lane: Lane
    detail: dict[str, Any] = Field(default_factory=dict)
    prev_sha256: str
    sha256: str


class LaneInfo(BaseModel):
    lane: Lane
    available: bool
    detail: str
    provenance: str


class ScenarioInfo(BaseModel):
    scenario_id: str
    label: str
    purpose: str
    lane: Lane
    duration_s: float
    expected: str
