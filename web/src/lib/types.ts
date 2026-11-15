// Mirrors api/models.py. Kept in sync by hand; the smoke test checks the shapes.

export type Lane = 'LAB DATA' | 'SIMULATED' | 'INJECTED' | 'RECORDED-NON-ASTRONAUT' | 'NONE';
export type Status = 'OK' | 'UNKNOWN' | 'NOT_AVAILABLE' | 'STALE' | 'FAILED';
export type Outcome = 'PASS' | 'BLOCK' | 'HOLD' | 'UNKNOWN';
export type Role = 'crew' | 'flight-surgeon' | 'ops' | 'researcher';
export type Habitat = 'Space Station (0g)' | 'Transit Ship' | 'Lunar Base (0.16g)' | 'Rover';
export type WorkflowState =
  | 'NOMINAL'
  | 'SENSOR_ISSUE'
  | 'CONTEXT_COMPENSATED'
  | 'CREW_CHECK'
  | 'SURGEON_ALERT'
  | 'UNKNOWN';
export type OrganStatus = 'NOMINAL' | 'WATCH' | 'ALERT' | 'UNKNOWN' | 'NOT_AVAILABLE';

export const DISCLAIMER = 'Demo thresholds, not clinically validated. Not a medical device.';

export const ALLOWED_ACTIONS = [
  'Repeat measurement',
  'Rest and recheck',
  'Check sensor',
  'Contact flight surgeon',
] as const;
export type AllowedAction = (typeof ALLOWED_ACTIONS)[number];

export interface Envelope {
  lane: Lane;
  provenance: string;
  generated_at: string;
  disclaimer: string;
}

export interface GateVerdict {
  gate: 1 | 2 | 3;
  outcome: Outcome;
  reason: string;
  evidence: Record<string, unknown>;
}

export interface SqReading {
  kurtosis: number | null;
  slew: number | null;
  calibrated: boolean;
}

export interface Frame {
  t_s: number;
  lane: Lane;
  subject_id: string;
  habitat: Habitat;
  hr_bpm: number | null;
  hr_status: Status;
  activity_norm: number | null;
  activity_unit: string;
  sqi: SqReading;
  gates: GateVerdict[];
  residual_bpm: number | null;
  band_upper: number | null;
  band_lower: number | null;
  band_label: string;
  state: WorkflowState;
  suppressed: boolean;
  suppression_reason: string | null;
  non_rate_flags: string[];
  actions: string[];
  scenario_id: string | null;
}

export interface Calibration {
  subject_id: string;
  calibrated: boolean;
  source: string;
  lane: Lane;
  n_windows: number;
  rest_hr_median: number | null;
  rest_hr_scale: number | null;
  rest_activity_median: number | null;
  rest_activity_scale: number | null;
  residual_q95: number | null;
  kurtosis_low: number | null;
  kurtosis_high: number | null;
  slew_high: number | null;
  created_at: string;
  note: string;
}

export interface Subject {
  subject_id: string;
  label: string;
  lane: Lane;
  calibration: Calibration;
}

export interface OrganReading {
  system: string;
  label: string;
  status: OrganStatus;
  indicator: string;
  value: number | null;
  unit: string;
  demo_threshold: string;
  threshold_label: string;
  hazard: string;
  staleness_tau: number | null;
  age_hours: number | null;
  z_score?: number | null;
  baseline_note?: string;
  action: string;
  evidence: string;
}

export interface ManualCheck {
  subject_id: string;
  kind: 'bp' | 'glucose' | 'temperature' | 'sleep' | 'mood' | 'onsd' | 'pvt';
  systolic: number | null;
  diastolic: number | null;
  value: number | null;
  unit: string;
  recorded_at: string;
  lane: Lane;
  source: string;
}

export interface Alert {
  alert_id: string;
  subject_id: string;
  created_at: string;
  lane: Lane;
  state: WorkflowState;
  severity: 'HOLD' | 'ALERT';
  reason: string;
  actions: string[];
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  ack_note: string | null;
  non_rate_flags: string[];
}

export interface AuditEntry {
  seq: number;
  ts: string;
  event: string;
  role: string;
  subject_id: string;
  lane: Lane;
  detail: Record<string, unknown>;
  prev_sha256: string;
  sha256: string;
}

export interface LaneInfo {
  lane: Lane;
  available: boolean;
  detail: string;
  provenance: string;
}

export interface ScenarioInfo {
  scenario_id: string;
  label: string;
  purpose: string;
  lane: Lane;
  duration_s: number;
  expected: string;
}

export interface Channel {
  channel_id: string;
  label: string;
  region: string;
  status: string;
  lane: string;
  source: string;
  sampling: string;
  unit: string;
  note: string;
}

export interface Readiness {
  streak_days: number;
  days_logged: number;
  note: string;
}

export interface SessionResponse extends Envelope {
  role: Role;
  subject_id: string;
  habitat: Habitat;
  subjects: Subject[];
  running: boolean;
  scenario_id: string | null;
  t_s: number;
  habitats: Habitat[];
  roles: Role[];
}

export interface StreamStateResponse extends Envelope {
  running: boolean;
  t_s: number;
  scenario_id: string | null;
  frame: Frame | null;
  history: Frame[];
}

export interface OrgansResponse extends Envelope {
  subject_id: string;
  organs: OrganReading[];
  readiness: Readiness;
  threshold_notice: string;
}

/* ---- unified live workstation (/api/state) ---- */

export type DataSourceMode = 'REAL_EMPIRICAL' | 'SIMULATED_FALLBACK';
export type TelemetryMode = DataSourceMode | 'NOT_AVAILABLE';
export type HabitatKey = 'station' | 'transit' | 'lunar' | 'rover';

export interface WorkstationHistoryPoint {
  t_s: number;
  hr_bpm: number | null;
  residual_bpm: number | null;
  activity_norm: number | null;
  enmo_g: number | null;
  co2_mmhg: number | null;
  band_upper: number | null;
  band_lower: number | null;
  conformal_upper: number | null;
  state: WorkflowState;
  suppressed: boolean;
}

export interface ActiveSensingExam {
  exam: string;
  label: string;
  tau: number | null;
  score: number;
  cost_min: number;
}

export interface WorkstationState extends Envelope {
  habitat: HabitatKey;
  habitat_label: string;
  habitat_options: Array<{ key: HabitatKey; label: string }>;
  data_source_mode: DataSourceMode;
  telemetry_mode: TelemetryMode;
  provenance_banner: string;
  subject_id: string;
  scenario_key: string | null;
  running: boolean;
  t_s: number;
  demo_scenarios: Array<{ id: string; label: string }>;
  sources: {
    lab: LaneInfo;
    goes: { available: boolean; detail?: string; url: string; channels: Record<string, unknown>; dose_mgy_day: number | null };
    wearable: { available: boolean; detail: string; features: Record<string, number | null>; wesad: string };
  };
  organs: OrganReading[];
  frame: Frame | null;
  history: WorkstationHistoryPoint[];
  gates: GateVerdict[];
  conformal: {
    prediction: number | null; q_hat: number | null; upper: number | null; alpha: number;
    n_calibration: number; label: string; sigma_epistemic: number | null; sigma_note: string;
  };
  active_sensing: { ranked: ActiveSensingExam[]; top: ActiveSensingExam | null; label: string };
  triage: {
    tier: 'NOMINAL' | 'WATCH' | 'CREW' | 'SURGEON' | 'UNKNOWN';
    why: string; crew_or_surgeon: string; actions: string[]; steps: string[]; label: string;
  };
  overlays: {
    enmo_g: number | null; co2_mmhg: number | null; proton_mgy_day: number | null;
    water_ml: number | null; ared_min: number | null; label: string;
  };
  countermeasure_flags: { water_low: boolean | null; ared_low: boolean | null; label: string };
  readiness: Readiness & { freshness_tau_avg: number | null; badges: Array<{ id: string; label: string; unlocked: boolean }> };
  ml_benchmark: {
    provenance: string;
    measured_m6_hr: Array<{ model: string; mae_bpm: number; ci_low: number | null; ci_high: number | null }>;
    not_implemented: string[];
    requested_benchmarks: Array<{ model: string; status: string; metric: string | null }>;
    fl_simulation: { n_clients: number; rounds: number; global_weights: number[]; label: string };
    cosine_median_demo: { caught: boolean; silo_index: number; rejected: Array<{ silo_index: number; cosine: number }>; label: string };
  };
  audit: {
    verification: { ok: boolean; entries: number; reason: string };
    entries: AuditEntry[];
    contract: string;
    badge: string;
  };
  caliper?: { x1: number; y1: number; x2: number; y2: number; px_per_mm: number; onsd_mm: number; retrobulbar_mm: number; note: string };
}
