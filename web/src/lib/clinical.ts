import type { GateVerdict, HabitatKey, OrganReading, OrganStatus, WorkstationState } from './types';

export type Tone = 'nominal' | 'watch' | 'critical' | 'neutral';

export const HABITATS: Array<{ key: HabitatKey; label: string; delay: string }> = [
  { key: 'station', label: 'Orbital Station (0g)', delay: '0.1 s' },
  { key: 'transit', label: 'Transit Ship (0g · 20m Delay)', delay: '20 min' },
  { key: 'lunar', label: 'Lunar Base (0.16g)', delay: '1.3 s' },
  { key: 'rover', label: 'Surface Rover (EVA)', delay: '—' },
];

export const SCENARIOS = [
  { id: 'nominal-orbital', label: 'Nominal Rest' },
  { id: 'eva-ared-exercise', label: 'Exercise Bout Blocks False Alarm' },
  { id: 'sans-stale-eye', label: 'High CO₂ + SANS Eye Risk' },
  { id: 'spe-radiation', label: 'Solar Radiation Spike' },
  { id: 'glycemic-circadian', label: 'Blood Sugar & Sleep Drift' },
] as const;

export function organTone(status: OrganStatus): Tone {
  if (status === 'NOMINAL') return 'nominal';
  if (status === 'WATCH') return 'watch';
  if (status === 'ALERT') return 'critical';
  return 'neutral';
}

export function gateTone(gate: GateVerdict | undefined): Tone {
  if (!gate || gate.outcome === 'UNKNOWN') return 'neutral';
  if (gate.outcome === 'PASS') return 'nominal';
  return 'watch'; // BLOCK and HOLD are protective interventions, not critical findings.
}

export function triageTone(tier: WorkstationState['triage']['tier']): Tone {
  if (tier === 'NOMINAL') return 'nominal';
  if (tier === 'SURGEON') return 'critical';
  if (tier === 'WATCH' || tier === 'CREW') return 'watch';
  return 'neutral';
}

export const TRIAGE_LABELS: Record<WorkstationState['triage']['tier'], string> = {
  NOMINAL: 'NOMINAL',
  WATCH: 'ONBOARD COUNTERMEASURE',
  CREW: 'PERFORM 2-MIN CREW CHECK',
  SURGEON: 'ESCALATE TO FLIGHT SURGEON',
  UNKNOWN: 'ASSESSMENT UNKNOWN',
};

export function freshnessPercent(tau: number | null | undefined): number | null {
  if (tau === null || tau === undefined || !Number.isFinite(tau)) return null;
  return Math.round(Math.max(0, Math.min(1, tau)) * 100);
}

export function organSummary(organ: OrganReading): string {
  if (organ.status === 'NOT_AVAILABLE') return 'No measurement has been logged for this system yet.';
  if (organ.status === 'UNKNOWN') return 'The latest reading is stale or incomplete, so it cannot support a current assessment.';
  if (organ.status === 'ALERT') return 'A demo alert rule was crossed; this needs flight-surgeon review, not self-treatment.';
  if (organ.status === 'WATCH') return 'A watch-level demo rule is active, so repeat the indicated check before drawing a conclusion.';
  const summaries: Record<string, string> = {
    'head-eyes': 'The latest eye and cabin-context checks are below this prototype’s demo alert rules.',
    heart: 'The latest heart and blood-pressure checks are below this prototype’s demo alert rules.',
    'chest-immune': 'The latest temperature and radiation-context checks are below this prototype’s demo alert rules.',
    metabolic: 'The latest glucose check is below this prototype’s demo impaired-fasting band.',
    bones: 'The logged hydration and exercise countermeasures meet this prototype’s demo references.',
    brain: 'The latest sleep and reaction-time checks are within this prototype’s demo rules.',
  };
  return summaries[organ.system] ?? 'No demo rule is currently breached for this system.';
}

export function recommendedTool(state: WorkstationState): 'pvt' | 'ultrasound' | 'vitals' {
  const gate3 = state.gates.find((gate) => gate.gate === 3);
  if (gate3?.evidence['requested_exam'] === 'ultrasound') return 'ultrasound';
  const exam = state.active_sensing.top?.exam;
  if (exam === 'onsd') return 'ultrasound';
  if (exam === 'pvt') return 'pvt';
  return 'vitals';
}

export function commsDelay(habitat: HabitatKey): string {
  return HABITATS.find((item) => item.key === habitat)?.delay ?? '—';
}

export function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  const upper = sorted[middle];
  if (upper === undefined) return null;
  if (sorted.length % 2) return upper;
  const lower = sorted[middle - 1];
  return lower === undefined ? null : (lower + upper) / 2;
}
