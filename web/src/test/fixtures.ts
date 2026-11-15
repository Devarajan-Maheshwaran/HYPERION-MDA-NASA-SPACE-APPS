import type { Comms, Lifecycle, OrganReading, OutboxPacket, ReplayLane, WorkstationState } from '../lib/types';

const organs: OrganReading[] = [
  ['head-eyes', 'Head & Eyes', 4.6, 'mm', 'onsd = 4.6 mm'],
  ['heart', 'Heart & Vessels', 122, 'mmHg', 'bp = 122/78 mmHg'],
  ['chest-immune', 'Chest & Immune', 36.8, 'degC', 'temperature = 36.8 degC'],
  ['metabolic', 'Metabolic & Gut', 92, 'mg/dL', 'glucose = 92 mg/dL'],
  ['bones', 'Bones & Muscles', 1800, 'mL', 'water 1800 mL / ARED 30 min (crew log)'],
  ['brain', 'Brain & Sleep', 290, 'ms', 'pvt = 290 ms'],
].map(([system, label, value, unit, indicator]) => ({
  system: system as string, label: label as string, status: 'NOMINAL', indicator: indicator as string,
  value: value as number, unit: unit as string, demo_threshold: 'DEMO threshold',
  threshold_label: 'DEMO THRESHOLD — not a validated clinical limit', hazard: 'Spaceflight hazard',
  staleness_tau: 0.99, age_hours: 0.05, z_score: null, baseline_note: 'No personal baseline.',
  action: 'Repeat measurement', evidence: 'Crew-entered demo check.',
}));

export function makeLifecycle(overrides: Partial<Lifecycle> = {}): Lifecycle {
  return {
    stage: 'S0_NOMINAL', label: 'S0 · NOMINAL MONITORING', tone: 'nominal',
    reason: 'No demo rule or gate raised a finding.', requested_exam: null,
    since_mission_t_s: 0, acknowledged: false, action_required: false,
    routing_label: 'DEMO routing table, not a validated triage standard',
    recent_transitions: [], ...overrides,
  };
}

export function makePacket(overrides: Partial<OutboxPacket> = {}): OutboxPacket {
  return {
    packet_id: 'pkt-abcdefgh', case_id: 'case-default', created_at: '2026-11-14T12:00:00.000Z',
    comms_state: 'IN_TRANSIT', habitat: 'station', delay_s: 0.2, countdown_s: 0.1,
    finding: 'Cabin CO2 = 4.2 mmHg (SIMULATED)', fingerprint: 'abc123def4567890',
    sbar: {
      situation: 'S4 escalation for demo-crew-1 at T+0002s.',
      background: 'Lane SIMULATED. Habitat Orbital Station.',
      assessment: 'Head & Eyes ALERT. Gate 3 HOLD.',
      recommendation: 'Contact flight surgeon. Repeat measurement.',
    },
    delivered_at: null, acknowledged_at: null, receipt: null, ...overrides,
  };
}

export function makeComms(overrides: Partial<Comms> = {}): Comms {
  return {
    profile: { key: 'station', label: 'Orbital Station', delay_s: 0.2,
               real_world_note: 'Near-real-time relay; demo timer, not a link budget.' },
    blackout: false, packets: [], ...overrides,
  };
}

export function makeReplay(overrides: Partial<ReplayLane> = {}): ReplayLane {
  return {
    active: false, participant: null, available: true, lane: 'RECORDED-NON-ASTRONAUT',
    provenance: 'PhysioNet Wrist PPG During Exercise v1.0.0 · committed M6 windows',
    participants: ['s1', 's2', 's3', 's4', 's5', 's6', 's8', 's9'],
    n_windows: 3332, window_s: 8, replay_rate_hz: 1,
    time_compressed: '8 s recorded window advanced once per mission second (time-compressed replay).',
    active_windows: 0, window_index: null, ...overrides,
  };
}

export function makeState(overrides: Partial<WorkstationState> = {}): WorkstationState {
  const base: WorkstationState = {
    lane: 'SIMULATED', provenance: 'SIMULATED MISSION TELEMETRY FALLBACK', generated_at: '2026-11-14T12:00:00.000Z',
    disclaimer: 'Demo thresholds, not clinically validated. Not a medical device.',
    habitat: 'station', habitat_label: 'Orbital Space Station (0g, Delay: 0.1s)',
    habitat_options: [
      { key: 'station', label: 'Orbital Space Station (0g, Delay: 0.1s)' },
      { key: 'transit', label: 'Deep-Space Transit Ship (0g, Delay: 20 min)' },
      { key: 'lunar', label: 'Lunar Base (0.16g, Delay: 1.3s)' },
      { key: 'rover', label: 'Surface Rover (EVA High Exertion)' },
    ],
    data_source_mode: 'SIMULATED_FALLBACK', telemetry_mode: 'SIMULATED_FALLBACK',
    provenance_banner: 'SIMULATED MISSION TELEMETRY FALLBACK (Physics-Guided Physiological Scenario Engine — Explicitly Labeled Non-Flight Simulation)',
    subject_id: 'demo-crew-1', scenario_key: 'nominal-orbital', running: true, t_s: 2,
    case_id: 'case-default', session_id: 'session-demo',
    clock: { hz: 1, period_s: 1, running: true, mission_seconds_per_demo_hour: 60,
             tau_basis: 'mission clock, demo compression: 60 mission seconds = 1 hour of evidence age' },
    lifecycle: makeLifecycle(),
    comms: makeComms(),
    replay: makeReplay(),
    demo_scenarios: [
      { id: 'nominal-orbital', label: '1. Nominal 0g' }, { id: 'eva-ared-exercise', label: '2. Exercise False-Alarm Test' },
      { id: 'sans-stale-eye', label: '3. SANS + Stale Eye Scan' }, { id: 'spe-radiation', label: '4. Solar Radiation Spike' },
      { id: 'glycemic-circadian', label: '5. Glycemic & Sleep Drift' },
    ],
    sources: {
      lab: { lane: 'LAB DATA', available: true, detail: 'OSD-575 SHA-256 verified', provenance: 'NASA OSDR' },
      goes: {
        available: false, detail: 'GOES live unreachable; no cached flux', url: 'https://www.swpc.noaa.gov/',
        channels: {}, dose_mgy_day: null, unit: 'pfu', unit_long: 'particles / (cm^2 * s * sr)',
        cache_age_s: null, latest_sample: null,
        quantity: 'integral proton flux (environmental indicator, not tissue dose)',
        dose_note: 'GOES integral proton flux is an environmental space-weather indicator in pfu, NOT absorbed tissue dose in mGy/day.',
      },
      wearable: { available: false, detail: 'WESAD NO-GO', features: {}, wesad: 'NO-GO' },
    },
    organs,
    frame: {
      t_s: 2, lane: 'SIMULATED', subject_id: 'demo-crew-1', habitat: 'Space Station (0g)', hr_bpm: 69, hr_status: 'OK',
      activity_norm: 1.38, activity_unit: 'per-person rest scale', sqi: { kurtosis: 3.4, slew: 1.2, calibrated: true },
      gates: [], residual_bpm: -15.8, band_upper: -13.5, band_lower: -18.2, band_label: 'demo residual band',
      state: 'NOMINAL', suppressed: false, suppression_reason: null, non_rate_flags: [], actions: ['Repeat measurement'], scenario_id: 'rest-nominal',
    },
    history: [
      { t_s: 0, hr_bpm: 68, residual_bpm: -16, activity_norm: 1.2, enmo_g: 0.02, co2_mmhg: 2.5, band_upper: -13.5, band_lower: -18.2, conformal_upper: 86, state: 'NOMINAL', suppressed: false },
      { t_s: 1, hr_bpm: 69, residual_bpm: -15.8, activity_norm: 1.3, enmo_g: 0.02, co2_mmhg: 2.5, band_upper: -13.5, band_lower: -18.2, conformal_upper: 86, state: 'NOMINAL', suppressed: false },
    ],
    gates: [
      { gate: 1, outcome: 'PASS', reason: 'within calibrated sensor envelope', evidence: { kurtosis: 3.4, slew: 1.2, calibrated: true } },
      { gate: 2, outcome: 'PASS', reason: 'rate below the demo alert band; nothing to block', evidence: { hr_bpm: 69, residual_bpm: -15.8, activity_norm: 1.38 } },
      { gate: 3, outcome: 'PASS', reason: 'no rate alarm to hold', evidence: { min_tau: 0.99, requested_exam: null } },
    ],
    conformal: { prediction: 84.9, q_hat: 1.55, upper: 86.46, alpha: 0.1, n_calibration: 60, label: 'demo split-conformal quantile; no coverage guarantee', sigma_epistemic: null, sigma_note: 'MC-dropout not implemented.' },
    active_sensing: { ranked: [{ exam: 'pvt', label: '15 s click PVT', tau: 0.99, score: 0.0034, cost_min: 0.25 }], top: { exam: 'pvt', label: '15 s click PVT', tau: 0.99, score: 0.0034, cost_min: 0.25 }, label: 'demo active-sensing heuristic' },
    triage: { tier: 'NOMINAL', why: 'No demo rule or gate raised a finding.', crew_or_surgeon: 'Can be handled by crew onboard', actions: ['Repeat measurement'], steps: ['Read the lane/provenance badge before acting.', 'Repeat the indicated measurement with the listed crew tool.', 'If the finding persists or escalates, contact the flight surgeon.'], label: 'DEMO triage, not NASA-STD-3001 compliance and not treatment advice' },
    overlays: { enmo_g: 0.02, co2_mmhg: 2.5, proton_mgy_day: 0.3, water_ml: 1800, ared_min: 30, label: 'SIMULATED reference channels' },
    countermeasure_flags: { water_low: false, ared_low: false, label: 'DEMO countermeasure flags' },
    readiness: { streak_days: 1, days_logged: 1, note: 'Engagement counter only. No clinical or readiness meaning.', freshness_tau_avg: 0.99, badges: [{ id: 'pvt', label: 'Alertness', unlocked: true }] },
    ml_benchmark: {
      provenance: 'M6 measured offline; FL panel is toy simulation.',
      measured_m6_hr: [{ model: 'A0', mae_bpm: 24.177234, ci_low: 12.00258, ci_high: 41.169426 }],
      not_implemented: ['PyTorch HyperionCoreNet', 'Opacus DP-SGD'],
      requested_benchmarks: [{ model: 'sklearn LogisticRegression', status: 'NOT_IMPLEMENTED', metric: null }],
      fl_simulation: { n_clients: 4, rounds: 3, global_weights: [0.74, 0.77, -0.02], label: 'FL SIMULATION' },
      cosine_median_demo: { caught: true, silo_index: 1, rejected: [{ silo_index: 1, cosine: 0.719 }], label: 'SIMULATED bit-flip in silo 2' },
    },
    audit: {
      verification: { ok: true, entries: 1, reason: 'chain intact' },
      entries: [{ seq: 0, ts: '2026-11-14T12:00:00.000Z', event: 'scenario.start', role: 'crew', subject_id: 'demo-crew-1', lane: 'SIMULATED', detail: { scenario_id: 'nominal-orbital' }, prev_sha256: '0'.repeat(64), sha256: 'a'.repeat(64) }],
      contract: 'HealthAudit.sol reference only — NOT deployed, NOT on-chain', badge: 'ZERO RAW PRIVATE HEALTH DATA ON-CHAIN',
    },
  };
  return { ...base, ...overrides };
}

export function exerciseState(): WorkstationState {
  const state = makeState({ scenario_key: 'eva-ared-exercise', habitat: 'rover' });
  state.frame = { ...state.frame!, hr_bpm: 148, state: 'CONTEXT_COMPENSATED', suppressed: true };
  state.gates = state.gates.map((gate) => gate.gate === 2 ? { ...gate, outcome: 'BLOCK', reason: 'rate explained by this person’s activity scale', evidence: { ...gate.evidence, hr_bpm: 148, activity_norm: 16.4 } } : gate);
  state.overlays = { ...state.overlays, enmo_g: 0.31 };
  state.triage = { ...state.triage, tier: 'WATCH', why: 'Gate 2 blocked an exercise false alarm; movement explains the rate.' };
  state.lifecycle = makeLifecycle({ stage: 'S1_EXERTION_COMPENSATED', label: 'S1 · EXERTION COMPENSATED',
    tone: 'teal', reason: 'Gate 2 explained this rate by the personal activity scale.' });
  return state;
}

export function sansState(): WorkstationState {
  const state = makeState({ scenario_key: 'sans-stale-eye' });
  state.gates = state.gates.map((gate) => gate.gate === 3 ? { ...gate, outcome: 'HOLD', reason: 'cabin CO2 elevated and eye scan stale; request guided ONSD ultrasound', evidence: { ...gate.evidence, requested_exam: 'ultrasound', min_tau: 0.18 } } : gate);
  state.triage = { ...state.triage, tier: 'CREW', why: 'Gate 3 held the ground alarm. Run the guided eye ultrasound tab next.' };
  state.active_sensing = { ...state.active_sensing, top: { exam: 'onsd', label: 'Guided eye ultrasound (ONSD mm)', tau: 0.18, score: 3.2, cost_min: 2 } };
  state.lifecycle = makeLifecycle({ stage: 'S2_ACTIVE_SENSING_HOLD', label: 'S2 · ACTIVE SENSING HOLD',
    tone: 'watch', reason: 'Cabin CO2 elevated and the eye scan is stale.',
    requested_exam: 'ultrasound', action_required: true });
  return state;
}

export function escalatedState(): WorkstationState {
  const state = sansState();
  state.scenario_key = 'spe-radiation';
  state.lifecycle = makeLifecycle({ stage: 'S4_SURGEON_ESCALATED', label: 'S4 · SURGEON ESCALATED',
    tone: 'critical', reason: 'A demo alert rule was crossed; SBAR packet queued.' });
  state.triage = { ...state.triage, tier: 'SURGEON', why: 'Escalated to the flight surgeon.' };
  state.comms = makeComms({ packets: [makePacket()] });
  return state;
}

export function deliveredState(): WorkstationState {
  const state = escalatedState();
  state.comms = makeComms({ packets: [makePacket({ comms_state: 'DELIVERED', countdown_s: null,
    delivered_at: '2026-11-14T12:00:01.000Z' })] });
  return state;
}

export function acknowledgedState(): WorkstationState {
  const state = escalatedState();
  state.lifecycle = makeLifecycle({ stage: 'S4_SURGEON_ACKNOWLEDGED', label: 'S4 · SURGEON ACKNOWLEDGED',
    tone: 'critical', reason: 'Flight surgeon acknowledged this finding.', acknowledged: true });
  state.comms = makeComms({ packets: [makePacket({
    comms_state: 'ACKNOWLEDGED', countdown_s: null,
    delivered_at: '2026-11-14T12:00:01.000Z', acknowledged_at: '2026-11-14T12:00:02.000Z',
    receipt: { receipt_id: 'rcpt-abcdefgh', packet_id: 'pkt-abcdefgh', role: 'flight-surgeon',
               directive: 'Recheck ONSD in 30 minutes.', acknowledged_at: '2026-11-14T12:00:02.000Z',
               sha256: 'b'.repeat(64) },
  })] });
  return state;
}

export function replayState(): WorkstationState {
  // Matches the API: recorded replay is real (non-astronaut) data, not a simulation.
  const state = makeState({ scenario_key: null, telemetry_mode: 'RECORDED_REPLAY',
    data_source_mode: 'REAL_EMPIRICAL', lane: 'RECORDED-NON-ASTRONAUT',
    provenance_banner: 'RECORDED HUMAN REPLAY · NON-ASTRONAUT · PhysioNet exercise data' });
  state.replay = makeReplay({ active: true, participant: 's1', active_windows: 868, window_index: 12 });
  return state;
}
