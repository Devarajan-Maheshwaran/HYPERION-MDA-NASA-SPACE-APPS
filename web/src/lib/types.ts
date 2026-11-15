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
