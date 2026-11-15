// The honesty rules, in one place. Vitest asserts UNKNOWN is never green.

import type { Lane, OrganStatus, Outcome, Status, WorkflowState } from './types';

export type Tone = 'nominal' | 'watch' | 'alert' | 'unknown' | 'info';

const TONE_CLASS: Record<Tone, string> = {
  nominal: 'bg-nominal/15 text-nominal border-nominal/40',
  watch: 'bg-watch/15 text-watch border-watch/40',
  alert: 'bg-alert/15 text-alert border-alert/40',
  unknown: 'bg-slate-500/15 text-slate-400 border-slate-500/40',
  info: 'bg-sky-500/15 text-sky-300 border-sky-500/40',
};

export function toneClass(tone: Tone): string {
  return TONE_CLASS[tone];
}

/** Only an explicitly healthy, current, available reading may be green. */
export function organTone(status: OrganStatus): Tone {
  switch (status) {
    case 'NOMINAL':
      return 'nominal';
    case 'WATCH':
      return 'watch';
    case 'ALERT':
      return 'alert';
    case 'UNKNOWN':
    case 'NOT_AVAILABLE':
      return 'unknown';
  }
}

export function stateTone(state: WorkflowState): Tone {
  switch (state) {
    case 'NOMINAL':
      return 'nominal';
    case 'CONTEXT_COMPENSATED':
      return 'info';
    case 'CREW_CHECK':
    case 'SENSOR_ISSUE':
      return 'watch';
    case 'SURGEON_ALERT':
      return 'alert';
    case 'UNKNOWN':
      return 'unknown';
  }
}

export function outcomeTone(outcome: Outcome): Tone {
  switch (outcome) {
    case 'PASS':
      return 'nominal';
    case 'BLOCK':
      return 'info';
    case 'HOLD':
      return 'watch';
    case 'UNKNOWN':
      return 'unknown';
  }
}

export function measurementTone(status: Status): Tone {
  return status === 'OK' ? 'nominal' : 'unknown';
}

export function laneTone(lane: Lane): string {
  switch (lane) {
    case 'LAB DATA':
      return 'bg-lab/15 text-lab border-lab/40';
    case 'SIMULATED':
      return 'bg-simulated/15 text-simulated border-simulated/40';
    case 'INJECTED':
      return 'bg-injected/15 text-injected border-injected/40';
    case 'RECORDED-NON-ASTRONAUT':
      return 'bg-recorded/15 text-recorded border-recorded/40';
    case 'NONE':
      return 'bg-slate-500/15 text-slate-400 border-slate-500/40';
  }
}

export function laneExplanation(lane: Lane): string {
  switch (lane) {
    case 'LAB DATA':
      return 'Real NASA OSD-575 astronaut serum laboratory values. Sparse samples, not telemetry.';
    case 'SIMULATED':
      return 'Fixed-formula synthetic signals. Not measured, not from a device, not astronaut data.';
    case 'INJECTED':
      return 'Operator-injected test condition for the gate truth table. Not a real finding.';
    case 'RECORDED-NON-ASTRONAUT':
      return 'Real recordings from non-astronaut adults in a terrestrial study (PhysioNet, ODC-By 1.0).';
    case 'NONE':
      return 'No data loaded.';
  }
}

/** Unavailable / stale / failed values render as text, never as a number or a zero. */
export function formatValue(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'Not available';
  return value.toFixed(digits);
}

export function formatStatus(status: Status): string {
  switch (status) {
    case 'OK':
      return 'OK';
    case 'UNKNOWN':
      return 'Unknown';
    case 'NOT_AVAILABLE':
      return 'Not available';
    case 'STALE':
      return 'Stale';
    case 'FAILED':
      return 'Failed';
  }
}

export function stateLabel(state: WorkflowState): string {
  switch (state) {
    case 'NOMINAL':
      return 'Nominal';
    case 'SENSOR_ISSUE':
      return 'Sensor quality issue';
    case 'CONTEXT_COMPENSATED':
      return 'Context compensated';
    case 'CREW_CHECK':
      return 'Crew check requested';
    case 'SURGEON_ALERT':
      return 'Flight surgeon alert';
    case 'UNKNOWN':
      return 'Unknown';
  }
}
