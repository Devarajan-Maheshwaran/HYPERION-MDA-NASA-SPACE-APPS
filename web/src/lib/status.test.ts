import { describe, expect, it } from 'vitest';
import {
  formatStatus,
  formatValue,
  laneExplanation,
  measurementTone,
  organTone,
  outcomeTone,
  stateTone,
  toneClass,
} from './status';
import { ALLOWED_ACTIONS, DISCLAIMER } from './types';

describe('status honesty rules', () => {
  it('never maps UNKNOWN or NOT_AVAILABLE to the nominal (green) tone', () => {
    expect(organTone('UNKNOWN')).toBe('unknown');
    expect(organTone('NOT_AVAILABLE')).toBe('unknown');
    expect(organTone('UNKNOWN')).not.toBe('nominal');
    expect(organTone('NOT_AVAILABLE')).not.toBe('nominal');
  });

  it('never renders an unknown workflow state as nominal', () => {
    expect(stateTone('UNKNOWN')).toBe('unknown');
    expect(stateTone('SENSOR_ISSUE')).not.toBe('nominal');
    expect(stateTone('SURGEON_ALERT')).toBe('alert');
  });

  it('treats a non-OK measurement as unknown, including stale and failed', () => {
    for (const status of ['UNKNOWN', 'NOT_AVAILABLE', 'STALE', 'FAILED'] as const) {
      expect(measurementTone(status)).toBe('unknown');
      expect(measurementTone(status)).not.toBe('nominal');
    }
    expect(measurementTone('OK')).toBe('nominal');
  });

  it('does not give an unknown gate outcome a passing colour', () => {
    expect(outcomeTone('UNKNOWN')).toBe('unknown');
    expect(outcomeTone('HOLD')).toBe('watch');
  });

  it('uses a grey class for unknown, with no green in it', () => {
    const css = toneClass('unknown');
    expect(css).toContain('slate');
    expect(css).not.toContain('nominal');
    expect(css).not.toContain('#22c55e');
  });

  it('renders missing numbers as text, never as zero', () => {
    expect(formatValue(null)).toBe('Not available');
    expect(formatValue(undefined)).toBe('Not available');
    expect(formatValue(Number.NaN)).toBe('Not available');
    expect(formatValue(0)).toBe('0.0');
    expect(formatValue(72.45)).toBe('72.5');
  });

  it('labels every non-OK status explicitly', () => {
    expect(formatStatus('NOT_AVAILABLE')).toBe('Not available');
    expect(formatStatus('STALE')).toBe('Stale');
    expect(formatStatus('FAILED')).toBe('Failed');
    expect(formatStatus('UNKNOWN')).toBe('Unknown');
  });
});

describe('lane labelling', () => {
  it('states plainly that simulated data is not measured', () => {
    expect(laneExplanation('SIMULATED')).toContain('Not measured');
    expect(laneExplanation('SIMULATED')).toContain('not astronaut data');
  });

  it('states that recorded data is non-astronaut', () => {
    expect(laneExplanation('RECORDED-NON-ASTRONAUT')).toContain('non-astronaut');
  });

  it('describes injected data as a test condition', () => {
    expect(laneExplanation('INJECTED')).toContain('test condition');
  });

  it('says no data loaded for NONE', () => {
    expect(laneExplanation('NONE')).toBe('No data loaded.');
  });
});

describe('contract constants', () => {
  it('ships exactly the four allowed non-treatment actions', () => {
    expect(ALLOWED_ACTIONS).toEqual([
      'Repeat measurement',
      'Rest and recheck',
      'Check sensor',
      'Contact flight surgeon',
    ]);
  });

  it('contains no treatment advice in the allow-list', () => {
    const banned = ['salt', 'fluid', 'drink', 'potassium', 'medication', 'ration', 'therapy'];
    for (const action of ALLOWED_ACTIONS) {
      for (const word of banned) {
        expect(action.toLowerCase()).not.toContain(word);
      }
    }
  });

  it('carries the required disclaimer verbatim', () => {
    expect(DISCLAIMER).toBe('Demo thresholds, not clinically validated. Not a medical device.');
  });
});
